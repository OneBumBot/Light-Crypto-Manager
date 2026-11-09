# Обучение и артефакты

Используйте Python3.12.16 и lockfile. `.venv`/uv:

```bash
UV_CACHE_DIR=.cache/uv uv sync --frozen --group ml --group receiver --group web --group dev
```

ML зависимости runtime минимальны: numpy/pandas/scipy/sklearn/joblib; Jupyter,
plots и исследовательские инструменты остаются в отдельной ml group. Новые данные
и модели не попадают в Git, root local artifacts — .local-runtime (0700/0600).

## Real Network IDS experiment

Исходный DNN CSV предоставлен пользователем. Он не имеет пригодной полной
календарной хронологии/проверенных device/session IDs. Default network-train.json
требует capture_id и **не** делает random-row fallback, если этой metadata нет.
Ограниченное воспроизведение выполненного host-pair исследования:

```bash
.venv/bin/python -m scripts.prepare_edge_research --data 'src/classifier/Edge-IIoTset dataset/Selected dataset for ML and DL/DNN-EdgeIIoT-dataset.csv' --output .local-runtime/edge-research/network-grouped-v2.csv --max-rows 150000 --seed 42 --rare-group-fraction 0.02 --common-count 100
.venv/bin/python -m src.classifier.ml.train train --data .local-runtime/edge-research/network-grouped-v2.csv --config configs/ml/network-real-research.json --models-dir .local-runtime/stage6-network-models --report .local-runtime/edge-research/rf-binary.json
.venv/bin/python -m src.classifier.ml.train train --data .local-runtime/edge-research/network-grouped-v2.csv --config configs/ml/network-real-rf_multiclass.json --models-dir .local-runtime/stage6-network-models --report .local-runtime/edge-research/rf-multiclass.json
.venv/bin/python -m src.classifier.ml.train train --data .local-runtime/edge-research/network-grouped-v2.csv --config configs/ml/network-real-isolation_forest.json --models-dir .local-runtime/stage6-network-models --report .local-runtime/edge-research/network-if.json
```

Команды отказываются перезаписывать файлы/model version. Для повторения используйте
новый приватный каталог и скорректируйте source_manifest в копии config.
Сырые адреса не model features: host-pair только group metadata. Sampling целевых
labels не использует: common pairs count>=100 сохраняются, rare pairs выбираются
hash2%, row-hash reservoir до1000 на группу. Метрики не population-weighted.
Затем5-fold grouped stratification даёт номинальные60/20/20; canonical feature
fingerprints, пересекающие части, удаляются из всех частей по заранее заданному
правилу без анализа y. Статистика очищения/индексы/хеши сохраняются в manifest.
Фактический split5630/1227/2005; IF fit1961 normal. Ни один threshold не подобран
на test, после просмотра holdout параметры ради улучшения не менялись.

При надёжной time metadata поддержан time split с purge_seconds и исключением
групп, пересекающих границы. Нельзя превращать неполное frame.time в выдуманную
календарную дату и объявлять независимый временной holdout. Pipeline явно проверяет
metadata, пустые части и availability normal train/validation.

## Telemetry training

Реалистичной размеченной normal history нет. Из Mongo можно экспортировать только
проверенные поля bounded CLI scripts/export_ml_telemetry.py (MONGO_PASSWORD_FILE
должен принадлежать history role). Выборка ограничивается device/start/end/max_rows,
выход.csv/.manifest.json приватные. Нет автоматического чтения всей истории в RAM.
В ml Docker image этот CLI доступен через --entrypoint python; output/tmp можно
забрать docker cp из явно именованного одноразового контейнера без --rm.
Содержимое normal sample должно быть подтверждено исследователем: текущий
случайный demo publisher не является надёжной нормой реальных датчиков.

Default configs/ml/telemetry-train.json — DEMO statistical; algorithm может быть
isolation_forest. Offline features используют только допустимые предыдущие записи,
fit baseline/scaler только train; unknown validation device вызывает явный отказ.
Отдельные evaluation configs лежат в configs/ml/*-evaluate.json.

Именно для инженерного smoke, **не научного качества**:

```bash
.venv/bin/python -m src.classifier.ml.demo --synthetic-demo --device raspb1 --device alpha --device beta --device gamma --output .local-runtime/stage6-demo/train.csv --config-output .local-runtime/stage6-demo/train.json
.venv/bin/python -m src.classifier.ml.train train --data .local-runtime/stage6-demo/train.csv --config .local-runtime/stage6-demo/train.json --models-dir .local-runtime/stage6-models --report .local-runtime/stage6-demo/model-report.json
```

320 synthetic records,4 independently named devices; window5 →300 feature rows,
train180 / validation60 / test60. Threshold validation quantile0.99; test alert
rate0.0 не является accuracy/FPR/доказательством обнаружения реальных атак.

## Artifact boundary

`<explicit models root>/<model_id>/<model_version>/manifest.json + model.joblib`.
В manifest: task/algorithm/schema version, source+hash+parent provenance, параметры,
random_state, Python/libs exact versions, trained_at, preprocessing/window/score
semantics/range, threshold, splits/metrics/limitations, artifact SHA256.
Pipeline включает transformations и модель. Сохранение model ID/version immutable.

Root/parents/model directories0700 и файлы0600, UID владельца процесса, no symlinks,
manifest<=1MiB, model<=64MiB. Load проверяет identity/schema/hash/exact versions
до joblib.load. Hash не является подписью: локальный root должен быть доверенным;
нельзя копировать туда произвольные .pkl/.joblib из интернета. Одинаковый version
с другим manifest/hash отвергается также PostgreSQL model registry.

Модели/данные не в Git и не в Docker image. Большие full-data модели или manifest
с массивами split indices могут превысить текущие limits; это явный resource bound,
а не silent truncation. Реальные weights не распространяются до проверки license.
