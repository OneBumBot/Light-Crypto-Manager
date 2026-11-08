# Инвентаризация LightCrypto Manager

> Исторический снимок этапа 1 (`76ca884`). Изменения этапа 2, PostgreSQL,
> зависимости и фактический запуск описаны в [RUNTIME.md](RUNTIME.md),
> [COMPOSE.md](COMPOSE.md) (актуальный этап 4), [SECURITY.md](SECURITY.md) и
> [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md). Утверждения об отсутствующих
> пакетах и MSSQL ниже относятся к состоянию до этапа 2.

Дата: 2026-11-08. Основание: фактические файлы, безопасная база `908dd56`
и сохранение прав исполнения `c352d81`. Инвентаризация выполнена после этих
коммитов. Изменения безопасности этапа 0 описаны в [BASELINE.md](BASELINE.md).
Наличие кода ниже не означает работоспособность сервиса.

## Полнота обследования

В исходном дереве: 9 Python-файлов, notebook из 13 кодовых ячеек, 7 HTML-шаблонов,
CSS, JS, requirements, README и LICENSE Ascon. Все перечисленные файлы прочитаны.
ZIP просмотрен без распаковки: 72 записи, включая копии исходников, конфигурации,
вложенную `.git` и кеш Python. Вложенный репозиторий Ascon сохранён; его исходники
учтены корневым Git как обычные файлы. Других `.git` под корнем не найдено.
Служебные `.agents/`, `.aws/`, `.codex/` не являются модулями проекта и исключены.
`AGENTS.md` в дереве проекта не найден. Кеш и архив сохранены локально, исключены
из Git. Датасетов, моделей, миграций, Dockerfile/Compose, тестового набора,
FastAPI, PostgreSQL и конфигурации настоящего MQTT-брокера нет.

## Файлы и повторное использование

Пути относительно корня репозитория.

| Файл | Назначение / зависимости | Повторное использование |
|---|---|---|
| `src/publisher/mqtt_pub.py` | Генератор датчиков, Ascon, Paho MQTT; NumPy, внешний `pyascon.ascon` | Сохранить генератор и оболочку пакета; согласовать импорты, конфигурацию и проверки |
| `src/brocker/mqtt_brocker.py` | MQTT subscriber, дешифрование, пороговые аномалии, MSSQL через pymssql | Основа отдельного worker после исправления SQL, ошибок и импортов; брокером не является |
| `src/classifier/iot-test.ipynb` | Обучение и оценка RF/IF по Edge-IIoT сетевым признакам | Основа воспроизводимых экспериментов; напрямую к текущим датчикам неприменима |
| `src/web/app.py` | Flask, HTTP/API, роли, Socket.IO, отдельный MQTT-клиент, запросы SQLAlchemy | Сохранить пользовательские сценарии; отделять транспорт и обработку постепенно |
| `src/web/config.py` | MSSQL/MQTT/Flask/Ascon конфигурация | Параметры окружения введены на этапе 0; требуется дальнейшая валидация |
| `src/web/models.py` | 14 SQLAlchemy-моделей, роли, сериализация и пароли Werkzeug | Сохранить предметную область; проверить схему и ограничения перед миграцией |
| `src/web/forms.py` | WTForms: вход, регистрация, уникальность имени/email | Перенести требования к полям и пользовательские сценарии |
| `src/web/requirements.txt` | 11 точных версий для web; полного окружения не описывает | Отправная точка для раздельных воспроизводимых зависимостей |
| `src/web/templates/base.html` | Общий Bootstrap layout, меню, flash, клиент Socket.IO | Сохранить; исправить вывод строковой роли через `.name` |
| `src/web/templates/dashboard.html` | Адаптивные карточки и графики; активный inline JS, Chart.js | Сохранить; состояние соединения и обработку нулей исправить |
| `src/web/templates/login.html` | Форма входа с `hidden_tag()` | Сохранить |
| `src/web/templates/register.html` | Форма регистрации с `hidden_tag()` | Сохранить |
| `src/web/templates/tables.html` | Список доступных таблиц по роли | Сохранить; подпись про полный CRUD сейчас неточна |
| `src/web/templates/table_edit.html` | Активная таблица и модальные окна просмотра/CRUD | Сохранить макет; закрыть XSS, согласовать API, типы и составные ключи |
| `src/web/templates/table_edit2.html` | Альтернативная таблица, не подключена маршрутами; модальные элементы отсутствуют | Сохранить как legacy; сначала решить, нужен ли второй вариант |
| `src/web/static/js/dashboard.js` | Вторая реализация графиков и Socket.IO | Сейчас не подключена шаблонами; выбирать одну реализацию после проверок |
| `src/web/static/css/style.css` | Общие стили, высота графика | Переиспользовать |
| `src/web/ascon/ascon.py` | Pure Python AEAD/hash/XOF/MAC, перестановка и demo | Переиспользовать после независимых KAT и оценки ограничений |
| `src/web/ascon/genkat.py` | Генератор KAT с проверкой encrypt/decrypt | Полезен для локальной самопроверки; не независимый эталон |
| `src/web/ascon/writer.py` | Запись векторов в TXT/JSON | Используется genkat; `typing.override` требует Python 3.12+ |
| `src/web/ascon/README.md` | Описание pyascon и вариантов, ссылка на draft стандарта | Сохранить происхождение; проверять расхождения с текущим стандартом |
| `src/web/ascon/LICENSE` | CC0 1.0 Universal | Сохранить при повторном использовании |
| `src/web/web_mqtt.zip` | Резервная копия web с конфигурацией и вложенной историей | Только приватный архив; не использовать как пакет развёртывания |
| `src/web/ascon/.git/` | История upstream, master, HEAD ed24e54 | Сохранена локально; не подмодуль корневого репозитория |
| `src/web/ascon/__pycache__/` | Исходный кеш `.pyc`, плюс кеш локального импорта при проверке | Не исходники; исключён |
| `.gitignore`, `docs/BASELINE.md` | Безопасное сохранение исходной версии | Поддерживать |
| `docs/INVENTORY.md`, `CURRENT_ARCHITECTURE.md`, `KNOWN_ISSUES.md`, `DEVELOPMENT_STATUS.md` | Результаты этапа 1 и план | Обновлять по фактическим результатам следующих этапов |

## Publisher

Основной цикл выполняется при импорте файла, без main guard. Каждые 10 секунд
генерируются `temperature ~ N(50, 15)` и `humidity ~ N(70, 10)` с округлением до
2 знаков; диапазоны не ограничены. Это синтетика, GPIO/I²C/датчиков нет.
Payload содержит два значения и локальный ISO timestamp без часового пояса.
Метаданные AAD — JSON со строковым `device_id` из `CLIENT_ID` и отдельным timestamp.
Числовые `DEVICE_ID`/`ALGORITHM_ID` объявлены, но не участвуют в пакете.

Ascon: случайный `os.urandom(16)` nonce; ключ 16 байт; фактический основной вызов
передаёт `Ascon-AEAD128`. Пакет JSON содержит base64 `nonce`, `associated_data`,
`ciphertext` (шифротекст вместе с тегом), строку `algorithm`. Тема —
`iot/sensors/device1`, client ID — `raspb1`; публикация QoS 1, loop в потоке.
Есть локальная расшифровка, но подтверждение доставки не ожидается и результат
publish не проверяется. Нет TLS, настройки логина и пароля, replay counter,
key ID, версии схемы, команд изменения профиля и политики смены ключей.
Дефолт `encrypt_data(..., variant="Ascon-128")` расходится с основным вызовом.

ARM64/Raspberry Pi OS: архитектурных привязок в генераторе не выявлено, но
совместимость не проверена. Нужны доступность NumPy/Paho, единый импорт Ascon,
подходящий Python и измерения на устройстве. Проверка здесь — Linux x86_64,
Python 3.14.9; ARM64 окружения нет. При включении инструментов KAT существующий
writer требует Python 3.12+. Не заявляется поддержка конкретного выпуска Pi OS.

## Receiver (`brocker`)

Paho подписывается на `iot/sensors/#` без проверки кода успешного соединения;
у subscribe не указан QoS, поэтому публикация QoS 1 не обеспечивает QoS 1 доставки
этому подписчику. Парсит AAD, вычисляет задержку **до** проверки тега,
затем вызывает `ascon_decrypt` с вариантом из входного пакета. Нет схемы/лимитов
размеров/base64 strict validation и проверки привязки device к topic.

Правила: температура >60 или влажность >70 → причина 0; иначе задержка >0.5 с
→ причина 1. К задержке вручную добавляются 3 часа. Это правила, ML не вызывается.
По имени тега ищется конфигурация устройства в MSSQL, добавляется запись Anomalies;
температура/влажность в БД этим модулем не сохраняются. Нет команды publisher,
Policy Engine или переключения алгоритмов. Соединение БД глобальное; после ошибки
подключения остаётся None; исключение в rollback может выйти из обработчика.
SQL строится f-string из сетевых метаданных; параметры дат/чисел требуют исправления.

## Classifier

Датасет: `DNN-EdgeIIoT-dataset.csv`, рекурсивный поиск в `/kaggle/input`.
CSV и сведения о версии/хеше датасета в проекте отсутствуют. В оригинальных
outputs видны сетевые поля ARP/ICMP/HTTP/DNS/TCP/MQTT/Modbus, а не температура
и влажность. Полная финальная схема признаков не сохранена.

Ячейки нумеруются здесь с 0, по порядку JSON:

| Ячейки | Действие |
|---|---|
| 0–1 | Импорты и загрузка CSV |
| 2–3 | Удаление 15 потенциальных flow-полей, строк с пропусками и дубликатов, просмотр |
| 4–5 | `Attack_label` (2 класса); LabelEncoder для `Attack_type` (15 классов); исключение обеих меток из X |
| 6 | get_dummies по 7 выбранным категориальным полям, to_numeric/coerce, fillna(0), преобразование в NumPy |
| 7 | Два stratified split 80/20, random_state=42 |
| 8–10 | RF: 50 деревьев, random_state=42, n_jobs=-1; fit/predict и оценка обеих задач |
| 11–12 | IF: 100 деревьев, contamination=auto, fit только по normal (y=0); predict +1/-1 переводится в 0/1 |

Метрики: accuracy, classification_report (precision/recall/F1/support), confusion
matrix с heatmap. StandardScaler импортирован, но не применяется. Преобразования
выполняются до split; нет отдельно обучаемого preprocessing pipeline,
временного/группового split, cross-validation, PR-AUC/ROC-AUC и анализа утечки
между связанными сетевыми наблюдениями.

Сохранение: `rf_model_15_class.pkl`, `rf_model_2_class.pkl`, `if_model.pkl`
через joblib.dump. Самих файлов нет. Загрузки joblib.load и online inference нет;
список/порядок dummy-колонок, encoder, preprocessing, версии библиотек и метаданные
модели не сохраняются. Прямого отображения сетевых признаков на MQTT-телеметрию нет.

Исторические outputs просмотрены в приватной копии, не воспроизведены:
RF 15 классов accuracy 98.2625%, RF 2 класса 100.0000%, IF 68.6714%.
IF attack precision/recall/F1: 0.46/0.63/0.53. Test support — 381935;
normal — 272800, attack — 109135. Это записи прошлого запуска с неизвестным
окружением, а не текущие доказанные результаты и не оценка реального канала IoT.
Outputs удалены из безопасной версии на этапе 0, исходники ячеек сохранены.

## Web: HTTP и авторизация

Flask-Login, session cookies, Werkzeug password hashes. Открытая регистрация
назначает viewer; вход проверяет is_active. WTForms формы имеют hidden_tag;
общего CSRFProtect для JSON API нет. `role_required` определён, но не используется.
Admin имеет все 13 таблиц и CRUD-права; operator — configuration/tags/logs/sensors,
создание и изменение; viewer — logs/sensors только чтение. Реального CREATE API нет.

| Метод / путь | Функция | Контроль / фактическое действие |
|---|---|---|
| GET, POST `/login` | login | Форма входа; небезопасный redirect next |
| GET, POST `/register` | register | Форма, создание viewer |
| GET `/logout` | logout | login_required, выход с побочным эффектом GET |
| GET `/` | index | login_required, dashboard |
| GET `/api/latest-data` | get_latest_data | login_required; память, при пустоте запрос MSSQL |
| GET `/tables` | tables_list | login_required; список по роли |
| GET `/table/<table_name>` | view_table | login + доступ к таблице; query.all(), без пагинации |
| GET `/debug/mqtt-status` | mqtt_status | login_required; состояние и параметры MQTT |
| PUT `/api/<table_name>/<record_id>` | update_record | login, доступ, can_update; generic setattr, commit, ошибочные логгеры |
| DELETE `/api/<table_name>/<record_id>` | delete_record | login, доступ, can_delete; commit, ошибочные логгеры |
| GET `/generate-test-data/<int:count>` | generate_test_data | login; генерирует значения, сохранение закомментировано; ответ ошибочно заявляет создание |

У методов GET Flask также неявно предоставляет HEAD/OPTIONS; таблица отражает
явные пользовательские действия. Все строки получены статически из декораторов,
не из успешно запущенного приложения.

## Web: БД и браузер

`models.py`: 14 моделей, включая Users, 13 остальных находятся в TABLES.
Явных ForeignKey/relationship нет; ниже связи отражают назначение полей, а не
доказанные ограничения реальной БД. DDL/дампа/миграций и справочных seed-данных нет.

| Модель / таблица | PK / основные ссылки по полям |
|---|---|
| User / Users | User_ID; unique Username/Email, hash, role, active |
| Algorithm / Algorithms | Algorithm_ID; Parameters_ID, Algorithm_Type_ID |
| AlgorithmType / Algorithm_Type | Algorithm_Type_ID |
| AlgorithmScheme / Algorithm_Scheme | Algorithm_Scheme_ID |
| Parameters / Parameters | (Parameters_ID, Algorithm_Type_ID); Algorithm_Scheme_ID |
| DeviceConfiguration / Device_Configuration | (Device_ID, Configuration_Update_Date); Algorithm_ID, Tag_ID |
| TagJournal / Tag_Journal | Tag_ID |
| LogJournal / Log_Journal | Record_ID; Log_Type_ID, Anomaly_ID |
| LogType / Log_Type | Log_Type_ID |
| Anomaly / Anomalies | Anomaly_ID; Anomaly_Cause_ID, Device_ID, Configuration_Update_Date |
| AnomalyCause / Anomaly_Causes | Anomaly_Cause_ID |
| GlobalReport / Global_Reports | (Creation_Date, Report_ID); Report_Type_ID, Record_ID |
| ReportType / Report_Types | Report_Type_ID |
| SensorData / Sensor_Data | Record_ID; Numeric(5,2) Temperature/Humidity |

Web поднимает собственный Paho-клиент только при запуске `app.py` как main,
подписывается и дешифрует, хранит последние 50 точек в памяти процесса и emit
`sensor_update` всем подключениям Socket.IO. Сохранение из on_message отключено;
сама save_sensor_data не добавляет SensorData в сессию и не делает commit.
История читается join LogJournal/SensorData, а не из receiver.
При импорте через WSGI клиент MQTT не запускается; несколько процессов также
не разделяют latest_data. Socket.IO connect-авторизация не реализована, CORS `*`.

Bootstrap 5.3.0, Socket.IO client 4.5.4, Chart.js 4.4.0, Bootstrap Icons 1.10.0
загружаются с CDN. Активный dashboard JS встроен в HTML; static/js/dashboard.js
не подключён и имеет отдельную ошибку замены ссылок на массивы исторических данных.
Индикатор MQTT изначально online, updateStatus не вызывается. Табличный UI
использует JSON fetch, но POST отсутствует, а составной PK сводится к одному ID.
Адаптивная сетка/таблицы есть; браузерная проверка не выполнялась.

## Ascon: происхождение и границы проверки

Локальный remote: `https://github.com/meichlseder/pyascon.git`, HEAD `ed24e54`,
ветка master. LICENSE — CC0 1.0 Universal. Это источник происхождения по локальным
Git/README; независимая сверка всех файлов с удалённым commit не проводилась.
Лицензия остальных авторских компонентов проекта не объявлена.

В коде AEAD поддерживается только `Ascon-AEAD128`: key/nonce/tag по 16 байт,
rate 16 байт, 12 раундов init/final, 8 промежуточных, little-endian кодирование,
padding 0x01. Также есть Hash256/XOF128/CXOF128 и нестандартные MAC/PRF варианты.
Ascon-128/128a/80pq в этой версии AEAD не поддерживаются, вопреки legacy default
publisher. Receiver и web используют vendored `ascon.ascon`; publisher импортирует
внешний `pyascon.ascon`, которого нет в дереве/окружении и dependencies.
Исходные ключи трёх компонентов совпадали; это не доказывает совместимость импортов.

Финальный [NIST SP 800-232](https://csrc.nist.gov/pubs/sp/800/232/final), опубликованный
13.08.2025, задаёт Ascon-AEAD128 и три hash/XOF функции. Локальный README ссылается
на initial public draft. Название, параметры и структура реализации согласуются
с ожидаемым направлением стандарта, но соответствие финальному документу **не
подтверждено независимыми эталонными векторами**. Полного формального аудита нет.

Готовых эталонных файлов в дереве нет. genkat генерирует 33×33 AEAD примера той же
реализацией и сверяет round trip. В ходе инвентаризации проверены 81 сочетание
длин PT/AAD из {0,1,7,8,15,16,17,31,32}, длина ciphertext+tag и отказы при замене
тега, AAD, key, nonce; проверки успешны. writer/genkat импортируются в Python 3.14.9;
полный генератор не запускался. Эти проверки не доказывают нормативное соответствие,
constant-time поведение, производительность ARM64 или безопасность протокола.
Обычное сравнение тега, assert валидация и pure Python требуют отдельной оценки.

## Зависимости и возможности проверки

Заявлено в web requirements: Flask 3.0.0; Flask-MQTT 1.1.1 (прямо не используется);
Flask-SocketIO 5.3.5; Flask-SQLAlchemy 3.1.1; Flask-Login 0.6.3;
Flask-WTF 1.2.1; WTForms 3.1.1; pymssql 2.2.11; python-socketio 5.10.0;
eventlet 0.33.3; werkzeug 3.0.1. SQLAlchemy/Jinja2 поступают транзитивно;
прямой paho-mqtt не зафиксирован. WTForms Email требует email-validator,
который явно не указан. Отдельных requirements publisher/receiver/classifier нет.
Notebook требует pandas, numpy, scikit-learn, matplotlib, seaborn, joblib и Jupyter.
Ascon использует стандартную библиотеку Python.

Сейчас в Python 3.14.9 не установлены перечисленные web/MQTT/ML зависимости,
включая NumPy, Paho, pyascon, email-validator. Пакеты не устанавливались.
Flask, MQTT, MSSQL и обучение не запускались; сетевые подключения к исходным
адресам не выполнялись. Синтаксис 9 .py и 13 ячеек проверен compile() без запуска
приложения. Работоспособность сервисов, API и браузера остаётся непроверенной.
