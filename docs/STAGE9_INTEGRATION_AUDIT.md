# Stage 9 — аудит интеграции

Baseline d3cd219e39c719c6a53db057c58635f2b0410a8d, clean tree,
feature/adaptive-crypto-control-fix → feature/system-integration-demo.
Миграции 0001–0008, последний head 0008_control_evidence. Криптопротоколы сохраняются.

| User action | Existing endpoint | Authoritative source | Current limitation | Required integration |
|---|---|---|---|---|
| Открыть мониторинг | /, /api/latest-data | process-local web buffer / legacy Sensor_Data | смешаны identities, green indicator по умолчанию, память не admission authority | заменить dashboard PG-backed device snapshot |
| Читать историю | /telemetry, /api/telemetry/history | Mongo measurements | таблица без графика/карточки; failure уже 503 | переиспользовать bounded device filter/UTC/offset |
| Оценить storage | /api/telemetry/metrics | PG metrics/outbox + Mongo count | единый 503 при Mongo outage; только admin | независимые component semantics в read-only adapter |
| Читать Policy | /policy, /api/policy | policy_device_states/version/worker heartbeat | большие JSON, configured_profile не effective | карточки risk/DRY_RUN/freshness; отдельная recommendation |
| Читать причины | /api/policy/decisions, /signals, /transitions, /intents | PG decisions/signals/audit | нет общего device timeline | bounded rows с identity/версией; сохранять исходные диагностические APIs |
| Policy metrics | /api/policy/metrics | PG policy records | admin, отдельная страница | ссылаться как расширенная диагностика |
| Читать ML | /ml, /api/ml/status, /api/ml/events | PG model registry/results | score без общего device context | RESEARCH/DEMO, false trust, absent != normal |
| Выбрать профиль | /control, /api/control | live_control_devices + transitions + receipts | textbox identity, большой JSON, нет confirmation UX | verified inventory/capability picker, явное подтверждение |
| Авторизовать | POST /api/control/<device>/switch | PG durable request → worker | RBAC/CSRF есть, 202 не completion | переиспользовать без publish во Flask |
| Восстановить unknown | POST /api/control/<device>/reconcile | существующий bounded server logic | admin action не объяснён, не repair PREPARE-only | guarded confirmation + recovery guide |
| Проследить команду | /api/control | PG commands/ACK/audit/evidence | смешаны delivery/ACK/effective, ACK body сырой | allowlisted timeline без wire/body/keys |
| Проверить transport | /debug/mqtt-status | web MQTT client | не receiver status | PG diagnostic receiver SUBACK heartbeat (не MQTT presence) |
| Проверить worker | /api/control, /api/policy | PG heartbeat | stale flags есть, не сводятся | каждый worker отдельно, age и TTL |
| Редактировать SQL | /tables, /api/<table>/<id> | legacy ORM | не UX устройств | сохранить admin tooling, не основной device control |

Новый API нужен для согласованного bounded PG snapshot inventory/latest admission/
security/Policy/worker status без N+1 и без выдачи raw authenticated control bodies.
История и mutating control endpoints переиспользуются. Snapshot не новая authority,
не копия effective, не Policy→command pipeline. Mongo проверяется отдельно от PG.

Границы: stale telemetry не presence; ACK не effective; expired transition не успех;
Policy configured_profile не verified; rejected без identity не привязывается к
устройству; replay observation не доказанная атака; физическая аномалия не IDS.
При ошибке PG UI инвалидирует старый snapshot, а не продолжает показывать его fresh.
Все новые read routes требуют sensor_data access; control сохраняет admin+CSRF.
