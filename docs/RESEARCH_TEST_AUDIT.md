# Аудит тестов 7.5b-fix

Baseline3282557, ветка feature/mqtt-tls-ground-truth-hardening. Старые301passed
подтверждают выполненные assertions, не достоверность разметки/качество IDS.
До изменения кода проведён реальный negative experiment: в копии обоих CSV normal
поменян на violation, hashes/class_counts обновлены; validate(raw_root) **принял**.
Доказательство: reports/stage75b-fix-baseline-defect.json. Архив не изменялся.

| Проверки | Подмена зависимостей / реальные эффекты | Может пройти при дефекте / что должно падать | Научный вывод |
|---|---|---|---|
| bounds, matrix paired/unique | synthetic config, без сети | Не проверяют реальную интенсивность/ресурсы; invalid config должен падать | Только schema/config |
| boundary_and_normal, mixed_capture, time_only | handmade4packets; wrapper всегда добавляет accepted_devices | Сфабрикованный local auth/confirmed flag даёт positive; SYN/tuple mismatch должен падать | Не независимые labels |
| reused_tuple, no_syn, duplicate_connection, missing_clock | synthetic headers/journal | Удаление SYN/unique checks должно выявляться; реальное получение SYN не проверено | Локальные инварианты association |
| independent_outcome_required | synthetic core/broker dicts | ACL client ID без времени, replay tuple без accepted event, global reject принимаются; удаление соответствующего слабого check должно падать | Имя теста завышает независимость |
| qos_retry_is_normal | local bool + artificial replay list | Не создаёт MQTT DUP; не проверяет packet/protocol correspondence | Только branching |
| normal_requires_verified_acceptance | synthetic accepted_devices | Device присутствует в любом accepted за run, не доказывает это соединение | Aggregate corroboration |
| builder_keeps_unknown... | monkeypatch read полностью обходит PCAP/GT | Может пройти при сломанном реальном mapper; проверяет CSV/hash/filtering | Structural unit, не source validation |
| hash_tampering, explicit_exclusion | temporary artificial files | Ловят stale hash; согласованная подмена labels с новыми hashes проходит | Integrity, не logical truth |
| private ontology, unknown outcome, disk watchdog | mocks/fixtures; volume du подменён | Не проверяют реальные Docker quota/traffic stop | Unit guard |
| retention guards/age | temporary files/symlink, удаления нет | Проверяют unsafe path и age, не state приложения | File safety |
| credential length | pure function, без broker | Не доказывает MQTT rejection | Shortcut prevention only |
| header exports private | mocked tshark/subprocess | Проходит при неверном tshark extraction; проверяет umask | Permissions only |
| research75 import/schema/split | synthetic CSV groups, реальные pandas/sklearn | Проверяют schema/hash/capture intersections; synthetic grouping не доказывает независимость real captures | Reproducibility/engineering |
| research75 preprocessing/IF/balancing | synthetic fit/predict | Training-only transforms/normal-only IF проверяются; real attack coverage отсутствует | ML methodology unit |
| research75 freeze/inference/threshold/unknown class/CI | tiny synthetic models/artifacts | Hash/once-only threshold/test guards; scores искусственные | Не реальные RF/IF metrics |
| research75 Policy/online-schema guards | in-process synthetic signals | Несовместимость должна падать, не доказывает сетевой collector | Trust boundary unit |
| verify_research75b | реальный Docker/TLS/PG/Mongo/PCAP; checks Mongo=outbox, socket state, fault stop | Ловит остановку ingestion/duplicates/socket leak; использует тот же validate, не ловит согласованную подмену labels | Реальная интеграция, не label accuracy |
| mqtt_security_smoke/live_web_smoke/Chromium | реальные TLS/ACL/HTTP/Socket.IO/browser | Реальные forbidden actions должны отвергаться; не тестируют lab labeling | Security integration |
| check_dual_database/check_ml_system/check_policy_system | реальные новые project/services, outage/restart/crash | Проверяют committed records/recovery/dedupe; не входят в независимую проверку меток | Fault/recovery |
| bounded rebuild +13baseline hashes | реальные файлы, network disabled | Доказывают byte-identical regeneration/сохранность; один и тот же mapper может повторять ошибку | Reproducibility, не correctness |

Реальные defects: reconciliation gap; connection activity обозначена packet_audited;
rate/pattern подтверждены len(actions); ACL без session/time; replay без timed accepted
и intentional-vs-QoS связи; anonymous reject +local flag; scientific_quality_available
из двух полей. Риски, ещё не доказанные реалистичной атакой: shortcut generalization,
часы/абсолютная label accuracy, broker log delay/loss, общий host/stack, statistical
independence. Идентичный feature vector не равен физическому дубликату пакета.

Новый oracle должен независимо проверять packet identity из PCAP и evidence,
а не вызывать builder повторно. Старые tests остаются historical regressions.
Новые tests/probes и mutation results перечисляются в GROUND_TRUTH_VERIFICATION.md
и RESEARCH_75B_FIX_RESULTS.md после фактического выполнения.

Итог после исправления: новый oracle и real probes реализованы; результаты и
ограничения приведены в [RESEARCH_75B_FIX_RESULTS.md](RESEARCH_75B_FIX_RESULTS.md).
Историческая классификация выше относится к исходному HEAD 3282557.
