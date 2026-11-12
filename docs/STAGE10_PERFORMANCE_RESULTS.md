# Stage10 performance: методика чтения результатов

Машиночитаемые первичные данные: `reports/stage10/load-*/samples.json`, `agent-events.json`, `committed.json`, `result.json`, `timings.csv`. Итоговые таблицы будут сведены из этих артефактов, а не из PUBACK.

Каждый scheduled count — идеальное периодическое окно локального agent clock, включая ожидание соединения/grant. Formed — конкретная AEAD identity; publish_called и queued разделены; PUBACK связывается по device/boot/mid. Команда lease/control тоже получает PUBACK, но её mid не засчитывается в telemetry source. Journal append/line buffered — наблюдение, не crash-durable audit. При аварии оставшиеся packets нельзя автоматически объявить потерянными.

PG window — committed rows, отобранные по admission created_at в интервале наблюдения. Counter delta берётся между snapshots и включает границы остановки/drain; поэтому может немного отличаться от window. Source unmatched window означает возможный boundary event, а не доказанную потерю. После drain сравниваются cumulative PGaccepted и Mongo-managed counts отдельно. В этом стенде retention отключён, старых managed device rows нет.

CPU — Docker sampled % одного core суммарно по project, RAM — Docker working memory, не весь host RAM и не allocation cipher. Опубликованные percentiles latency относятся к сообщениям одного cohort, они коррелированы; это не confidence interval для независимых устройств/deployments. Run/cohort выполнен один раз; capacity не экстраполируется. Microbench имеет3 независимых subprocess repeats, 1000 pairs+100 warmup, равный148B AAD, payload64/256/1024/83B;83B — canonical sensor JSON текущего агента. AAD148B выбран одинаковым для обоих implementations, не является фиксированной длиной всех telemetry identities/sequence.

Криптографическое сравнение — **Python reference Ascon против native cryptography AESGCM на данном x86 host**, а не универсальная эффективность алгоритмов, криптостойкость, ARM или энергопотребление. PeakRSS — процесс целиком. Точные software/OpenSSL versions и raw ns в crypto-microbenchmark.json/CSV. Порядок Ascon/AES чередуется по repeats.

Clock model: Linux Docker host CLOCK_REALTIME; local intervals perf_counter/monotonic. measured→received включает device encoding/queue/TLS/receiver authentication до timestamp admission; это не network-only и не PGcommit duration. received→delivered_at включает relay/Mongo/PGfinish, delivered_at после Mongo majority/journal write, не exact Mongo commit. Отдельные PGcommit/network-only/DBreconnect метрики not_measured. Внешние часы/физические устройства не проверялись.

Первый 3-device run включал настоящие browser switches и фоновый microbench; он помечается mixed/adaptive, его CPU не сравнивается как чистая isolated crypto workload. 10-device run Static Ascon. Остальные workloads явно отмечаются в итоговой таблице.
