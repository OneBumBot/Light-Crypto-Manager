# Stage15 — operational false positives

Три новых independently corroborated normal workload captures:regular,jitter,normal QoS1retry. Labels построены неизменёнными broker+witness+PG oracle rules на настоящем Shadow PCAP,независимо от scores. Known375Normal packet observations,12corroborated activity sessions;unknown boundary packets исключены из FPR.12sessions не являются12независимымиhardware experiments;QoS1пары связаны,host/realmодин.

| Frozen model role | Normal observations | FP observations | Packet FPR | Normal activity sessions | False session/window aggregates |
|---|---:|---:|---:|---:|---:|
|rf_binary|375|0|0.000000|12|0|
|if|375|254|0.677333|12|7|
|rf_session|375|1|0.002667|12|0|
|if_session|375|247|0.658667|12|12|

Packet winners — rf_binary иif;session winners — rf_session иif_session. Session/window ratios в этой таблице рассчитаны отдельно по retrospectively known-normal activity subset и frozen aggregator;это не автоматическая оценка всех raw TLS boundary packets как Normal и не тот же объект,что causal online whole-observed prefix. Полные causal session outputs хранятся отдельно с explicit closure/context boundaries.

IF frozen threshold не сохраняет validation FPRtarget0.05 на этом новом нормальном traffic subset:254/375≈67.73%.Это реальный отрицательный операционный результат. Никакого подбора порога,новой calibration или retraining. RF0/375не означает доказанный FPR0или безопасность устройства;normal support мал и зависим,controlled-violation detection не гарантирована.

Дополнительные normal peers в controlled scenarios тоже анализируются отдельно в operational-contrast.json. Без oracle labels,например48-run load series иquarantined broker reconnect,публикуется только unlabelled threshold-crossing rate, FPR=not_evaluable. Unknown не становится Normal. Тамpering/wrong epoch/sequence actors остаютсяunknown без точной authenticated failure attribution.

False_alarm_events_per_nominal_run_hour — rate повторяющихся packet threshold crossings, масштабированный из фактических≈6s run windows кчасу. Это не реально наблюдённый час,не число независимых incidents и не latched operator alarms. Нельзя использовать узкий packet-IIDconfidence interval. Per-session false alarms иповторные packet crossings показаны раздельно.

QoS1:independent brokerDUP/PG replay может быть нормальной redelivery. Controlled non-DUPreplay имеет prior accepted identity,witnessdigest иPGreplay,ноthese categoriesне predictors. По5passive fields нельзя выводить cryptographic replay verdict. Новые handshakes/packet-size/timing/longer-lived sequences отличаются от Stage14purgedknown-labelled population. Exact feature parity не устраняет population/domain shift.

Independent host/domain отсутствует:INDEPENDENT_GENERALIZATION_NOT_VERIFIED, generalization_evaluation=BLOCKED_INDEPENDENT_DATA. Это same-host operational evidence,не новый scientific final holdout. Stage14holdoutне открывался для tuning,модели остаютсяSHADOW_ONLY/trusted_detector=false.
