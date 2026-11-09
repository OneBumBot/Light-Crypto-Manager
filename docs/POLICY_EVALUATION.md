# Фактическая оценка Policy Engine — этап 7

Результаты относятся к алгоритму управления в DRY_RUN/SIMULATION.
Качество ML/IDS, стойкость криптографии, скорость шифрования и реальные
переключения устройств этими результатами не измеряются.

## Детерминированный эксперимент

13 синтетических сценариев ×4 варианта. По117 наблюдений на вариант; JSON
сохраняет rules/config, policy_version, времена и trace каждого решения.

| Вариант | Решений в trace | Переходов риска | Suppressed | Изменений модельной рекомендации | Условных неожиданных эскалаций |
|---|---:|---:|---:|---:|---:|
| fixed | 117 | 4 | 0 | 0 | 0 |
| adaptive | 117 | 34 | 28 | 7 | 10 |
| adaptive_research | 117 | 35 | 28 | 7 | 11 |
| adaptive_hysteresis | 117 | 16 | 6 | 7 | 3 |

Файл [stage7-policy-experiment.json](reports/stage7-policy-experiment.json).
Trace фиксирует каждый шаг симулятора; suppressed/rate_limited шаг не обязательно
становится самостоятельной записью decision у реального State Manager.

В oscillation: adaptive17 переходов, adaptive_hysteresis1. Replay-series:
реакция до ALERT1s против2s (при подтверждениях2 против3); это модельное время
от первого заданного replay, не время реального криптографического переключения.
Во всех52 runs applied_changes=0. Fixed не повышает защиту по security trigger,
но NORMAL/UNKNOWN доступности могут меняться. Исследовательские ML рекомендации
дают дополнительные модельные наблюдения, не подтверждённые атаки.

Unexpected risk escalations считаются относительно заданного наличия security
trigger в сценарии; даже корректный WATCH физического правила может попасть в
этот счётчик. Это не оценка FPR детектора и не число реальных ложных переключений.
Пропущенные события не заполняются нормой; ML outage не разрешает восстановление.

## Реальный контейнерный контур

Протоколы [STAGE7.md](reports/STAGE7.md). Отдельный project lcm-stage7, новые volumes;
прежние рабочие БД не использовались для fault tests. Проверены:

- атомарность/rollback, UNIQUE(event_id,version),16 конкурентных попыток одного
  события, independent device states и guard при активации другой версии;
- реальные MQTT replay трёх устройств, поддельный AAD без victim state;
- два policy-worker, рестарт, policy downtime без остановки telemetry;
- настоящий PostgreSQL outage, снятие readiness и свежий heartbeat после recovery;
- сохранность replay/ML/legacy данных через additive migrations;
- старые Outbox/Mongo/PG outage/crash сценарии и ML model restart/Mongo recovery;
- Flask login/roles/admin activation/CSRF, Socket.IO, safe redirect, TLS/ACL и
  Chromium XSS на старых и новых интерфейсах.

Последний полный pytest и точная команда — reports/stage7-final.txt.
Предыдущие failures сохранены: unit mock нового журнала, изоляция Flask test g и
ожидание literal JSON строки в Chromium; проверки защиты не отключались.

## Снимок метрик стенда

[stage7-policy-metrics.json](reports/stage7-policy-metrics.json):
среднее compute_ms=0.4915, p95=1.5695ms;
средний source lag=0.5302s. Значения получены
на малом изолированном smoke-контуре, включают ранние прогоны разработки и не
являются benchmark финальной версии. Timing относится к evaluate(), без PG
commit latency; source lag включает очередь/остановки тестов. Switching latency=null.
Нет измерений throughput/CPU/RAM/энергии для разных криптоалгоритмов или10000 устройств.

Для практической главы пригодны исходный код/контракты, схема транзакций,
воспроизводимые52 traces, сравнение oscillation/reaction trade-off и фактические
recovery/security проверки. Для выводов о реальных атаках/криптопереключении нужны
проверенные детекторы, реальные device данные, control handler/keys/ACK и отдельные
эксперименты на реализованных профилях. «Магма» и CRISP остаются будущей работой.
