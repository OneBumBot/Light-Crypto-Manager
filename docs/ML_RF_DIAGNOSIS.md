# Диагностика замороженного RF этапа 6

Baseline не переобучен, threshold и test не менялись. Ветка этапа7.5 начинается
с c9250d8. Диагностический запуск только читает старый fitted pipeline и старые
partition indices: [stage75-rf-diagnosis-v3.json](reports/stage75-rf-diagnosis-v3.json).
Ни старый test, ни его score не используются для выбора новых параметров/признаков.

## Почему порог больше 1

У всех **9 normal validation** RF risk=1.0 (минимум/медиана/максимум одинаковы).
Для атак validation risk quantiles [min,p5,p50,p95,max]=[0,0,0.09375,1,1].
При условии empirical FPR<=0.05 допустимо floor(9*0.05)=0 ложных срабатываний.
Любой порог<=1 помечает все девять normal как attack. Порог nextafter(1,+inf)
выбран корректно относительно этой плохо представительной validation, но отключает
обнаружение. Это не доказанный operating point с population FPR<=5%.

Уменьшить порог — значит скрыть конфликт ранжирования и false positives, а не
исправить модель. RF score не калиброванная вероятность. На сохранённом test
ROC-AUC0.4806/PR-AUC0.6422: низкое качество ранжирования существует отдельно от
нулевого thresholded recall. Test здесь исторический диагностический результат,
не новая цель оптимизации.

## Разделение и покрытие

Prepared11851 из source2219201; после conservative cross-feature duplicate purge
train5630/validation1227/test2005. Group counts2638/220/614, cross-group overlap0.
Группа — bidirectional endpoint-pair hash, не доказанная независимая capture/session.
Train содержит7 из15 категорий; validation14 с normal9, test5; MITM в train нет.
Все распределения классов и frozen feature importances сохранены в JSON.

Baseline RF уже имеет class_weight=balanced,32 trees, seed42. Поэтому добавление
balanced не является само по себе новым исправлением baseline. Нужны отдельные
сравнения с unweighted и balanced_subsample на новом корректном partition plan.
IF fit только1961 normal train. Различие train/validation/test и недостаток normal
важнее немедленного расширения hyperparameter search.

Подтверждённые Edge label proxies: все603558 attack rows имеют token0.0 в
mqtt.protoname/topic/conack.flags, normal такого token не имеет. Эти поля и
сомнительные DNS fields не входят в network-core-v1. Это не полный аудит всех
оставшихся extractor semantics. Source chronology частично утрачена; related
packets одного capture могут пересекать endpoint-pair группы. Duplicate purge
также меняет распределение; отсутствие overlap не доказывает репрезентативность.

## Исторические результаты — не новая оценка

| Модель | Macro-F1 | FPR | Attack recall |
|---|---:|---:|---:|
| RF binary | 0.3328 | 0 | 0 |
| RF multiclass, fixed15 ontology | 0.1373 | отдельная argmax задача | отдельно в исходном отчёте |
| Network IF binary | 0.7296 | 0 | 0.4945 |

RF multiclass по фактическим5 test labels имеет Macro-F1.4119; эти числа нельзя
смешивать с fixed15 .1373 или бинарной risk оценкой. Исходные отчёты этапа6
сохраняются побайтно. Telemetry DEMO также не меняется.

## Предварительно заданное направление

Новый extractor выбирается по TLS наблюдаемости, не по старому test. Capture/session
metadata сохраняются вне X; duplicates/связанные группы не пересекают новые части.
Preprocessing/train weights только на train, threshold/hyperparameters только на
validation, окончательный test после freeze. Без независимых normal captures
полноценный benchmark блокируется, а не заменяется random-row split.

## Уточнение независимости и эффекта purge

| Часть | Строк до purge | Normal до | Строк после | Normal после |
|---|---:|---:|---:|---:|
| Train | 7165 | 2677 | 5630 | 1961 |
| Validation | 2190 | 694 | 1227 | 9 |
| Test (только историческая диагностика) | 2496 | 1000 | 2005 | 1000 |

У оставшихся9 normal validation **одна endpoint-pair группа и один уникальный
canonical feature-вектор**. Это не9 независимых проверок normal traffic.
Conservative feature-duplicate purge удалил685 из694 normal validation, поэтому
сильно изменил распределение. Совпадение числовых признаков ещё не доказывает
копирование одного физического пакета: repeated TCP patterns бывают нормальными.
Нужны capture/packet provenance и отчёт о последствиях очистки. Новый pipeline
сохраняет эту conservative проверку как заранее заданный guard и отказывает,
если после неё недостаточно normal rows/groups; он не объявляет редкую оставшуюся
точку надёжной validation. Для другой dedup методики требуется отдельный заранее
зафиксированный план, а не подбор по старому test.
