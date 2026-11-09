# Этап 7.5 — выполненные проверки и научные ограничения

Исходный c9250d8, ветка feature/ml-research-improvement. Все fault tests используют
новый Compose project lcm-stage75 с собственными volumes/секретами. Старые working
volumes не использованы. ML smoke использует прежний private stage6 DEMO artifact,
не новую Network модель и не новые telemetry данные.

## Итог

- 267 pytest passed in27.24s, без skips/warnings.255 предыдущих и12 новых тестов.
- 12 новых unit tests обучают только synthetic fixtures; их model metrics не
  публикуются как исследование реальных атак.
- Real import14501 observations; strict real plan отклонён. Новых real models0,
  новых scientific validation/final/external scores нет.
- 13 baseline file hashes совпали, old stage6 reports/5 artifacts сохранены.

## Матрица25 требований

| Сценарий | Фактическое доказательство |
|---|---|
| Dataset schema/provenance/hash/class mapping/missing field | test_import_provenance_granularity_mapping_and_missing |
| Packet vs flow incompatibility | test_flow_manifest_and_policy_schema_are_closed; import granularity guard |
| Duplicate/capture/session isolation и deterministic seed | test_group_split_determinism_capture_session_and_duplicate_guards |
| No label/provenance features, train-only balancing | test_balancing_is_train_only_and_provenance_cannot_be_predictive |
| Train-only imputer/scaler / invalid NaN/Infinity/types | test_schema_nonfinite_types_and_missing_imputed_on_train_only |
| IF fit only normal /3 scaling paths | test_if_only_normal_training_scaling_variants |
| Frozen threshold, artifact/hash/version/restart/test once | test_freeze_artifacts_once_only_test_and_offline_inference |
| Modified plan/candidate resource bounds | test_modified_plan_rejected_and_candidate_resource_limits |
| Unknown multiclass type/per-attack IF never fit attack | test_unknown_multiclass_attack_is_reported_not_invented |
| Empty test class/score bounds/cluster uncertainty | test_operating_point_empty_class_scores_and_group_uncertainty |
| Audited packet labels preserve normal background | test_audited_packet_labels_preserve_normal_background |
| Network model forbidden in telemetry worker | test_new_network_model_is_forbidden_in_online_telemetry_worker |
| New schema rejected by Policy allowlist / Ascon only | test_flow_manifest_and_policy_schema_are_closed + unchanged previous tests |
| TLS/password/CA/ACL negatives | stage75-security.txt |
| Anti-replay/multi-device/PG+Mongo rollback/restart/crash-after-write | stage75-storage.txt + full previous tests |
| ML model unavailable/reload/dedupe/Mongo recovery | stage75-ml.txt |
| Policy two workers/restart/PG outage/readiness/victim binding | stage75-policy.txt |
| Flask roles/CSRF/Socket.IO/safe redirects/live policy views | stage75-web.txt |
| Browser XSS regression | stage75-browser.txt, actual Chromium12 payload checks |
| All tests0–7 | stage75-final.txt,267 passed |

## Команды реального research audit

```bash
.venv/bin/python -m scripts.diagnose_rf75 --data .local-runtime/edge-research/network-grouped-v2.csv --models .local-runtime/stage6-network-models --output /private/diagnosis.json
.venv/bin/python -m scripts.audit_mqttset75 --directory .local-runtime/research75 --output /private/source-audit.json
.venv/bin/python -m scripts.benchmark_baseline75 --data .local-runtime/edge-research/network-grouped-v2.csv --models .local-runtime/stage6-network-models --output /private/cost.json
```

Фактические output filenames/команды/exit codes — stage75-baseline.txt,
stage75-access.txt, stage75-real-data.txt, stage75-cost.txt. Output paths immutable:
для повторной диагностики задайте новый путь, не перезаписывайте baseline.

Real plan error: Insufficient independent captures per class {'0':0,'1':1}, exit2.
Это ожидаемый методический отказ, не успешное обучение. Reduced не имеет нужных
fields и provenance. Public IEEE page HTTP200 с CC BY4.0 не равна разрешённому
anonymous download; download UI login/subscription не обходился.

## Команды регрессий

```bash
docker compose --env-file .local-runtime/stage75.env run --rm --no-deps tests
python3 scripts/check_policy_system.py --env-file .local-runtime/stage75.env
python3 scripts/check_dual_database.py --env-file .local-runtime/stage75.env
python3 scripts/check_ml_system.py --env-file .local-runtime/stage75.env
```

Повтор ML smoke с уже установленной immutable моделью требует
--reuse-installed-model. При первом запуске проверялось отсутствие model artifact.
Контур и secrets надо подготовить как в COMPOSE.md; env/keys/models не в Git.

## Промежуточные неуспехи

Вспомогательные hash проверки в system Python не находили joblib; использована
существующая .venv, без изменения зависимостей. Первый запуск diagnose script как
filepath не находил src; правильный module
запуск python -m scripts.diagnose_rf75 прошёл. Первый unit run7 passed/1 failed:
ошибочное предположение fixture о50/50 в первых100 строках; фактически48/52,
assert теперь сравнивает реальные train counts, без изменения алгоритма/данных.
Real plan дважды отклонён ожидаемо; отказ не замаскирован random-row fallback.
Данные/thresholds не подгонялись для успешного отчёта. Buildx отсутствует, classic
Docker builder успешен; это не ARM64 build verification.

## Научный статус и необходимые данные

Нужны независимые normal/attack captures, audited labels (background normal!),
сохранённые stream/packet/time metadata и untouched final holdout. Условия/хэши
локально предоставленных2020 архивов тоже нужны. Схемы/link layer/единицы должны
совпадать; flows и packets не смешиваются. Новые quality metrics отсутствуют,
ниже их не заменяют paper scores, synthetic tests или old validation cost.

Сводная таблица диплома — ../ML_RF_IF_BENCHMARK.md. Новые packet models остаются
offline research, trusted_detector=false. Текущая система не получила нового
collector, live Network IDS, control channel, FastAPI или криптопримитива.

После проверок lcm-stage75 остановлен без удаления volumes:
[stage75-shutdown.txt](stage75-shutdown.txt). Секреты, исходные datasets и прежние
модели сохранены локально, не в Git/образах. Полный список файлов —
[stage75-files.txt](stage75-files.txt).
