# Воспроизводимое моделирование

```bash
.venv/bin/python -m src.policy.simulation --output .local-runtime/policy-experiment.json
```

Фиксированное время UTC2026-01-01, детерминированные UUID и конфигурации. Случайных
или реальных sensor/attack данных здесь нет. 13 сценариев ×4 варианта политики:
fixed, adaptive, adaptive_research, adaptive_hysteresis.

Сценарии: normal; single_physical; physical_series; replay_series;
verified_security_violation; ml_unavailable; stale_ml; conflicting_sources;
recovery; oscillation; missing_events; unsupported_profile; missing_ack.

Baseline fixed сохраняет фиксированный профиль, но состояние доступности может
меняться NORMAL/UNKNOWN; остальные сравнивают
алгоритм управления, а не эффективность криптографических алгоритмов. Без
hysteresis recovery/count/cooldown осознанно уменьшены. adaptive_research явно
позволяет недоверенной ML-рекомендации менять только модельный risk WATCH.
В реальном DRY_RUN это не делает ML доверенным.

Каждый trace содержит сигналы, причины, время, state transition, рекомендацию и
applied=NULL. simulated-profile — только математический маркер для маршрута
рекомендаций, без криптографического примитива. missing_ack проверяет, что даже
модельная рекомендация не становится применением. ACK simulator тестируется
отдельно; симулятор не создаёт поддельных ACK реальных устройств.

Показатели: decisions, risk_transitions, suppressed, modeled_recommendation_changes,
unexpected_risk_escalations, reaction_seconds и applied_changes=0. Unexpected
означает эскалацию на сценарии без заданного security trigger (физическая/ML
нетипичность также может дать WATCH); это условная метрика управления, не FPR
IDS и не доказательство ложного реального переключения. reaction_seconds —
время от первого синтетического security trigger до ALERT/CRITICAL; null, если
порог не достигнут. Пропуски не дополняются выдуманными нормальными наблюдениями.

Машиночитаемый результат этапа — reports/stage7-policy-experiment.json.
Повторный запуск должен дать одинаковый JSON; это проверяется unit-тестом.
