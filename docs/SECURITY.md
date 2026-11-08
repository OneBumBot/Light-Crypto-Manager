# Этап 4: защищённый контур (в работе)

Ветка: feature/security-hardening от 5be5444. Этап 5 не начат.

## Транспорт

По умолчанию Mosquitto слушает только TLS/8883, требует пароль и ACL. CA/server
сертификаты генерируются локально, с SAN broker/localhost/127.0.0.1. Для будущего
Pi добавьте DNS/IP брокера при генерации, установите доверенный ca.crt на Pi и
задайте MQTT_HOST/PORT/CA_FILE/USERNAME/PASSWORD_FILE; publisher менять не нужно.
Hostname verification не отключается. Минимальный TLS — 1.2.

```bash
python3 scripts/prepare_security.py --directory .local-runtime/security
python3 scripts/prepare_compose.py
# .env.compose: MQTT_SECURITY_DIR=.local-runtime/security
# Выполнять из корня репозитория.
docker compose --env-file .env.compose --profile demo --profile web up --build -d --wait
```

Родительский .local-runtime должен быть приватным (0700). Генератор отказывается
перезаписывать существующий каталог. Все сгенерированные файлы имеют 0600, каталог
0700. Сертификаты тестовые, срок 30 дней; CA private key остаётся только на хосте.
Пароли передаются mosquitto_passwd через stdin, не аргументами процесса.

security-init копирует файлы в отдельные volumes с UID 1883 (broker) и 10001
(клиенты). Обычные приложения не видят чужие пароли; publisher/smoke имеют ключи
только своего устройства, receiver/web — разрешённых устройств. Тестовый сервис
получает тестовые credentials для негативных проверок. Изображения не содержат
секретных материалов. PostgreSQL по-прежнему не публикуется на хост.

ACL: publisher пишет только iot/sensors/raspb1, receiver/web читают raspb1 и smoke,
smoke пишет только свой topic, monitor публикует только lightcrypto/health.
Healthcheck broker использует приватный options file, не пароль в командной строке.
Клиентский plaintext режим возможен только при одновременно APP_ENV=test и
MQTT_INSECURE_TEST_MODE=1; Compose не содержит plaintext listener/override.

Очищенные протоколы с командами/кодами завершения: docs/reports/stage4-*.txt.
Формат и anti-replay, затем web-защита — следующие блоки текущего этапа.
