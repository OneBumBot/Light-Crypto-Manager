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

## Этап11: Kuznyechik-MGM в изолированном software lab

Добавлен настоящий третий AEAD: pinned Go Kuznyechik/MGM, RFC7801/RFC9058 KAT, independent cross-check, per-key budget и подтверждение переключения по PostgreSQL AEAD receipts. Обычные deployments сохраняют Ascon/AES live eligibility; MGM требует отдельной явной test-lab authorization и provisioned ключей/capabilities. Timing resistance/ARM/сертификация не заявляются. Policy остаётся DRY_RUN, RF/IF untrusted.

Запуск и остановка, приватные аккаунты и сохранение state: [STAGE11_RESULTS](docs/STAGE11_RESULTS.md). Подробности: [provider](docs/STAGE11_PROVIDER_SELECTION.md), [nonce/budget](docs/KUZNYECHIK_NONCE_AND_KEY_BUDGET.md), [verification matrix](docs/STAGE11_INTEGRATION_TESTS.md).

## Этап 12: сравнение реализаций и ограниченный Kuznyechik worker

Для лаборатории добавлен bounded local Go worker без сетевого порта; профиль и wire protocol не зависят от backend. Default — one-shot, выбор worker явный (`LCM_KUZ_BACKEND=persistent`), без fallback. Итоговая регрессия: **882 passed, 0 skipped**. Это не доказательство constant-time или качества IDS.

Magma-MGM исследована по RFC и публичным векторам, но **не допускается к continuous telemetry/live control**: короткий budget 64-битного блока несовместим с текущим lease и отсутствующим rekey lifecycle. В UI остаются три прежних профиля. Kuznyechik сохраняет lab-only; side-channel зависимость MGM не объявлена устранённой. Policy DRY_RUN, ML untrusted.

[Результаты, ограничения и графики](docs/STAGE12_RESULTS.md) · [Запуск/stop/resume](docs/STAGE12_SYSTEM_INTEGRATION.md) · [Команды и отчёты](docs/reports/stage12/COMMANDS.md) · [Magma budget](docs/MAGMA_MGM_SECURITY_BUDGET.md). Все Stage12 контейнеры после экспериментов остановлены, ключи и volumes сохранены.

## Этап13: Policy throughput и порядок событий

Indexed durable pending queue и bounded atomic batches сохраняют FSM, late events, version isolation, идемпотентность и DRY_RUN. Readiness worker теперь отделена от свежести evidence/очереди. На software-стенде проверены3/10/25/50 устройств, три независимых25-device repeats и15-минутная стабильность; подробные ограничения и фактические числа: [STAGE13_RESULTS](docs/STAGE13_RESULTS.md). [Воспроизведение/stop/resume](docs/STAGE13_POLICY_THROUGHPUT_DESIGN.md), [ordering](docs/STAGE13_EVENT_ORDERING_CONTRACT.md), [SQL](docs/STAGE13_SQL_OPTIMIZATION.md). ML остаётся untrusted, управление криптографией manual-only; новых алгоритмов нет.
