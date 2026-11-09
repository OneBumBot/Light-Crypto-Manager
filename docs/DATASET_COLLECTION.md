# Воспроизведение сбора MQTT/TLS

Нужны Docker/Compose с поддержкой `!reset`, Python3.12 и существующее ML/dev venv.
Никакие датасеты/модели не загружаются в image. Сначала проверьте свободное место
(`df -h .`) и нагрузку (`uptime`). На рабочем сервере предпочтите отдельную VM.

```bash
python3 scripts/prepare_research_stand.py --directory .local-runtime/new75b --project lcm-stage7b-example
export COMPOSE_FILE=compose.yaml:compose.research.yaml
LAB_ENV=.local-runtime/new75b/compose.env
docker compose --env-file "$LAB_ENV" --profile research build receiver tests research-init
docker compose --env-file "$LAB_ENV" --profile research up -d --wait --wait-timeout 180 mongo outbox-relay web policy-worker traffic-collector
.venv/bin/python -m src.research_stand.orchestrator --env-file "$LAB_ENV" --output .local-runtime/new75b/pilot --matrix pilot --prefix pilot-first
.venv/bin/python -m src.research_stand.dataset build --root .local-runtime/new75b/pilot --output .local-runtime/new75b/pilot-dataset
.venv/bin/python -m src.research_stand.dataset validate --root .local-runtime/new75b/pilot-dataset --captures .local-runtime/new75b/pilot
```

`research-provision` регистрирует ключевые эпохи/ACL identities в новой PG; после
этого research-init выдаёт только scoped generator credentials. Не пропускайте
эту зависимость: успешное TLS-подключение не доказывает принятие telemetry.
Дополнительный Policy Worker DRY_RUN — только в этом же исследовательском проекте.
ML worker по умолчанию не включается. Стенд не использует рабочие приложения.

После ручной проверки пилота:

```bash
.venv/bin/python -m src.research_stand.orchestrator --env-file "$LAB_ENV" --output .local-runtime/new75b/primary --matrix primary --prefix primary-first
.venv/bin/python -m src.research_stand.dataset build --root .local-runtime/new75b/primary --output .local-runtime/new75b/dataset
.venv/bin/python -m src.classifier.research.cli plan --data .local-runtime/new75b/dataset/dataset.csv --manifest .local-runtime/new75b/dataset/dataset.manifest.json --config configs/ml/research75.json --output .local-runtime/new75b/plan.json
```

Только plan; train/test/automatic model install не вызываются. Повторяемость —
параметры/seed/версии/границы, не byte-identical PCAP: nonce, TCP scheduling,
client UUID и время намеренно новые. Сохраняйте immutable plan и его SHA, не
переименовывайте один capture ради увеличения числа групп.

## Пределы и остановка

- Config2..24 clients; duration3..20s; base interval0.15..2s; jitter0..0.2s;
  base aggregate≤120/s. Normal publish limiter≤120/s; отдельный QoS retry bounded
  одним повтором на client; максимум80 итераций/client, менее2000 сообщений/run.
- TCP startup stagger0.09s; все сценарии ограничены одной лабораторной целью,
  max24 concurrent clients, max48 connections обычного matrix run. Не brute force.
- Generator/collector:1CPU/256MiB каждый; broker0.5CPU/128MiB; PG1CPU/512MiB,
  Mongo1CPU/768MiB с WiredTiger cache0.25GiB; relay/receiver1CPU/256MiB;
  web0.5CPU/256MiB; Policy0.5CPU/192MiB. Docker OOM/failure прекращает эксперимент.
- tcpdump≤20000 packets, PCAP≈8MiB/run с polling50ms, capture≤30s; pcap limit
  может превышаться на один небольшой polling interval, это не filesystem quota.
- Host free floor2GiB перед run/1GiB во время; capture stops below512MiB;
  research host output≤512MiB. Через2s проверяются physical research volumes:
  PG≤1GiB, Mongo≤1GiB, research-data≤512MiB. Превышение/collector exit останавливает
  generator. Это watchdog budgets, **не жёсткие квоты файловой системы**. Нужны
  dedicated filesystem/VM hard disk quota для гарантии против внешнего disk fill.
- Проверка load average≤max(4,0.75×host CPUs) перед/во время; CPU/RAM Docker quotas
  действуют независимо. Логи rotated4MiB×2 на основные сервисы. Images/предыдущие
  volumes не входят в budget эксперимента; их не удаляют автоматически.

Стандартная остановка, без удаления данных:

```bash
docker compose --env-file "$LAB_ENV" --profile research --profile policy --profile web down
```

Все PCAP/CSV/manifests находятся в private volume и host directory700/files600,
вне Git. SQLite counters остаются отдельно. Автоматического retention нет.
Для удаления только завершённых выбранных host captures предусмотрен
`python -m src.research_stand.retention` (по умолчанию preview), см. --help.
Docker volumes намеренно сохраняются; их удаление — отдельное ручное действие
после backup/проверки имён. Не используйте down -v для очистки рабочего контура.
