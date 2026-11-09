# Random Forest vs Isolation Forest — результаты, которые можно подтвердить

## Исторический Edge baseline (не новый эксперимент)

Frozen source2219201, selected11851, train5630/validation1227/test2005 после purge.
RF fit5630, IF fit1961 normal. Validation normal9 из1 группы/1 feature-pattern;
train7 из15 категорий, MITM unseen. Ограничения не устранены переименованием опыта.

| Метод / scope | Attack precision | Attack recall | Attack F1 | Macro-F1 | Balanced accuracy | FPR | PR-AUC / ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| RF binary, threshold>1 | 0 | 0 | 0 | 0.3328 | 0.5000 | 0 | 0.6422 /0.4806 |
| IF binary | 1.0000 | 0.4945 | 0.6618 | 0.7296 | 0.7473 | 0 | 0.8544 /0.7164 |
| RF multiclass, fixed15 ontology | разные per-class значения | отдельная задача | отдельная задача | 0.1373 | не смешивается с binary risk | — | отдельный binary ranking |

Binary confusion RF:[[1000,0],[1005,0]], IF:[[1000,0],[508,497]], rows normal/attack.
Balanced accuracy вычисляется из уже сохранённых specificity/recall; нового fit,
подбора или пересмотра старого test нет. FPR0 при RF не означает полезный детектор:
он не выдаёт тревог вообще. Нельзя обобщать превосходство IF на другой источник.
Multiclass argmax FPR1.0 и Macro-F1 на5 фактических labels.4119 — иная область,
не fixed15 .1373 и не thresholded risk. Оригинальные reports/stage6-* неизменны.

## Новая матрица — реализована, но не исполнена на пригодных реальных данных

Полная конфигурация configs/ml/research75.json, seed75, CPU n_jobs1:

| Метод | Заданные параметры | Реальный scientific fit/test |
|---|---|---|
| RF новый baseline |100 trees, depth=None, split2/leaf1, sqrt, без class_weight | не выполнен |
| RF balanced | тот же, class_weight=balanced | не выполнен |
| RF balanced_subsample | тот же, balanced_subsample | не выполнен |
| Tuned RF0 |100 trees, depth16, split4/leaf2, sqrt, balanced | не выполнен |
| Tuned RF1 |200 trees, depth32, split8/leaf4, max_features0.8, balanced_subsample | не выполнен |
| IF baseline |100 trees, max_samples256, max_features1, no scaling | не выполнен |
| IF standard |100/256/1, StandardScaler | не выполнен |
| IF tuned0 |200/1024/0.75, no scaling | не выполнен |
| IF tuned1 |200/256/0.5, RobustScaler | не выполнен |

5 RF configurations ×binary/multiclass +4 IF =14 planned fits. Это небольшой
prespecified search, не полный факторный анализ независимого влияния параметров.
IF fit только normal train; contamination=auto не оценка attack prevalence.
Все transforms включены в exported Pipeline. Scalers сравниваются как отдельные
варианты; положительные affine scaling для tree splits не обязаны улучшать IF.

Все новые metric cells — **N/A, не0**. Причины: raw sample14501 содержит1 attack
capture/0 normal, full listing только1 normal capture, reduced330926 не имеет
provenance. Исторический RF уже balanced; его нельзя выдавать за новый unweighted
baseline на той же задаче. Новые5 features несовместимы с его30-column schema.

## Измеренная вычислительная стоимость baseline

Frozen **validation**,1227 rows; по64 single-row calls/model, batch256. Команда и
точные версии — reports/stage75-cost.txt, reports/stage75-baseline-cost.json.
Схема network-core-v1,32 trees. Никаких training/test selection действий.

| Fitted model | Single inference p50/p95/p99, ms | Batch throughput, rows/s |
|---|---:|---:|
| RF binary |6.001/6.130/6.326 |35760 |
| RF multiclass |6.036/6.095/6.121 |35511 |
| IF |6.153/6.216/6.386 |34811 |

Это небольшой snapshot общего x86_64 development host, включает schema validation
и preprocessing; не network throughput и не performance гарантия. Tiny различия
между моделями не доказательство преимущества. Cumulative process peak RSS174156KiB
(~170MiB) включает Python/libs/data и не является отдельной памятью каждой модели.
Время старого обучения/preprocessing fit не измерялось — N/A. Для новых моделей
fit/preprocessing/latency/throughput/RSS измеряются кодом, но на реальных данных
они сейчас N/A. ARM64/Raspberry Pi, CPU/RAM/energy под нагрузкой не проверены.

## Что пригодно для диплома

Сводная таблица честно показывает методический отказ RF на старой validation,
ограниченную историческую IF оценку, реальные inference costs baseline и отсутствие
подтверждённого нового benchmark. Новое число F1 не создаётся из синтетической
фикстуры или статьи авторов. Библиотеки/команды/hashes/counts и blocked statuses
сохранены в машиночитаемых reports/stage75-*.json/txt.

## Исторические ошибки по типам атак (read-only diagnosis)

Frozen threshold и weight files не менялись. Новая таблица только детализирует
сохранённые результаты старого test; она не используется для выбора новых
features/parameters. Источник: stage75-rf-diagnosis-v3.json.

| Тип / old test count | RF binary recall / FN | IF anomaly recall / FN |
|---|---:|---:|
| DDoS_ICMP /388 |0 /388 |0 /388 |
| DDoS_TCP /177 |0 /177 |0.6271 /66 |
| DDoS_UDP /47 |0 /47 |0 /47 |
| MITM /393 |0 /393 |0.9822 /7 |

IF не видел ни одной атаки при fit; MITM также отсутствовала в supervised RF train.
Высокий MITM recall внутри этого ограниченного split не доказывает переносимость
на новый capture/source и не означает, что IF распознаёт тип MITM. IF полностью
пропустил ICMP/UDP атаки, поэтому aggregate recall.4945 нельзя выдавать за равномерное
покрытие атак. RF multiclass binary risk при threshold>1 тоже не выдаёт сигналов;
его argmax type predictions — отдельная задача.
