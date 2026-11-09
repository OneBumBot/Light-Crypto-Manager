# Этап 7.5: научный benchmark пока заблокирован

Новые реальные RF/IF не обучены: нет достаточного independent normal capture
support, reduced потерял capture/session provenance; external2020 files не получены.
Никаких новых quality scores из синтетики не публикуется. Historical reports
stage6-network-metrics.json и stage6-telemetry-metrics.json сохранены побайтно.

Новая диагностика: RF normal validation scores1.0, feature purge694→9 normal,
остаток1 группа/1 vector. Details в ML_RF_DIAGNOSIS.md. Сводная таблица baseline,
planned matrix, historical per-attack failures и measured validation inference
costs — ML_RF_IF_BENCHMARK.md. Новая методика и команды — ML_RESEARCH_7_5.md.

Не смешивать historical test, внутренний future validation/test, external dataset,
synthetic unit checks и технические regression tests. Ниже историческая оценка6.

---

# Оценка: разные задачи и разные виды доказательств

## Network IDS — реальные данные, ограниченный эксперимент

Source DNN-EdgeIIoT:2219201 rows,63 columns,15 категорий; полный SHA и распределение
в [stage6-dataset-audit.json](reports/stage6-dataset-audit.json) и
[stage6-network-metrics.json](reports/stage6-network-metrics.json). Prepared subset
11851 реальных строк/3504 host-pair groups. Canonical duplicate purge2989;
train5630 / validation1227 / test2005. Seed42;32 trees, n_jobs1. IF только normal
train1961. Test: normal1000, attack1005, из5 категорий; MITM не встречалась в train.

Это **не независимый device/session benchmark** и не оценка всей исходной
популяции. После grouping/purge train содержит7 категорий, validation14 (normal9),
test5. Самплинг изменяет prevalence. Threshold constraint5% при normal validation9
статистически слаб: не заявляется подтверждённая population FPR≤5%.

| Модель | Fit rows | Macro-F1 на фактических labels | FPR | PR-AUC | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| RF binary | 5630 | 0.3328 | 0.0000 | 0.6422 | 0.4806 |
| RF multiclass (7 fitted categories) | 5630 | 0.4119 | 1.0000 | 0.6405 | 0.4767 |
| IsolationForest binary | 1961 normal | 0.7296 | 0.0000 | 0.8544 | 0.7164 |

RF multiclass FPR относится к argmax-class prediction, а PR/ROC — binary
1-P(normal) risk ranking. Macro-F1 по фиксированной полной15-class ontology:
**0.1373**. Отдельные thresholded risk metrics записаны в JSON; их нельзя смешивать
с argmax multiclass результатом. RF threshold=1.0000000000000002 означает
отсутствие attack-сигналов: attack precision/recall/F1=0. IF threshold0.47294358:
attack precision1.0000, recall0.4945, F1=0.6618 на данном test.

Результат RF неудовлетворителен для доверенного детектора. Параметры/методика не
подгонялись после просмотра test. Исходный notebook может давать иные, высокие
random-row результаты, но это не доказательство лучшего обнаружения атак.
Внешнее сообщение об Edge placeholder artifacts проверено локально: все603558
attack rows имеют mqtt.protoname/topic/conack.flags token0.0, normal таких token
не имеет. Counts в dataset-audit JSON; core эти label proxies не использует.

Precision/recall/F1 по классам, confusion matrix, macro averages, FPR, PR-AUC
(trapezoid precision-recall curve) и average precision/ROC-AUC сохранены машиночитаемо.
При отсутствии обоих binary классов AUC=null с причиной; FPR=null без normal.
Никакого псевдолейблинга test нет. No fit/threshold tuning при экспорте frozen report.

## Telemetry — DEMO / RESEARCH, без независимых labels

Statistical deployed artifact:320 явно синтетических объектов4 устройств,
feature windows300, split180/60/60, threshold1.0679093578640817. На synthetic test60
alert_rate0.0; quality/F1/precision/recall **не доступны**, поскольку независимой
разметки нет. Отдельный IF telemetry artifact также обучен на тех же320 synthetic records:
train180/validation60/test60,32 trees, threshold0.6044995891, test alert_rate0.0667.
Это не FPR/качество: независимых labels нет. Он не развёрнут; unit tests также
проверяют IF на240 synthetic records3 устройств. Агрегаты обоих артефактов —
[stage6-telemetry-metrics.json](reports/stage6-telemetry-metrics.json).

Ни random publisher, ни sensor threshold rules, ни собственные predictions не
считаются истинными attack labels. Контролируемые MQTT probes проверяют доставку,
временные окна и event identity, а не научную sensitivity модели. Для обоснования
нужны реальные device baselines, режимы/clock quality, независимо подтверждённые
fault/attack интервалы, достаточно normal validation и новый untouched test.

## Инженерные проверки

Отдельно от качества: полный pytest и real Docker MQTT/Mongo/PG/ML smoke,
missing artifact, restart/immutable version, retry при Mongo outage, replay,
crypto ACL/TLS, CSRF/Socket.IO и авторизованный UI. Команды/коды — reports/stage6-*.
Успех этих тестов не является научной метрикой классификации атак.

## Дополнительные датасеты

[ML_DATASETS.md](ML_DATASETS.md): MQTTset — первый кандидат, MQTT-IoT-IDS2020 —
сначала внешний holdout, CICIoT2023 — более широкий domain transfer. Перед merge
нужны единые extractor/schema/observation granularity и проверка license/provenance.
Рост RF на этих данных пока **не проверен**; новых датасетов автоматически не
скачивали, уже просмотренный Edge test для подбора не переиспользуется.
