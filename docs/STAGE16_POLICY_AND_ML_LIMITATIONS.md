# Policy и ML: обязательные ограничения

Policy FSM, версии правил, guard/cooldown/hysteresis/recovery и оптимизированная durable queue Stage13 сохранены. Режим DRY_RUN; proposals не отправляют команды. Worker heartbeat и freshness обработанного evidence — разные поля. UNKNOWN при отсутствующем/устаревшем ML не является ошибкой интерфейса; отсутствие ML нельзя считать NORMAL. Высокая температура или delivery delay не доказывают кибератаку.

Stage14: holdout 2090 retained packet observations, 1986 Normal/104 ControlledViolation; 78 sessions, только 5 positive. Packet RF recall 0.490385, IF 0.076923. Session RF recall 0.4, IF 0.2. Один физический host, сильный fingerprint purge и ограничения shortcut audit; никакой независимой host-domain validation.

Stage15: 975-packet online/offline five-feature parity в заявленном Ethernet/IPv4/TCP contract. На новом corroborated Normal subset packet IF дал 254/375 ложных threshold crossings (67.73%), выбранный session IF — 12/12 false activity-window aggregates. Пороги не изменялись. Нулевой RF FP в малом subset не доказывает нулевой operational FPR. Labels connection/window не являются packet-specific attack attribution.

Shadow — SHADOW_ONLY/trusted_detector=false, network sessions unbound. Scores не probabilities реальной атаки, не authenticated security verdict и не право на control. Нет доказанного production IDS, external generalization или physical IoT portability. В Stage16 модели не обучаются, старый holdout не переиспользуется. Research tests с synthetic fixtures не являются новым научным экспериментом.

[Stage14 metrics](STAGE14_RF_IF_RESULTS.md), [Stage15 operational results](STAGE15_OPERATIONAL_FALSE_POSITIVES.md), [future Policy design](STAGE15_POLICY_INTEGRATION_DESIGN.md).
