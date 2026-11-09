# Протоколы этапа 6

Ветка feature/ml-inference-pipeline от cfda660. Все отказы проверялись в отдельном
Compose project lcm-stage6; прежние working volumes не использованы. Секретные
env/keys/certs/models/data приватны и не в Git/образах. Source notebook unchanged.

Разделяйте три вида результатов:

1. **Network real-data experiment**: source2219201 rows/63cols, selected11851,
   split5630/1227/2005 после duplicate purge. RF/IF реальные, но host-pair proxy и
   normal validation9 не подтверждают переносимость на устройства/настоящий MQTT.
   stage6-network-metrics.json + stage6-dataset-audit.json, ML_EVALUATION.md.
2. **Telemetry DEMO**:320 synthetic records4devices,300 causal windows,
   split180/60/60. Statistical/IF models. stage6-telemetry-metrics.json.
   Нет independent labels, нет precision/recall/F1 «из собственных predictions».
3. **Engineering tests**:233 pytest passed + реальные MQTT/PG/Mongo/ML/HTTP
   сценарии. Это проверка механизма, не detection accuracy.

| Требование | Доказательство |
|---|---|
| Train/inference schema и train-only preprocessing | test_ml_pipeline.py, stage6-offline.txt / stage6-tests.txt |
| Missing/bad/NaN/Infinity/unknown categories | те же tests, explicit bounds и train median/OHE rules |
| Per-device isolation / causal windows / clock errors | test_ml_pipeline.py, test_ml_inference.py; seq/time guards, warmup/skips |
| Manifest load/restart/tamper/version/path trust | test_ml_pipeline.py, actual worker restart в stage6-integration.txt |
| One source/model evaluation / fencing / racing completion | test_ml_storage.py, test_ml_inference.py; unique constraints + fresh row lock |
| Missing/disabled ML не останавливает telemetry | stage6-integration.txt: missing artifact и продолжающийся MQTT→Mongo; disabled worker unit |
| Mongo outage сохраняет committed ML и retry | stage6-integration.txt: настоящий stop/up, stage6-tests.txt |
| Late measured_at не теряется из-за cursor | bounded delivery markers + late-source integration test с out_of_order event |
| Stage5 migrations сохраняют старые данные | test_stage5_upgrade_preserves_outbox_and_backfills_ml в stage6-tests.txt |
| Authorized UI / closed permission | test_ml_web.py, stage6-live-web.txt, no inference in HTTP |
| Real PG/Mongo contour / prior regressions | stage6-tests.txt, stage6-storage-regression.txt, stage6-integration.txt |
| TLS/ACL/CSRF/Socket.IO/Chromium | stage6-security.txt / stage6-live-web.txt / stage6-browser.txt |

Протоколы с UTC/командой/exit codes включают промежуточные failures. Первые
offline tests выявили отсутствующий fitted_ у statistical estimator и ошибочное
предположение теста о последней строке при межустройственной сортировке; исправлены.
Range guard tcp.len потребовал исправить synthetic holdout test value, protection
не отключалась. Source preparation выявила нечисловые ports и слишком много
host-pairs для initial budget; методика cohort sampling зафиксирована до fit.
Full source C-engine auditor завершилсяSIGSEGV; raw-string Python engine успешен.

Frozen summary exporter не обучает модель и не меняет threshold. PR/ROC относятся
к binary attack risk; multiclass argmax и thresholded risk metrics раздельны.
Test не использовали для подгонки параметров после просмотра. Additional dataset
research — ML_DATASETS.md; скачивание и смешивание не выполнялись.

## Воспроизведение проверок

Фактические команды с environment/config приведены в соответствующих txt:

```bash
docker compose --env-file .local-runtime/stage6.env run --rm --no-deps tests
python3 scripts/check_ml_system.py --env-file .local-runtime/stage6.env --reuse-installed-model
python3 scripts/check_dual_database.py --env-file .local-runtime/stage6.env
```

Первый прогон ML smoke выполнялся без --reuse-installed-model на новом изолированном
model volume и проверял отсутствие модели. Повторный запуск сохраняет установленную
immutable модель. Security/web/browser команды см. stage6-security.txt,
stage6-live-web.txt, stage6-browser.txt. Последний полный pytest — stage6-final.txt:
233 passed in22.13s. Статические проверки и проверка воспроизводимости всех шести
requirements exports — stage6-static.txt; известные секреты/Git history/три образа
проверены в stage6-audit.txt. Данные/weights в Git и /app образов не добавлены.

После завершения изолированный lcm-stage6 остановлен без удаления volumes:
[stage6-shutdown.txt](stage6-shutdown.txt). Данные и локальные private модели
сохранены; команды реального integration run требуют сначала поднять контур.
