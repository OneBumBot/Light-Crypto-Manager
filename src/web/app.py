import logging
from src.mqtt_transport import configure_client
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, abort
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect, CSRFError, validate_csrf
from wtforms import ValidationError
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from threading import Lock
import secrets
from src.web.security import safe_next, validated_changes, record_identity
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import json
from src.web.ascon.ascon import ascon_decrypt
from src.runtime import database_url
from src.telemetry import decode_packet, load_registry
from src.replay import admit, metadata as replay_metadata
from datetime import datetime
from src.web.config import Config
from src.web.models import *
from src.web.forms import LoginForm, RegistrationForm
import paho.mqtt.client as mqtt_client
import base64


# ============= СНАЧАЛА СОЗДАЕМ ПРИЛОЖЕНИЕ =============

app = Flask(__name__)
app.config.from_object(Config)

def configure_logging():
    """File logging is optional and is configured only at explicit startup."""
    from pathlib import Path

    path = os.environ.get("LOG_FILE")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


db_logger = logging.getLogger("lightcrypto.database")
error_logger = logging.getLogger("lightcrypto.errors")
json_audit_logger = logging.getLogger("lightcrypto.audit")


# Инициализация расширений
db.init_app(app)
csrf = CSRFProtect(app)
socketio = SocketIO(app, async_mode="threading", max_http_buffer_size=8192)
socket_connections = {}
socket_lock = Lock()

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id), populate_existing=True)
    except (ValueError, TypeError):
        return None
    except SQLAlchemyError:
        app.logger.warning('Authentication database temporarily unavailable')
        abort(503, description='PostgreSQL недоступна. Актуальные права доступа проверить невозможно.')
    return user if user and user.is_active and user.role in {r.value for r in UserRole} else None

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith(('/api/', '/debug/')):
        return jsonify({'error': 'Требуется вход'}), 401
    return redirect(url_for('login', next=request.path))


@app.errorhandler(CSRFError)
def csrf_failure(error):
    return jsonify({'error': 'Запрос отклонён'}), 400


@app.errorhandler(HTTPException)
def http_failure(error):
    return jsonify({'error': 'Запрос отклонён'}), error.code


@app.errorhandler(Exception)
def request_failure(error):
    db.session.rollback()
    app.logger.error('Request failed (%s)', type(error).__name__)
    return jsonify({'error': 'Ошибка обработки запроса'}), 500


@app.before_request
def authenticated_session_token():
    if current_user.is_authenticated:
        session.setdefault('socket_token', secrets.token_urlsafe(32))


@app.after_request
def response_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response


@socketio.on('connect')
def socket_connect(auth=None):
    if not current_user.is_authenticated or not current_user.has_table_access('sensor_data'):
        return False
    token = auth.get('csrf_token') if isinstance(auth,dict) else None
    if type(token) is not str or len(token)>256 or not session.get('socket_token'):
        return False
    try:
        validate_csrf(token)
    except ValidationError:
        return False
    with socket_lock:
        socket_connections[request.sid] = (current_user.id, session['socket_token'])


@socketio.on('disconnect')
def socket_disconnect(reason=None):
    with socket_lock:
        socket_connections.pop(request.sid, None)


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

def on_connect(client, userdata, flags, rc, properties):
    """Callback при подключении к MQTT брокеру"""
    if rc == 0:
        print(f"[{datetime.now()}] Успешно подключено к MQTT брокеру!")
        client.subscribe(app.config['MQTT_TOPIC'], qos=1)
        print(f"[{datetime.now()}] Подписка на топик: {app.config['MQTT_TOPIC']}")
    else:
        print(f"[{datetime.now()}] ОШИБКА подключения к MQTT брокеру!")
        print(f"Код ошибки: {rc}")

def on_disconnect(client, userdata, flags, rc, properties):
    """Callback при отключении от MQTT брокера"""
    print(f"✗ [{datetime.now()}] Отключено от MQTT брокера (код: {rc})")
    if rc != 0:
        print("  Попытка переподключения...")

def on_message(client, userdata, message):
    try:
        verified = decode_packet(message.payload, message.topic, load_registry())
        with app.app_context():
            with db.engine.begin() as connection:
                from src.devices import require_enabled
                require_enabled(connection,verified,message.topic)
                accepted = admit(connection, verified, 'web')
            if accepted:
                update_dashboard(verified.sensor)
    except Exception as error:
        app.logger.warning('MQTT telemetry rejected (%s)', type(error).__name__)

def create_mqtt_client():
    """Создание и настройка MQTT клиента"""
    client = mqtt_client.Client(
        mqtt_client.CallbackAPIVersion.VERSION2,
        client_id=f"flask-mqtt-{datetime.now().timestamp()}",
        clean_session=True
    )
    
    # Установка callback'ов
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    configure_client(client)

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
        app.logger.warning("MQTT startup failed (%s)", type(e).__name__)
        import traceback
        app.logger.warning("Operation failed (%s)", type(e).__name__)

# ============= MQTT Функции =============

def decrypt_ascon_data(encrypted_payload, topic, registry=None):
    return decode_packet(encrypted_payload, topic, registry or load_registry()).sensor


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
        app.logger.warning("Sensor save failed (%s)", type(e).__name__)
        import traceback
        app.logger.warning("Operation failed (%s)", type(e).__name__)
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
    
    with socket_lock:
        peers = list(socket_connections.items())
    for sid, (user_id, token) in peers:
        user = db.session.get(User, user_id, populate_existing=True)
        if not user or not user.is_active or user.role not in {r.value for r in UserRole} or not user.has_table_access('sensor_data'):
            socketio.server.disconnect(sid, namespace='/')
            continue
        socketio.emit('sensor_update', {
            'temperature': data.get('temperature'), 'humidity': data.get('humidity'),
            'timestamp': data.get('timestamp'),
        }, to=sid)


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
        app.logger.warning("History load failed (%s)", type(e).__name__)

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
            if not user.is_active or user.role not in {r.value for r in UserRole}:
                flash('Ваш аккаунт деактивирован.', 'danger')
                return redirect(url_for('login'))
            
            login_user(user, remember=form.remember_me.data)
            session['socket_token'] = secrets.token_urlsafe(32)
            flash(f'Добро пожаловать, {user.username}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if safe_next(next_page) else redirect(url_for('index'))
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

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    token = session.pop('socket_token', None)
    with socket_lock:
        peers = [sid for sid, identity in socket_connections.items() if identity == (current_user.id, token)]
    for sid in peers:
        socketio.server.disconnect(sid, namespace='/')
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    if not current_user.has_table_access('sensor_data'): abort(403)
    return render_template('monitoring.html', device=None)

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
    columns = [column.key for column in model.__table__.columns]
    
    return render_template('table_edit.html', 
                         table_name=table_name,
                         records=[r.to_dict() for r in records],
                         columns=columns,
                         primary_keys=[c.key for c in model.__table__.primary_key.columns],
                         field_types={c.key: c.type.python_type.__name__ for c in model.__table__.columns},
                         can_create=current_user.can_create(table_name),
                         can_update=current_user.can_update(table_name),
                         can_delete=current_user.can_delete(table_name))

# Добавьте остальные ваши роуты (CRUD API и т.д.)

# ============= Debug endpoints =============

@app.route('/debug/mqtt-status')
@login_required
@role_required(UserRole.ADMIN)
def mqtt_status():
    """Проверка статуса MQTT подключения"""
    global mqtt_client_instance
    
    is_connected = False
    if mqtt_client_instance:
        is_connected = mqtt_client_instance.is_connected()
    
    return jsonify({
        'mqtt_connected': is_connected,
        'client_exists': mqtt_client_instance is not None
    })


def operation_model(table_name, operation):
    if table_name not in TABLES or not current_user.has_table_access(table_name):
        abort(403)
    if not getattr(current_user, 'can_' + operation)(table_name):
        abort(403)
    return TABLES[table_name]


@app.route('/api/<table_name>/<record_id>', methods=['PUT'])
@login_required
def update_record(table_name, record_id):
    model = operation_model(table_name, 'update')
    identity = record_identity(model, record_id)
    changes = validated_changes(table_name, model, request.get_json(silent=True))
    try:
        record = db.session.get(model, identity)
        if record is None:
            abort(404)
        for name,value in changes.items():
            setattr(record, name, value)
        db.session.commit()
        return jsonify({'message': 'Запись обновлена', 'data': record.to_dict()})
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.warning('Database update rejected')
        return jsonify({'error': 'Изменение отклонено'}), 400


@app.route('/api/<table_name>/<record_id>', methods=['DELETE'])
@login_required
def delete_record(table_name, record_id):
    model = operation_model(table_name, 'delete')
    identity = record_identity(model, record_id)
    try:
        record = db.session.get(model, identity)
        if record is None:
            abort(404)
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Запись удалена'})
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.warning('Database delete rejected')
        return jsonify({'error': 'Удаление отклонено'}), 400


@app.route('/generate-test-data/<int:count>', methods=['POST'])
@login_required
@role_required(UserRole.ADMIN)
def generate_test_data(count=10):
    return jsonify({'error': 'Генератор данных пока недоступен'}), 501

@app.get('/ml')
@login_required
def ml_results_page():
    if not current_user.has_table_access('sensor_data'): abort(403)
    return render_template('ml_results.html')


@app.get('/api/ml/events')
@login_required
def ml_results():
    if not current_user.has_table_access('sensor_data'): abort(403)
    from src.ml_storage import events
    from src.telemetry import DEVICE
    from sqlalchemy import select
    try:
        if set(request.args)-{'device_id','limit','offset'} or any(len(request.args.getlist(k))!=1 for k in request.args): abort(400)
        limit=int(request.args.get('limit','50'));offset=int(request.args.get('offset','0'))
        device=request.args.get('device_id')
        if not 1<=limit<=200 or not 0<=offset<=10000 or (device is not None and not DEVICE.fullmatch(device)):abort(400)
    except (ValueError,TypeError):abort(400)
    columns=[events.c[k] for k in ['device_id','key_epoch','sequence_number','detector','model_id','model_version',
        'feature_version','evaluated_at','score','threshold','is_anomaly','status','diagnostic','prepare_ms','inference_ms','delivery_ack_lag_seconds']]
    query=select(*columns).order_by(events.c.evaluated_at.desc().nullslast(),events.c.id.desc()).limit(limit).offset(offset)
    if device is not None:query=query.where(events.c.device_id==device)
    try:
        with db.engine.connect() as c:rows=c.execute(query).mappings().all()
        items=[{k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in row.items()} for row in rows]
        return jsonify(items=items,limit=limit,offset=offset,interpretation='Research signals; not confirmed cyberattacks')
    except SQLAlchemyError:
        return jsonify(error='Результаты ML временно недоступны'),503


@app.get('/api/ml/status')
@login_required
def ml_status():
    if not current_user.has_table_access('sensor_data'):abort(403)
    from src.ml_storage import models,events,feed_state
    from src.outbox import metrics
    from sqlalchemy import select,func
    from datetime import timezone,timedelta
    try:
        with db.engine.connect() as c:
            rows=c.execute(select(models.c.model_id,models.c.model_version,models.c.feature_version,
                models.c.detector,models.c.mode,models.c.score_semantics,models.c.score_upper_bound,models.c.status,models.c.heartbeat_at,models.c.diagnostic)
                .order_by(models.c.heartbeat_at.desc()).limit(50)).mappings().all()
            state=c.execute(select(feed_state)).mappings().first()
            counts=dict(c.execute(select(events.c.status,func.count()).group_by(events.c.status)).all())
            timing=c.execute(select(func.avg(events.c.prepare_ms),func.avg(events.c.inference_ms),
                func.avg(events.c.delivery_ack_lag_seconds))).one()
            rejected=None;rules=None
            if current_user.role=='admin':
                rejected=c.scalar(select(func.coalesce(func.sum(metrics.c.count),0)).where(metrics.c.kind=='rejected'))
            if current_user.has_table_access('anomalies'):
                rules=c.scalar(select(func.count()).select_from(Anomaly))
        now=datetime.now(timezone.utc)
        model_rows=[]
        for row in rows:
            value=dict(row);value['heartbeat_at']=value['heartbeat_at'].isoformat()
            value['stale']=(now-row['heartbeat_at'])>timedelta(seconds=30)
            model_rows.append(value)
        return jsonify(models=model_rows,feed=dict(state) if state else None,
            event_status_counts=counts,mean_prepare_ms=timing[0],mean_inference_ms=timing[1],
            mean_delivery_ack_lag_seconds=timing[2],
            protocol_rejections=rejected,rule_anomalies=rules,
            score_interpretation='Model-specific higher-is-more-anomalous score; not a common attack probability')
    except SQLAlchemyError:
        return jsonify(error='Статус ML временно недоступен'),503


history_repository_lock = Lock()


def history_repository():
    # Lazy initialization; no Mongo credentials needed for legacy routes/tests.
    from src.mongo_repository import MongoRepository
    with history_repository_lock:
        if 'telemetry_repository' not in app.extensions:
            app.extensions['telemetry_repository'] = MongoRepository('history')
        return app.extensions['telemetry_repository']


@app.get('/telemetry')
@login_required
def telemetry_history_page():
    if not current_user.has_table_access('sensor_data'): abort(403)
    return render_template('telemetry_history.html')


@app.get('/api/telemetry/history')
@login_required
def telemetry_history():
    if not current_user.has_table_access('sensor_data'):
        abort(403)
    allowed = {'device_id','start','end','limit','offset'}
    if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args):
        abort(400)
    try:
        limit=int(request.args.get('limit','100'))
        offset=int(request.args.get('offset','0'))
        # Repository repeats validation at its public boundary.
        from src.mongo_repository import utc_millis
        from src.telemetry import DEVICE
        device=request.args.get('device_id')
        if device is not None and not DEVICE.fullmatch(device): abort(400)
        start=utc_millis(request.args['start']) if 'start' in request.args else None
        end=utc_millis(request.args['end']) if 'end' in request.args else None
        if not 1<=limit<=500 or not 0<=offset<=10000 or (start and end and start>end): abort(400)
    except (ValueError,TypeError,OverflowError):
        abort(400)
    try:
        rows=history_repository().history(device=device,start=start,end=end,limit=limit,offset=offset)
        return jsonify({'items':rows,'limit':limit,'offset':offset})
    except Exception as error:
        app.logger.warning('Telemetry history unavailable (%s)',type(error).__name__)
        return jsonify({'error':'История телеметрии временно недоступна'}),503


@app.get('/api/telemetry/metrics')
@login_required
def telemetry_metrics():
    if current_user.role != 'admin': abort(403)
    from sqlalchemy import select, func
    from datetime import timedelta, timezone
    from src.outbox import outbox, metrics
    try:
        cutoff=datetime.now(timezone.utc)-timedelta(minutes=1)
        with db.engine.connect() as connection:
            counts=dict(connection.execute(select(outbox.c.status,func.count()).group_by(outbox.c.status)).all())
            counters=dict(connection.execute(select(metrics.c.kind,func.sum(metrics.c.count))
                .where(metrics.c.minute>=cutoff.replace(second=0,microsecond=0)).group_by(metrics.c.kind)).all())
            oldest=connection.scalar(select(func.min(outbox.c.created_at)).where(outbox.c.status!='delivered'))
            latency=connection.scalar(select(func.avg(func.extract('epoch',outbox.c.delivered_at-outbox.c.created_at)))
                .where(outbox.c.delivered_at>=cutoff))
        # Two minute-aligned buckets; rate explicitly reports its actual window.
        window=(datetime.now(timezone.utc)-cutoff.replace(second=0,microsecond=0)).total_seconds()
        mongo_count=history_repository().collection.count_documents({},maxTimeMS=2000)
        return jsonify(outbox=counts,counters={k:int(v) for k,v in counters.items()},
            incoming_per_second=float(counters.get('incoming',0))/window,window_seconds=window,
            oldest_pending_seconds=(datetime.now(timezone.utc)-oldest).total_seconds() if oldest else 0,
            mean_delivery_seconds=float(latency) if latency is not None else None,mongo_documents=mongo_count)
    except Exception as error:
        app.logger.warning('Metrics unavailable (%s)',type(error).__name__)
        return jsonify({'error':'Метрики временно недоступны'}),503


# ============= Инициализация =============

def create_default_users():
    """Create only explicitly requested accounts, never reset existing passwords."""
    created = 0
    for role in ('admin', 'operator', 'viewer'):
        password = os.environ.get(f'BOOTSTRAP_{role.upper()}_PASSWORD')
        if not password or User.query.filter_by(username=role).first():
            continue
        user = User(username=role, email=f'{role}@iot.local', role=role)
        user.set_password(password)
        db.session.add(user)
        created += 1
    db.session.commit()
    return created


# ============= ГЛАВНАЯ ТОЧКА ВХОДА =============

from src.policy.web import blueprint as policy_blueprint
app.register_blueprint(policy_blueprint)
from src.device_control.web import blueprint as control_blueprint
app.register_blueprint(control_blueprint)
from src.web.monitoring import blueprint as monitoring_blueprint
app.register_blueprint(monitoring_blueprint)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Legacy Flask UI on PostgreSQL")
    parser.add_argument('command', nargs='?', default='serve',
                        choices=['serve', 'init-db', 'bootstrap-users'])
    args = parser.parse_args()
    database_url()  # Require an explicit PostgreSQL URL at runtime.
    configure_logging()
    if args.command == 'init-db':
        with app.app_context():
            from src.migrate import upgrade
            upgrade(db.engine)
        print("PostgreSQL migrations applied")
        return
    if args.command == 'bootstrap-users':
        with app.app_context():
            count = create_default_users()
        print(f"Created accounts: {count}")
        return
    if not app.config['SECRET_KEY']:
        raise ValueError('FLASK_SECRET_KEY is required to serve the web UI')
    try:
        if os.environ.get('WEB_MQTT_ENABLED', '0') == '1':
            load_registry()
            start_mqtt_client()
        socketio.run(app, host=os.environ.get('WEB_HOST', '127.0.0.1'),
                     port=int(os.environ.get('WEB_PORT', '5000')), debug=False,
                     allow_unsafe_werkzeug=True)
    finally:
        if mqtt_client_instance:
            mqtt_client_instance.disconnect()
            mqtt_client_instance.loop_stop()


if __name__ == '__main__':
    main()
