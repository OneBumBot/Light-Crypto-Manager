# Stage16 — сводка окончательных результатов

**COURSEWORK_RELEASE_CANDIDATE_READY**: основной demo проверен реально. Shadow optional unavailable и Kuz lab-only не скрыты. [Полный отчёт](STAGE16_RESULTS.md).

| Показатель | Значение | Источник и границы |
|---|---|---|
| Baseline pytest |1049 passed /0skipped /53.91s /exit0|Новые PG/Mongo, baseline sourceb2317f9|
| Final pytest |1057 passed /0skipped /56.55s /exit0|Изолированные PG/Mongo, sourced1dfbf4,8new guard tests|
| Основной demo |3agents,5838PG/Mongo,14confirmed,28ACK|Quiescent stopped checkpoint; не PUBACK/formed count|
| Final clean checkout |3agents,278PG/Mongo,4confirmed,8ACK|Отдельные fresh keys/state, cold run + latest resume/helper check|
| UI |15final screenshots, desktop/mobile, JS errors0|Реальный Chromium,5mobile pages без document overflow|
| Recovery |6 bounded actual fault cases + stop/resume|Локальные наблюдаемые интервалы, не universal RTO|
| Preservation |1533tracked/6080private совпали|Files+metadata, не SQL-volume byte audit|
| ML/control |DRY_RUN /trusted_detector=false /manual-only|DB applied/models/events0, actors admin-only|

[Матрица](STAGE16_E2E_TEST_MATRIX.md), [каталог единиц/выборок/условий](reports/stage16/evidence-catalog-final.json), [схемы](STAGE16_FINAL_ARCHITECTURE.md), [ограничения](STAGE16_KNOWN_LIMITATIONS.md). Старые негативные RF/IF результаты не пересмотрены и не скрыты. Исходные datasets/PCAP/models/plans не перезаписаны. Следующий этап17 — оформление работы, не развитие функций.
