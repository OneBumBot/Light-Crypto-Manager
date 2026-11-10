# Software IoT Device Control Agent

src/device_control/agent.py — настоящий publisher + обработчик команд, не
AckSimulator. Подключается к собственному MQTT/TLS broker, получает boot grant,
обрабатывает аутентифицированные PREPARE/ACTIVATE, сохраняет SQLite state и
вызывает общий telemetry encoder с действующим профилем. Существующий legacy
publisher сохраняет Ascon; для live switches запускается новый agent.

PREPARE проверяет capabilities/key reference, сохраняет prepared, но active
profile не меняет. ACTIVATE требует того же transition/correlation/profile/key,
атомарно меняет active profile и сохраняет ответ/command replay identity до ACK.
Повтор идентичной команды возвращает прежние bytes ACK, без повторного применения.
Конфликт того же sequence/UUID с другим digest отвергается.

SQLite FULL synchronous + BEGIN IMMEDIATE, private0600 и process lock. Installer
не сбрасывает существующий ledger; если после установки device.db исчез — отказ,
а не повторная инициализация. Инициализация допустима только при fresh provisioning.
Nonce ranges не восстанавливаются из файла в память после запуска, нужен новый
challenge-bound grant. Временный отказ controller не блокирует уже выданный range;
при исчерпании/новом boot без controller — fail closed. Queue ограничена 128.

Verified on software IoT device agent в Docker/x86_64. Raspberry Pi/ARM, физические
сенсоры, secure element и восстановление snapshot всей работающей VM не проверены.
Fault injection drop ACK/delay READY доступен только при APP_ENV=test и bounded
параметрах, не включён по умолчанию. SIGINT/SIGTERM завершают loop и освобождают lock.
