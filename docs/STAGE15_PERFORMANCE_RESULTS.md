# Stage15 — измеренная производительность

Источник сравнительной серии:dd3d15a.48runs,4cohorts×4conditions×3conditional repeats,15s workload/run, один cohort одновременно. После серии дополнительно усилены обработка malformed metadata, freshness и session finalization; математическая модель/пять признаков/пороги не менялись. Приведённые сравнительные timings относятся к указанному измеренному source, не к непроверенному универсальному пределу финальной версии. Полный pytest и отдельные живые проверки повторяются на финальных guards.

Source code hashes/CPU/RAM/duration — в каждом v3-*.json. Образ и readonly source bindings фиксируются отдельно. До успешнойv3 сохранены две остановленные диагностические попытки:offline import error и SQLite writer contention. Они не включены в48successful runs.

| Identities | Condition | PG admissions/s,mean | SD между3runs | Средняя run-median capture→prediction,s |
|---|---|---:|---:|---:|
|3|capture|1.475056|0.002254|not_measured|
|3|off|1.472699|0.006645|not_measured|
|3|rf|1.474347|0.009522|0.426413|
|3|rfif|1.478800|0.005258|0.903024|
|10|capture|9.404931|0.031237|not_measured|
|10|off|9.423211|0.026454|not_measured|
|10|rf|9.392030|0.053742|0.651324|
|10|rfif|9.385204|0.072245|0.670671|
|25|capture|44.553239|0.169471|not_measured|
|25|off|44.751342|0.355606|not_measured|
|25|rf|44.681700|0.050153|0.759797|
|25|rfif|44.473633|0.433659|0.795317|
|50|capture|69.890357|0.414739|not_measured|
|50|off|80.326797|0.235234|not_measured|
|50|rf|74.837417|0.165944|0.954020|
|50|rfif|75.916716|0.573233|0.957565|

Целевые частоты:3×0.5Hz,10×1Hz,25×2Hz,50×2Hz. Фактическая публикация при50ниже100/s, в том числе без observer. Это threaded software identities одного generator process, не50физических устройств или50Device Control Agent контейнеров. Startup staggering,синхронный Paho loop,SQLite sequence writes и shared-host scheduling ограничивают достижимый поток. Нельзя называть100/s достигнутой sustained нагрузкой.

Всего в48runs:formed=24483,queued=24483,PUBACK=24483,PGcommitted=24483,Mongostored=24483. Сверены точные(device,epoch,sequence) identities, а не только совпавшие counts. Outbox после drain0. Scheduled publications=not_measured_event_driven_loop. PUBACK сам по себе не доказательство PG/Mongo durability.

Captured TCP packets=68751; SCORED records=69492 (1RFилиRF+IFпоусловию). Это разные единицы.36capture runs complete, kernel/reader/application drops0,final pending0. Никакой формулы1telemetry=1TCP packet. Все successful source packets имели доступный контекст в этой серии; fault/unknown cases учитываются отдельно.

CPU/RAM raw Docker samples обрезаны по реальному active generator window из source-window-audit.json, чтобы idle tail23s capture не сравнивался с15s off workload. Docker MemUsage — sampled container memory, не точный RSS; отдельно worker/capture ru_maxrss. Run summary/repeat summary CSV и7PNG/SVGсемейств сохраняют только реальные точки; error bars=run SD,не confidence interval. Missing values остаютсяNone,не0.

Capture→features/prediction/journal-commit-ack измеряются отдельно. Model batch wall включает подготовку и все выбранные модели batch≤64; это не pure per-tree latency. p95приn≥100,p99приn≥1000 — описательные packet quantiles,пакеты коррелированы. CLOCK_REALTIME общий host/контейнеры, kernelPCAPmicro/nano units; cross-host accuracyне проверялась. Outbox creation→delivered marker — отдельный серверный интервал,не точное время PGcommit ack или чистого network transport.

При50идентичностях наблюдается снижение фактического incoming throughput относительно off; данные не скрыты.3повтора одногоhost/realm не дают строгого причинного эффекта или внешней переносимости. Short15s runs не доказывают30min stability/maximum capacity. Графики:data in figures/,CSV run-summary.csv/repeat-summary.csv,exact delivery proof in exact-delivery-identities.json.

Дополнительный25-device20s diagnostic:queue-freshness.json, sampled max pending188приcapacity512,physical captured3283,kernel drops0,capture complete. Sampling0.5s, истинный peakмеждуsamples=not_measured; не подменёнfinal pending0. Этот diagnostic не добавляется как четвёртый независимый повтор comparative matrix.

## Ресурсы и хвосты latency

Ниже среднее run-wise статистик трёх условных повторов; p95/p99 не являются pooled quantile, memory — среднее sampled container-memory peak, не точный RSS. Docker CPU 100% соответствует одному logical CPU.

| Identities / RF+IF | Model CPU | Capture CPU | Model memory | Capture→prediction p95 / p99 |
|---|---:|---:|---:|---:|
| 25 | 9.93% | 3.74% | 125.8 MiB | 1.149 / 1.307 s |
| 50 | 13.94% | 6.86% | 125.6 MiB | 1.342 / 1.492 s |

Receiver CPU: для 25 identities off 13.46%, RF+IF 11.66%; для 50 off 23.24%, RF+IF 21.73%. Меньшие отдельные значения не доказывают ускорение receiver: фактический поток, scheduling и короткое sampling window различаются. Полный набор условий — [resource comparison](reports/stage15/resource-comparison.json).
