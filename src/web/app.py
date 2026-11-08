import logging
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import json
from ascon.ascon import ascon_decrypt
from datetime import datetime
from config import Config
from models import *
from forms import LoginForm, RegistrationForm
import paho.mqtt.client as mqtt_client
from threading import Thread
import base64


# ============= СНАЧАЛА СОЗДАЕМ ПРИЛОЖЕНИЕ =============

app = Flask(__name__)
app.config.from_object(Config)

handler = logging.FileHandler('/var/log/flask_mqtt.log') # Logs will be saved to flask.log
handler.setLevel(logging.DEBUG) # Set the log level
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
logging.getLogger('werkzeug').addHandler(handler)


# Инициализация расширений
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Хранение последних данных
latest_data = {
    'temperature': [],
    'humidity': [],
    'timestamps': []
}

TABLES = {
    'algorithms': Algorithm,
    'algorithm_types': AlgorithmType,
    'algorithm_schemes': AlgorithmScheme,
    'parameters': Parameters,
    'device_configuration': DeviceConfiguration,
    'tag_journal': TagJournal,
    'log_journal': LogJournal,
    'log_types': LogType,
    'anomalies': Anomaly,
    'anomaly_causes': AnomalyCause,
    'global_reports': GlobalReport,
    'report_types': ReportType,
    'sensor_data': SensorData
}

# ============= MQTT КЛИЕНТ (PAHO) =============

mqtt_client_instance = None

def on_connect(client, userdata, flags, rc):
    """Callback при подключении к MQTT брокеру"""
    if rc == 0:
        print(f"[{datetime.now()}] Успешно подключено к MQTT брокеру!")
        client.subscribe(app.config['MQTT_TOPIC'])
        print(f"[{datetime.now()}] Подписка на топик: {app.config['MQTT_TOPIC']}")
    else:
        print(f"[{datetime.now()}] ОШИБКА подключения к MQTT брокеру!")
        print(f"Код ошибки: {rc}")
        error_messages = {
            1: "Неверная версия протокола",
            2: "Неверный client ID",
            3: "Сервер недоступен",
            4: "Неверный логин/пароль",
            5: "Нет авторизации"
        }
        print(f"Описание: {error_messages.get(rc, 'Неизвестная ошибка')}")

def on_disconnect(client, userdata, rc):
    """Callback при отключении от MQTT брокера"""
    print(f"✗ [{datetime.now()}] Отключено от MQTT брокера (код: {rc})")
    if rc != 0:
        print("  Попытка переподключения...")

def on_message(client, userdata, message):
    """Callback при получении MQTT сообщения"""
    
    try:
        payload = json.loads(message.payload.decode())
        
        # Расшифровка
        decrypted_data = decrypt_ascon_data(payload)
        
        if decrypted_data:
            
            # Сохранение в БД (используем app context)
            with app.app_context():
                #save_sensor_data(decrypted_data)
                update_dashboard(decrypted_data)
        else:
            print(f"[ERROR] Не удалось расшифровать данные")
            
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка парсинга JSON: {e}")
    except Exception as e:
        print(f"[ERROR] Ошибка обработки MQTT: {e}")
        import traceback
        traceback.print_exc()

def create_mqtt_client():
    """Создание и настройка MQTT клиента"""
    client = mqtt_client.Client(
        client_id=f"flask-mqtt-{datetime.now().timestamp()}",
        clean_session=True
    )
    
    # Установка callback'ов
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Если требуется авторизация
    if app.config.get('MQTT_USERNAME'):
        client.username_pw_set(
            app.config['MQTT_USERNAME'],
            app.config['MQTT_PASSWORD']
        )
    
    return client

def start_mqtt_client():
    """Запуск MQTT клиента"""
    global mqtt_client_instance
    
    try:
        mqtt_client_instance = create_mqtt_client()
        
        print(f"[INFO] Подключение к MQTT брокеру...")
        print(f"  Адрес: {app.config['MQTT_BROKER_URL']}:{app.config['MQTT_BROKER_PORT']}")
        print(f"  Топик: {app.config['MQTT_TOPIC']}")
        
        mqtt_client_instance.connect(
            app.config['MQTT_BROKER_URL'],
            app.config['MQTT_BROKER_PORT'],
            app.config.get('MQTT_KEEPALIVE', 60)
        )
        
        # Запуск loop в отдельном потоке
        mqtt_client_instance.loop_start()
        
        
    except Exception as e:
        print(f"[{datetime.now()}] Ошибка запуска MQTT клиента: {e}")
        import traceback
        traceback.print_exc()

# ============= MQTT Функции =============

def decrypt_ascon_data(encrypted_payload):
    """Расшифровывает данные Ascon"""
    try:
                # Проверяем наличие необходимых полей
        required_fields = ['nonce', 'ciphertext', 'associated_data', 'algorithm']
        for field in required_fields:
            if field not in encrypted_payload:
                print(f"[ERROR] Отсутствует поле: {field}")
                return None
        
        associated_data_bytes = base64.b64decode(encrypted_payload["associated_data"])
        metadata = json.loads(associated_data_bytes.decode('utf-8'))

        device_id = metadata.get("device_id", "unknown")
        timestamp = metadata.get("timestamp", "unknown")
        nonce = base64.b64decode(encrypted_payload["nonce"])
        ciphertext = base64.b64decode(encrypted_payload["ciphertext"])
        variant = encrypted_payload["algorithm"]

        
        # Расшифровка
        plaintext = ascon_decrypt(
            app.config['ASCON_KEY'],
            nonce,
            associated_data_bytes,
            ciphertext,
            variant
        )
        
        decrypted = json.loads(plaintext.decode('utf-8'))
        
        return decrypted
        
    except ValueError as e:
        print("[ERROR] Не удалось расшифровать данные: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Ошибка расшифровки: {e}")
        import traceback
        traceback.print_exc()
        return None

    return None


def save_sensor_data(data):
    """Сохраняет данные в БД"""
    try:
        log_entry = LogJournal(
            Log_Type_ID=1,
            Record_Date=datetime.fromisoformat(data['timestamp']),
            Anomaly_ID=None
        )
        db.session.add(log_entry)
        db.session.flush()
        
        sensor_entry = SensorData(
            Record_ID=log_entry.Record_ID,
            Temperature=data.get('temperature'),
            Humidity=data.get('humidity'),
        )
        
        print(f"[{datetime.now()}] ✓ Данные сохранены (Record_ID: {log_entry.Record_ID})")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Ошибка сохранения в БД: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_dashboard(data):
    """Отправляет обновления на дашборд через SocketIO"""
    max_points = 50
    
    latest_data['temperature'].append(data.get('temperature'))
    latest_data['humidity'].append(data.get('humidity'))
    latest_data['timestamps'].append(data.get('timestamp'))
    
    if len(latest_data['temperature']) > max_points:
        for key in latest_data:
            latest_data[key] = latest_data[key][-max_points:]
    
    socketio.emit('sensor_update', {
        'temperature': data.get('temperature'),
        'humidity': data.get('humidity'),
        'timestamp': data.get('timestamp')
    })

def load_data_from_db():
    """Загрузка последних данных из БД"""
    try:
        records = db.session.query(
            LogJournal.Record_Date,
            SensorData.Temperature,
            SensorData.Humidity,
        ).join(
            SensorData, LogJournal.Record_ID == SensorData.Record_ID
        ).order_by(
            LogJournal.Record_Date.desc()
        ).limit(50).all()
        
        if records:
            records = list(reversed(records))
            
            latest_data['timestamps'] = [r.Record_Date.isoformat() for r in records]
            latest_data['temperature'] = [float(r.Temperature) if r.Temperature else 0 for r in records]
            latest_data['humidity'] = [float(r.Humidity) if r.Humidity else 0 for r in records]
            
            print(f"[INFO] Загружено {len(records)} записей из БД")
        else:
            print("[INFO] Нет данных в БД")
            
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки из БД: {e}")

# ============= Декораторы =============

def role_required(*roles):
    """Декоратор для проверки роли пользователя"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Требуется авторизация.', 'warning')
                return redirect(url_for('login'))
            
            if current_user.role not in [r.value for r in roles]:
                flash('У вас нет доступа к этой странице.', 'danger')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def table_access_required(f):
    """Декоратор для проверки доступа к таблице"""
    @wraps(f)
    def decorated_function(table_name, *args, **kwargs):
        if not current_user.is_authenticated:
            flash('Требуется авторизация.', 'warning')
            return redirect(url_for('login'))
        
        if not current_user.has_table_access(table_name):
            flash(f'У вас нет доступа к таблице {table_name}.', 'danger')
            return redirect(url_for('tables_list'))
        
        return f(table_name, *args, **kwargs)
    return decorated_function

# ============= Routes (все ваши существующие роуты) =============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Ваш аккаунт деактивирован.', 'danger')
                return redirect(url_for('login'))
            
            login_user(user, remember=form.remember_me.data)
            flash(f'Добро пожаловать, {user.username}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role='viewer'
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('dashboard.html')

@app.route('/api/latest-data')
@login_required
def get_latest_data():
    if not latest_data['temperature']:
        print("[INFO] latest_data пустой, загружаем из БД...")
        load_data_from_db()
    
    return jsonify(latest_data)

@app.route('/tables')
@login_required
def tables_list():
    role_enum = current_user.get_role_enum()
    permissions = ROLE_PERMISSIONS.get(role_enum, {})
    allowed_tables = permissions.get('tables', [])
    accessible_tables = {k: v for k, v in TABLES.items() if k in allowed_tables}
    
    return render_template('tables.html', 
                         tables=accessible_tables.keys(),
                         user_role=current_user.role)

@app.route('/table/<table_name>')
@login_required
@table_access_required
def view_table(table_name):
    if table_name not in TABLES:
        flash('Таблица не найдена.', 'danger')
        return redirect(url_for('tables_list'))
    
    model = TABLES[table_name]
    records = model.query.all()
    columns = list(records[0].to_dict().keys()) if records else []
    
    return render_template('table_edit.html', 
                         table_name=table_name,
                         records=[r.to_dict() for r in records],
                         columns=columns,
                         can_create=current_user.can_create(table_name),
                         can_update=current_user.can_update(table_name),
                         can_delete=current_user.can_delete(table_name))

# Добавьте остальные ваши роуты (CRUD API и т.д.)

# ============= Debug endpoints =============

@app.route('/debug/mqtt-status')
@login_required
def mqtt_status():
    """Проверка статуса MQTT подключения"""
    global mqtt_client_instance
    
    is_connected = False
    if mqtt_client_instance:
        is_connected = mqtt_client_instance.is_connected()
    
    return jsonify({
        'mqtt_connected': is_connected,
        'broker_url': app.config['MQTT_BROKER_URL'],
        'broker_port': app.config['MQTT_BROKER_PORT'],
        'topic': app.config['MQTT_TOPIC'],
        'client_exists': mqtt_client_instance is not None
    })


@app.route('/api/<table_name>/<record_id>', methods=['PUT'])
@login_required
def update_record(table_name, record_id):
    if table_name not in TABLES or not current_user.has_table_access(table_name):
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    if not current_user.can_update(table_name):
        return jsonify({'error': 'Нет прав на изменение'}), 403
    
    try:
        model = TABLES[table_name]
        
        # Попытка получить запись по разным типам ID
        try:
            record_id = int(record_id)
            record = model.query.get(record_id)
        except:
            # Если не число, пробуем как строку
            record = model.query.get(record_id)
        
        if not record:
            return jsonify({'error': 'Запись не найдена'}), 404
        
        data = request.get_json()
        
        # Обновляем только непервичные ключи
        for key, value in data.items():
            if hasattr(record, key):
                setattr(record, key, value)
        
        db.session.commit()
        
        db_logger.info(f"Обновлена запись: таблица={table_name}, ID={record_id}, пользователь={current_user.username}")
        
        return jsonify({'message': 'Запись обновлена', 'data': record.to_dict()})
    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Ошибка обновления записи: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@app.route('/api/<table_name>/<record_id>', methods=['DELETE'])
@login_required
def delete_record(table_name, record_id):
    if table_name not in TABLES or not current_user.has_table_access(table_name):
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    if not current_user.can_delete(table_name):
        return jsonify({'error': 'Нет прав на удаление'}), 403
    
    try:
        model = TABLES[table_name]
        
        # Попытка получить запись
        try:
            record_id = int(record_id)
            record = model.query.get(record_id)
        except:
            record = model.query.get(record_id)
        
        if not record:
            return jsonify({'error': 'Запись не найдена'}), 404
        
        db.session.delete(record)
        db.session.commit()
        
        db_logger.warning(f"Удалена запись: таблица={table_name}, ID={record_id}, пользователь={current_user.username}")
        
        json_audit_logger.warning('', extra={
            'user': current_user.username,
            'ip': request.remote_addr,
            'action': 'delete',
            'table': table_name,
            'record_id': str(record_id)
        })
        
        return jsonify({'message': 'Запись удалена'})
    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Ошибка удаления записи: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 400


@app.route('/generate-test-data/<int:count>')
@login_required
def generate_test_data(count=10):
    """Генерация тестовых данных"""
    import random
    from datetime import timedelta
    
    if count > 100:
        count = 100
    
    base_time = datetime.now()
    
    for i in range(count):
        test_data = {
            'device_id': 1,
            'timestamp': (base_time - timedelta(minutes=count-i)).isoformat(),
            'temperature': round(random.uniform(20.0, 30.0), 2),
            'humidity': round(random.uniform(40.0, 70.0), 2),
            'algorithm_id': 1,
            'tag_id': 1
        }
        
        #save_sensor_data(test_data)
    
    load_data_from_db()
    
    return jsonify({
        'status': 'success',
        'message': f'Создано {count} тестовых записей',
        'data_count': len(latest_data['temperature'])
    })

# ============= Инициализация =============

def create_default_users():
    """Создание пользователей по умолчанию"""
    users = [
        {'username': 'admin', 'email': 'admin@iot.local', 'password': os.environ["BOOTSTRAP_ADMIN_PASSWORD"], 'role': 'admin'},
        {'username': 'operator', 'email': 'operator@iot.local', 'password': os.environ["BOOTSTRAP_OPERATOR_PASSWORD"], 'role': 'operator'},
        {'username': 'viewer', 'email': 'viewer@iot.local', 'password': os.environ["BOOTSTRAP_VIEWER_PASSWORD"], 'role': 'viewer'}
    ]
    
    for user_data in users:
        user = User.query.filter_by(username=user_data['username']).first()
        if not user:
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                role=user_data['role']
            )
            user.set_password(user_data['password'])
            db.session.add(user)
            print(f"Создан пользователь: {user_data['username']}")
    
    db.session.commit()

# ============= ГЛАВНАЯ ТОЧКА ВХОДА =============

if __name__ == '__main__':
    # Инициализация БД
    with app.app_context():
        db.create_all()
        create_default_users()
    
    # Запуск MQTT клиента
    start_mqtt_client()
    
    # Запуск Flask с SocketIO
    print(f"\n{'='*60}")
    print(f"  Запуск Flask приложения")
    print(f"  URL: http://0.0.0.0:5000")
    print(f"{'='*60}\n")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

