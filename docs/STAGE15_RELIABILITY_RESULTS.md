# Stage15 — надёжность и отказоустойчивость

Все fault runs отделены от успешной performance-матрицы; raw evidence и failed attempts сохранены. Источник основных 12 cases: `dd3d15a7b141918188214a25af74f6d3ba97cff3`. Дополнительные OOM, JSON/freshness/session guards имеют собственные команды и source hashes в reports.

| Проверка | Реальное наблюдение | Ограничение |
|---|---|---|
| Observer SIGKILL/restart | Receiver продолжает admission; новая mid-session capture не получает полный контекст | Убитый процесс не может записать final kernel statistics; unknown не заменяется нулём |
| Model worker SIGKILL/restart | Durable pending продолжаются без duplicate results | Restart не сбрасывает capture/nonce authority |
| Missing artifact / wrong hash / wrong feature version | MODEL_UNAVAILABLE, null score | Никакой fallback модели или score=0 |
| Receiver restart | 89 PG/Mongo records; ошибочный clock/context явно unavailable | Не все TCP packets обязаны быть scored |
| PostgreSQL outage | После восстановления 90 PG/Mongo, Outbox drain=0 | Неподтверждённый commit не объявляется accepted |
| MongoDB outage | 91 PG/Mongo после drain, Outbox=0 | Delivery во время outage не выдумывается |
| Broker outage | 17 PG/Mongo; генератор может остановиться | Нельзя заявлять lossless continuous producer recovery |
| Queue capacity=1 | CAPTURE_INCOMPLETE, reader drops=279, queue overflow=44, kernel drops=0 | Основная telemetry: 90 PG/Mongo; неполный источник не является verified Normal |
| Disk floor | Отдельный tmpfs 1 MiB блокирует preflight, exit 1 | Host disk не заполнялся |
| Memory cap 16 MiB | Успешное завершение, OOM не было | Не засчитано как kill |
| Memory cap 6 MiB, отдельный опыт | Настоящий OOMKilled=true/exit 137; ещё 36 PG/Mongo, Outbox=0 | Final capture stats отсутствуют; raw evidence сохранено |

[12 fault cases](reports/stage15/recovery.json), [настоящий OOM](reports/stage15/memory-exhaustion.json). Все ключи, broker/receiver/PG/Mongo state отделены от этапов 8–14. После экспериментов Stage15 сервисы остановлены без удаления контейнеров или volumes.

## Дефекты, найденные во время работы

Первый model image импортировал offline experiment helper, которому требовался отсутствующий Research Stand. Получены INFERENCE_ERROR/null, не ложный Normal. Серия остановлена. Исправление: узкая scoring formula без training/oracle imports. 128 новых packet vectors × 4 модели дали 512 exact comparisons, maximum difference=0.

Первый 25-device RF run выявил SQLite busy и падение worker: 2544 physical packets, kernel drops=0, application overflow=1767. Это failed CAPTURE_INCOMPLETE run. Точные 697 telemetry identities независимо доставлены в PG/Mongo. Исправлены atomic batch до 64 results, BEGIN IMMEDIATE и bounded retry; rollback не оставляет partial results/processing markers/session counters. Новая успешная 48-run серия измерена отдельно при прежних ресурсах.

Последующие guards отклоняют unhashable JSON types, неправильный порядок timestamps и SYN, отсутствие evidence freshness. Session finalization требует наблюдённого SYN и двустороннего FIN либо RST; окончание capture не выдаётся за конец полного TCP соединения. Синтетические malformed Ethernet/truncation/IPv6/fragments/gaps fixtures проверяют код, а не качество IDS.

## Поведенческие и browser проверки

31/31 мутация обнаружена assertion failures по поведению: missing timestamp→0, отрицательная delta, shared/reused flow state, lost SYN/sequence gap, truncated packet scoring, feature order/version, unauthorized model/threshold mutation, metadata predictor, invalid/missing score→Normal, fake device binding, duplicate insert, coupling к receiver, Policy/Control writes, ложный healthy/drop/freshness, holdout retuning, future-packet aggregation, partial batch rollback и SQLite busy. SyntaxError/ImportError не засчитаны. [Полные результаты](reports/stage15/mutations-final-release.json).

Настоящий Chromium: read-only viewer, 25 rows, score/identity display, POST denied, literal XSS strings, no-store, source expiry и очистка snapshot при реальном PG outage; JavaScript errors=0. Отдельная legacy DOM-XSS проверка сохранила прежние assertions для tables/ML/Policy. Её fixture дополнили уже существующими Stage13 diagnostics/DOM fields; Policy JavaScript и FSM не изменялись.

Финальный pytest на реальных изолированных PG/Mongo: **1049 passed, 0 skipped, 56.64 s, exit 0**. [Команда и исходный SHA](reports/stage15/final-regression.commands.json), [полный вывод](reports/stage15/final-regression.txt). Старые 967 тестов сохранены.

Нет Shadow→Policy/ML feed/Control пути и нет credentials для его выполнения. Финальные live commands/transitions, ML registry installations и Policy signals в новом online realm равны нулю. Основные crypto/control/Policy/oracle files byte-equal baseline; [security audit](reports/stage15/security-release.json). Это не замена отдельного physical IoT, independent-domain или production security audit.
