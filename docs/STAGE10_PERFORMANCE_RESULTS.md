# Stage10 performance: методика чтения результатов

Машиночитаемые первичные данные: `reports/stage10/load-*/samples.json`, `agent-events.json`, `committed.json`, `result.json`, `timings.csv`. Итоговые таблицы будут сведены из этих артефактов, а не из PUBACK.

Каждый scheduled count — идеальное периодическое окно локального agent clock, включая ожидание соединения/grant. Formed — конкретная AEAD identity; publish_called и queued разделены; PUBACK связывается по device/boot/mid. Команда lease/control тоже получает PUBACK, но её mid не засчитывается в telemetry source. Journal append/line buffered — наблюдение, не crash-durable audit. При аварии оставшиеся packets нельзя автоматически объявить потерянными.

PG window — committed rows, отобранные по admission created_at в интервале наблюдения. Counter delta берётся между snapshots и включает границы остановки/drain; поэтому может немного отличаться от window. Source unmatched window означает возможный boundary event, а не доказанную потерю. После drain сравниваются cumulative PGaccepted и Mongo-managed counts отдельно. В этом стенде retention отключён, старых managed device rows нет.

CPU — Docker sampled % одного core суммарно по project, RAM — Docker working memory, не весь host RAM и не allocation cipher. Опубликованные percentiles latency относятся к сообщениям одного cohort, они коррелированы; это не confidence interval для независимых устройств/deployments. Run/cohort выполнен один раз; capacity не экстраполируется. Microbench имеет3 независимых subprocess repeats, 1000 pairs+100 warmup, равный148B AAD, payload64/256/1024/83B;83B — canonical sensor JSON текущего агента. AAD148B выбран одинаковым для обоих implementations, не является фиксированной длиной всех telemetry identities/sequence.

Криптографическое сравнение — **Python reference Ascon против native cryptography AESGCM на данном x86 host**, а не универсальная эффективность алгоритмов, криптостойкость, ARM или энергопотребление. PeakRSS — процесс целиком. Точные software/OpenSSL versions и raw ns в crypto-microbenchmark.json/CSV. Порядок Ascon/AES чередуется по repeats.

Clock model: Linux Docker host CLOCK_REALTIME; local intervals perf_counter/monotonic. measured→received включает device encoding/queue/TLS/receiver authentication до timestamp admission; это не network-only и не PGcommit duration. received→delivered_at включает relay/Mongo/PGfinish, delivered_at после Mongo majority/journal write, не exact Mongo commit. Отдельные PGcommit/network-only/DBreconnect метрики not_measured. Внешние часы/физические устройства не проверялись.

Первый 3-device run включал настоящие browser switches и фоновый microbench; он помечается mixed/adaptive, его CPU не сравнивается как чистая isolated crypto workload. 10-device run Static Ascon. Остальные workloads явно отмечаются в итоговой таблице.

Software/device identities — не физические датчики: measurements23.5°C/48% — существующие сообщения настоящего программного агента, не новые экспериментальные environmental data. Измерения transport/AEAD/admission/delivery реальные. Constant sensor values не доказывают корректность IDS. 25-device stability run включал ограниченные диагностические SQL/HTTP probes и двухсекундный targeted DB regression в отдельной schema; все resource samples сохранены, пики не исключены. Это engineering workload observation, не полностью изолированная лаборатория CPU.

Прототипные3/10/25 collector reports сохраняют SHA/dirty/source metadata на момент завершения; приложения выполнялись из неизменяемых Docker image IDs, перечисленных в result. В окончательном collector source SHA/hashes фиксируются **до** окна, отдельно от image IDs. Изменения read-model/tests во время development не подменяются старым baselineSHA. Все raw timings сохранены; независимого repeat каждого deployment нет.

Сравнение cohort scatter plots описательное: длительности300/300/900/300s, объёмы истории и прогрев различаются. Нельзя приписывать весь рост RAM/latency только числу устройств. Никакой линии экстраполяции/оценки максимальной capacity не строится. Более низкая latency при некоторых низких частотах зависит от фазы относительно .5s idle polling relay; это не доказательство эффективности AEAD. Additional single-agent60s windows — exploratory Ascon/AES и .5/1/2s intervals, не длительный stability proof.

## Измеренные результаты

Числа ниже получены из `reports/stage10/load-*/result.json`. Ограничения длительностей, фоновых probes и clock model выше сохраняются. PG в окне и source join после drain разделены.

| Устройств | Фактическое окно, с | Formed | Source→PG после drain | PG msg/s | CPU mean, % одного core | RAM mean, MiB | Median end-to-end bound, мс |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 300.17 | 1790 | 1790 | 5.96 | 31.4 | 621 | 264.2 |
| 10 | 300.94 | 5980 | 5980 | 19.87 | 61.6 | 699 | 265.1 |
| 25 | 900.00 | 44716 | 44716 | 49.68 | 124.9 | 1133 | 269.7 |
| 50 | 300.00 | 29818 | 29818 | 99.38 | 179.0 | 1658 | 287.2 |

Во всех основных окнах observed nonce duplicates и MQTT reconnect агента — 0. Максимальные sampled Outbox backlog — 3/10/25/52, PG connections — 11/8/9/11. DB reconnect count не измерен. Итоговая доставка всех109868 committed записей подтверждена после drain; это не обещание доставки произвольных несформированных/несохранённых событий.

Полные per-device/per-run statistics, raw timings и ciphertext sizes — `analysis-final.json`, `crypto-microbenchmark.json`/CSV.gz. Восемь графиков — `reports/stage10/figures/`. Итоговый контекст, microbenchmark и отдельные60s frequency windows: [STAGE10_RESULTS.md](STAGE10_RESULTS.md).
