# Stage11: сравнение конкретных реализаций

`python -m scripts.benchmark_stage11 --output <new-path>`; provider executable задаётся приватным локальным `LCM_KUZ_PROVIDER` path, не ключом. Три независимых process/key повтора, ротация порядка трёх профилей, одинаковый AAD, payload64/256/1024 и размер настоящего sensor JSON. Warmup20,300 пар encrypt/authenticated-decrypt на конфигурацию; всего36 runs. Raw nanoseconds, mean/median/stdev/min/max и descriptive p95/p99 сохранены в `crypto-benchmark.json`.

Ascon — Python reference; AES — оптимизированный native cryptography; Kuznyechik/MGM — Go CT cipher с IPC и новым subprocess на вызов. Измеряется выбранный integration path, включая spawn, key schedule и authentication. Это не сравнение чистых математических алгоритмов, криптостойкости, ARM или сертификации. Python CPU и child CPU разделены; child RSS учитывается отдельно, не выдаётся за точную combined peak memory.

p99 из300 коррелированных packets не считается устойчивой tail estimate. Независимых runs только3; confidence interval не заявляется. Machine-readable report фиксирует среду и исходный commit, последующий source manifest отделяет изменённую рабочую копию от исходного baseline.

Реальная сеть: четыре направления переключения и семь отказов с cohort3, MQTT/TLS, durable PG и Mongo history. Static profile intervals сравниваются по реально committed events, а не PUBACK. Device encryption, received_at и delivered_at имеют разные границы; время measured_at→PGcreated включает формирование/транспорт/receiver/commit-boundary timestamp, не чистую network latency. На одном Docker host используется общий wall clock, погрешность clock/timestamp placement отдельно ограничивает вывод. Полного capacity research в Stage11 не проводится.

## Полученные microbenchmark значения

Среднее трёх **run medians**, микросекунды (encrypt / authenticated decrypt):

| Payload | Ascon Python | AES native | Kuznyechik Go+IPC |
|---|---:|---:|---:|
|64B|274.77 / 276.27|1.43 / 1.44|1513.85 / 1516.53|
|83B sensor JSON|292.14 / 293.31|1.42 / 1.43|1483.01 / 1483.27|
|256B|462.30 / 464.42|1.43 / 1.45|1621.53 / 1623.11|
|1024B|1240.13 / 1239.36|1.52 / 1.54|2228.05 / 2230.54|

IPC/startup overhead входит в измеренный Kuznyechik путь. Эти значения не дают основания ранжировать алгоритмы по криптостойкости. Точные CPU/RSS/raw timings и variance — в JSON.

Реальные static windows:16/16 PG/Mongo на каждый профиль за8s, median timestamp interval3.642/2.501/9.589ms (Ascon/AES/Kuznyechik). Подробные границы/ресурсы — `mqtt-benchmark.json`, краткая таблица — STAGE11_RESULTS.
