# Этап 7.5: воспроизводимое исследование и границы результата

База c9250d8, ветка feature/ml-research-improvement. Научного улучшения качества
RF/IF на новых независимых данных пока **не подтверждено**. Инженерный pipeline
реализован; новые реальные модели не обучались из-за недостатка captures/разметки.
Синтетические фикстуры используются только тестами, их F1 не публикуется как IDS.

## Реально выполнено

- Замороженный baseline сохранён. Read-only диагностика обнаружила нормальные
  validation scores1.0 и эффект duplicate purge694→9 normal; остаток —1 группа,
  1 canonical feature-vector. Диагностика не меняет threshold/fit/test selection.
- Изучены13 notebook cells, новый и старый training/preprocessing/splitting,
  manifest/loader и независимость Policy Engine. Notebook не переписан.
- Публичный MQTTset v5 metadata/license/listing, parser/README и два реальных CSV
  получены/проверены; данные не распространяются через Git.
- Реальные14501 raw TCP packet observations импортированы с SHA/provenance.
  Plan отклонён: normal captures0, attack captures1. Полный listing имеет только
  один normal capture; reduced330926 строк не имеет capture/session metadata.
- IEEE landing page получена анонимным HTTP200: metadata CC BY4.0; download UI
  предлагает login/subscription. Архивы не получены, ограничение не обходилось.
- Подготовлены новая packet schema, bounded candidate matrix, capture split,
  train-only transforms/weights, normal-only IF, validation threshold и frozen test.
- Старые source/crypto/policy invariants сохраняются; online collector не установлен.

## Команды

Все команды из корня репозитория, существующая .venv с закреплёнными зависимостями.
Данные/планы/модели держать в приватном локальном каталоге, не в Git.

```bash
python3 scripts/fetch_mqttset75.py --directory .local-runtime/research75/download --file Data/README.md
.venv/bin/python -m scripts.audit_mqttset75 --directory .local-runtime/research75 --output .local-runtime/research75/audit.json
.venv/bin/python -m scripts.diagnose_rf75 --data .local-runtime/edge-research/network-grouped-v2.csv --models .local-runtime/stage6-network-models --output .local-runtime/research75/diagnosis.json
```

Download helper ограничен конкретными файлами, версией5 и licence metadata; caps
и свободное место проверяются. Существующий файл не перезаписывается. Он не
использует Kaggle credentials и не скачивает весь9.57GB архив. Поддержан импорт
локально предоставленного CSV; source manifest с expected SHA обязателен.

```bash
.venv/bin/python -m src.classifier.research.cli import --config /private/import.json --output /private/packets.csv
.venv/bin/python -m src.classifier.research.cli plan --data /private/packets.csv --manifest /private/packets.manifest.json --config configs/ml/research75.json --output /private/plan.json
.venv/bin/python -m src.classifier.research.cli train --data /private/packets.csv --manifest /private/packets.manifest.json --plan /private/plan.json --models /private/models --experiment /private/experiment
.venv/bin/python -m src.classifier.research.cli test --data /private/packets.csv --manifest /private/packets.manifest.json --plan /private/plan.json --models /private/models --experiment /private/experiment
.venv/bin/python -m src.classifier.research.cli external --data /private/external.csv --manifest /private/external.manifest.json --models /private/models --experiment /private/experiment --output /private/external-result.json
```

/import пример — configs/ml/research75-import.example.json. source_id/capture_id,
SHA, source URL, dataset version, licence, synthetic declaration и label_scope
обязательны. Для packet_audited нужен label_column с0/1; normal background не
заменяется атакующим label файла. dataset_family: mqttset или mqtt-iot-ids2020,
их типы атак не сливаются произвольно. Native2020 CSV без RAW fields несовместим;
для адаптации нужны raw PCAP re-extraction и проверенная привязка labels.

## Жизненный цикл эксперимента

1. Hash/field/type/unit/provenance validation. Только packet TCP, до100000 строк
   по default, явный предел не заменяется молчаливым случайным sampling.
2. Capture-level60/20/20 (StratifiedGroupKFold5), fixed seed75. Captures и sessions
   не пересекаются. Conservative cross-feature duplicate purge записывает потери
   и распределения до/после. Недостаток классов/normal rows/groups → отказ.
3. Plan сохраняет indices/hash/config/версии до обучения. Source changes → отказ.
4. Fit RF preprocessing только train; IF preprocessing и estimator только normal
   train. Class weights только внутри fitted RF. Validation/test не балансируются.
5. RF binary/IF выбираются по validation binary F1 при empirical FPR target.
   RF multiclass отдельно по fixed-source-ontology Macro-F1; binary risk threshold
   этой модели — отдельная задача. Неопознаваемый тип атаки не выдумывается.
6. Все predefined candidates и validation winners/thresholds/artifact hashes
   замораживаются в freeze.json. Новые model_id research75-*, version7.5.0
   (для нового опыта задайте новую version); существующий artifact не перезаписывается.
7. Однократный test создаёт exclusive final-test-started **до** prediction.
   Повтор/изменённый freeze/model/threshold отвергается. После crash нужен reviewed
   новый эксперимент, а не незаметный повтор с другим порогом.
8. External route не fit-ит и не меняет threshold; проверяет source/capture hashes,
   отдельный source URL и общую schema. Он оценивает binary risk; несовместимые
   source taxonomies не объединяются в одну multiclass accuracy.

Plan читает labels/counts и статeless fingerprints для разделения/дедупликации;
это не fit preprocessing на holdout. Frozen internal test не используется для
подбора, даже если другая кандидатная модель на нём выглядит лучше.

## Артефакты и безопасность

Существующий loader расширен ровно для tcp-packet-passive-v1 с exact feature order
и trusted_detector=false. network-core-v1 и telemetry-causal-v1 не изменены.
Pipeline+manifest, SHA-256, точные версии Python/libs, owner/modes/path checks и
64MiB artifact cap сохранены. Hash — целостность, не подпись; только trusted local
root. Новые Network artifacts не ставятся в telemetry worker. В runtime image
новый research package не копируется; он есть только в tests target/локальном коде.

Дальнейшие шаги — предоставить independent raw captures/локальные архивы2020,
проверить labels/clock/link layer/session mapping, заморозить новый holdout и только
потом выполнить реальный train/test. Основной этап8 автоматически не начинается.
