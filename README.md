# LightCrypto Manager

Дипломная система защищённой IoT telemetry и ручного адаптивного управления двумя
AEAD: **Ascon-AEAD128** и **AES-128-GCM**. MQTT/TLS + ACL, PostgreSQL authoritative
admission/replay/Outbox, MongoDB history, Flask dashboard, durable HMAC control,
настоящие software Device Agents и подтверждение effective новой AEAD telemetry.

**Policy DRY_RUN. RF/IF RESEARCH/DEMO, trusted_detector=false.** Нет доверенного live
network IDS и автоматического выбора алгоритма по ML. Профили не ранжируются по
условной «силе»; physical Raspberry Pi/production deployment ещё не проверены.

## Проверка производительности — этап 10

Изолированные software-стенды 3/10/25/50 устройств, реальные MQTT/TLS/PG/Mongo
измерения и recovery: [результаты](docs/STAGE10_RESULTS.md),
[запуск и методика](docs/STAGE10_LOAD_TEST_PLAN.md),
[узкие места](docs/STAGE10_BOTTLENECK_ANALYSIS.md).
На 50 устройствах проверен telemetry path около 99,38 сообщения/с за 5 минут;
это не максимальная вместимость: Policy при 25×2 Гц уже отстаёт.
Итоговая регрессия — 739 passed, 0 skipped; это не доказательство качества IDS.

[Проект интеграции ГОСТ](docs/RUSSIAN_CRYPTO_INTEGRATION_DESIGN.md) и
[план сравнения реализаций](docs/CRYPTO_PROFILE_COMPARATIVE_EXPERIMENT_PLAN.md)
подготовлены для этапа 11. Кузнечик/Магма не включены в рабочие профили.

## Локальная демонстрация

```bash
uv sync --frozen --group dev
.venv/bin/python -m scripts.prepare_stage9_demo \
  --directory /tmp/lcm-stage9-demo-example --project lcm-stage9-demo-example
.venv/bin/python -m scripts.run_stage9_demo \
  --directory /tmp/lcm-stage9-demo-example start --build
```

Нужны Docker Compose, Python 3.12–3.14, uv и OpenSSL. Runner выводит loopback URL.
Три случайных account passwords остаются в приватном `accounts/*.password` (0600),
не в README/images/logs. Имена: demo-admin/demo-operator/demo-viewer. В браузере:
мониторинг → alpha → target → явное подтверждение → настоящие PREPARE/ACTIVATE/ACK
→ новая telemetry → EFFECTIVE_CONFIRMED. Beta/gamma независимы, gamma Ascon-only.

```bash
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example stop
.venv/bin/python -m scripts.run_stage9_demo --directory /tmp/lcm-stage9-demo-example start
```

Stop/resume сохраняют nonce/command authority и keys. Не удалять SQLite/SQL volumes,
не использовать `down -v` и не переинициализировать старую identity. Для нового
независимого стенда выбрать новый suffix и новые keys.

[Полная инструкция запуска и защиты](docs/STAGE9_DEMO_RUNBOOK.md) ·
[Руководство пользователя](docs/STAGE9_USER_GUIDE.md) ·
[Архитектура](docs/STAGE9_SYSTEM_ARCHITECTURE.md) ·
[Фактические результаты](docs/STAGE9_RESULTS.md) ·
[Матрица E2E](docs/STAGE9_E2E_TEST_MATRIX.md) ·
[Recovery](docs/CONTROL_RECOVERY.md) · [Security](docs/SECURITY.md).

Исторические исследования, PCAP, модели/frozen plans и отчёты прежних этапов
сохраняются. Число прошедших тестов — не доказательство качества IDS.
