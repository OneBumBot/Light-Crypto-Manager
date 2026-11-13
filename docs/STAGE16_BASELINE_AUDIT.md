# Stage16 — исходный аудит

Исходная ветка feature/online-shadow-ids-validation, чистый HEAD b2317f94b9198b6300d49d9e5effd11a7efee298. Новая ветка feature/final-integration-stabilization. Main не изменяется; push/merge/rebase не разрешены. Before preservation: 1533 защищённых tracked paths и 6080 private artifacts, старые Docker projects/volumes зафиксированы. Это не побайтовый snapshot SQL volumes.

Прочитаны Stage9 demo/runbook/user guide, Stage10–15 results, Compose base/control/research/shadow и существующие provisioning/control/receiver/Policy contracts. Alembic head — 0011_policy_throughput. Critical source hashes и все старые миграции зафиксированы в reports/stage16/critical-source-baseline.json.

Первый baseline упёрся в исчерпанный автоматический Docker address pool. Старые сети не удалялись. Повтор на явной непересекающейся 10.216.1.0/24: **1049 passed, 0 skipped, 53.91s, exit0**, отдельные свежие PostgreSQL/MongoDB. Первый failure и последующие команды сохранены раздельно. Хост: Linux x86_64, Python3.12.16, Docker Compose5.6.1, около31GiB RAM; фактические свободные ресурсы — preflight.json.

Stage9 уже содержит настоящий трёхагентный TLS/HMAC/AEAD demo. Новый runner переиспользует его provisioning, Compose, setup и control path. Не переписываются crypto providers, Policy FSM или ML. Добавляются только Stage16 lifecycle/preflight/evidence guards, явная подсеть, единый smoke и финальная документация.

Основной контур: broker, три Device Agent процесса, receiver, PG, Mongo, relay, web, control-worker, policy-worker DRY_RUN. Учётные записи admin/operator/viewer независимы, passwords приватные. Ключи новые, Gamma Ascon-only. Readiness требует новых PG/Mongo identities после каждого start/resume. Stop сохраняет state; resume не запускает первоначальный setup заново. Missing/replaced used volume, SQLite или setup marker должны блокировать старт.

Kuznyechik не включается в Stage16 namespace: существующий release gate оставлен без изменений, отдельные Stage11/12 labs документируются отдельно. Magma отсутствует в live control. Shadow — OPTIONAL_RESEARCH_DEMO_UNAVAILABLE в основном demo: отдельный capture namespace/parity/model scope требует существующего Stage15 research stand. Основной запуск не зависит от моделей; fake inference не добавляется.
