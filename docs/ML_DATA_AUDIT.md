# Аудит исходных ML-экспериментов — этап 6

Исходная база: cfda660, ветка feature/ml-inference-pipeline. Это аудит кода и
доступности данных, **не результат обучения и не завершение этапа 6**.
Notebook сохранён побайтно. Все 13 ячеек прочитаны; они синтаксически корректны,
но не исполнялись: исходный CSV отсутствует. Saved outputs отсутствуют, у всех
ячеек execution_count=null. Поэтому воспроизвести качество по notebook нельзя.

SHA-256 `src/classifier/iot-test.ipynb`:
`dd25b44ab0b53ab087c76c861c6f85d58980bc325c1fbac9134a78b4d368432b`.
Повторяемая структурная проверка: scripts/audit_ml_notebook.py; протокол —
[reports/stage6-audit.txt](reports/stage6-audit.txt).

## 1. Происхождение и доступность

Notebook ищет ровно DNN-EdgeIIoT-dataset.csv рекурсивно в /kaggle/input, затем
читает pandas.read_csv(low_memory=False). Это Kaggle-specific путь. Версия файла,
SHA-256, число строк/устройств, фактический список колонок и распределение классов
в коде не фиксируются. При нескольких одноимённых файлах выбор не гарантирует
явно указанную версию; внутренний break не завершает внешний os.walk.

Создатели Edge-IIoTset: Ferrag, Friha, Hamouda, Maglaras, Janicke; описание:
[IEEE Access, 2022, DOI 10.1109/ACCESS.2022.3165809](https://doi.org/10.1109/ACCESS.2022.3165809).
Статья описывает набор протокольных признаков, а не поток temperature/humidity
нашего publisher. Первичное определение Attack_label: 0 — normal, 1 — attack;
Attack_type — категория. См. также [страницу авторского датасета](https://www.kaggle.com/datasets/mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot).

Локально в исходниках не обнаружены CSV/parquet/model artifacts (поиск исключал
.venv, .cache, .local-runtime, .local-baseline и вложенную историю Git). В Git
исходного этапа нет датасета/моделей. Приватные runtime volumes не экспортировались
для аудита и не рассматриваются как размеченный набор для обучения.

| Свойство локального DNN-EdgeIIoT источника | Фактический статус |
|---|---|
| Файл / версия / SHA-256 | отсутствует / неизвестно / вычислить невозможно |
| Число объектов и устройств | не проверено |
| Фактические колонки / dtype / missing / infinity | не проверено |
| Временной диапазон, session/device/flow attribution | не проверено |
| Частоты Attack_label / Attack_type, соответствие между ними | не проверено |
| Условия использования конкретного CSV | не подтверждены |
| Качество RF / IF на реальном наборе | не воспроизведено |

Страница Kaggle не отдала читаемые условия лицензии при проверке. Apache2.0
у [авторского preprocessing notebook](https://www.kaggle.com/code/mohamedamineferrag/edge-iiotset-pre-processing)
не доказывает ту же лицензию данных; лицензия статьи также не переносится на CSV.
Автоматическое скачивание/распространение набора и моделей не выполнялось.
При получении данных сохранить их исходные условия использования отдельно вместе
с manifest; при неподтверждённой лицензии не публиковать данные/веса.

## 2. Разбор каждой ячейки

Номера строк относятся к физическому JSON notebook: source хранится одной строкой;
номер ячейки удобнее для проверки кода в Jupyter.

| Ячейка / строка | Действие | Вывод |
|---|---|---|
| 1 / 42 | imports pandas/numpy/sklearn/matplotlib/joblib | StandardScaler импортирован, но не используется; версии не закреплены в notebook |
| 2 / 60 | поиск CSV, read_csv, head | Нет явного пути/manifest/schema; отсутствующий файл вызывает FileNotFoundError |
| 3 / 76 | drop15 columns, dropna, drop_duplicates | Удаляются потенциальные split-идентификаторы до разделения; очистка без отчёта по причинам |
| 4 / 92 | head(5) | Только просмотр, не проверка схемы |
| 5 / 108 | Attack_type LabelEncoder, Attack_label | Encoder обучен на всех labels; фактическая разметка не валидируется |
| 6 / 124 | удаление обоих targets из X_df | Прямые target-колонки в X не включены; это не устраняет косвенные label proxies |
| 7 / 140 | get_dummies7, to_numeric(coerce), fillna(0), .values | Категории определяются по всему набору; скрываются ошибки типов, теряются имена/порядок schema |
| 8 / 156 | два random stratified train_test_split 80/20, seed42 | Нет validation, групп, времени; бинарный и multiclass split не обязаны совпадать |
| 9 / 172 | RF50 trees, fit/predict, accuracy/report/confusion, dump | Только estimator; нет pipeline/schema/class mapping/версий/hash/порога/manifest |
| 10 / 188 | multiclass RF | Название 15-Class не является проверкой фактических 15 категорий |
| 11 / 204 | binary RF | Порядок Normal/Attack предполагается, а не проверяется по данным |
| 12 / 220 | IF100 trees, train[y==0], contamination=auto, predict | Выбор normal соответствует определению binary label; actual CSV надо проверить отдельно |
| 13 / 236 | запуск IF на бинарном split | Знаки +1 normal / -1 anomaly преобразованы в0/1 корректно; validation threshold отсутствует |

## 3. Какие признаки использует notebook

Окончательного списка и порядка **нет**: выбираются все оставшиеся CSV колонки,
кроме Attack_label/Attack_type. При добавлении постороннего столбца он тоже попадёт
в X. До чтения CSV нельзя достоверно назвать фактическую размерность X, типы,
категории и порядок dummy-колонок. Будущий pipeline должен использовать allowlist.

Объявленный drop-list (ячейка3):

```text
frame.time, ip.src_host, ip.dst_host, arp.src.proto_ipv4,
arp.dst.proto_ipv4, http.file_data, http.request.full_uri,
icmp.transmit_timestamp, http.request.uri.query, tcp.options,
tcp.payload, tcp.srcport, tcp.dstport, udp.port, mqtt.msg
```

Объявленные categorical columns (ячейка7):

```text
http.request.method, http.referer, http.request.version,
dns.qry.name.len, mqtt.conack.flags, mqtt.protoname, mqtt.topic
```

Остальные surviving columns преобразуются в числовые без явного списка и диапазонов.
Это могут быть TCP flags/length/ack/sequence/checksum, ARP/ICMP поля, UDP stream/time,
DNS параметры, MQTT flags/length/type/version и Modbus поля, если они присутствуют
в конкретном CSV. Это описание семейств, не подтверждённая локальная схема.
`dns.qry.name.len` и `mqtt.conack.flags` нельзя объявлять категориальными только по
виду CSV строки: сверить семантику и нормализовать числовые представления.
Остаточные текстовые значения вне семи категорий при coerce могут молча стать0.

## 4. Утечка и методические проблемы

1. get_dummies применяется до split: словарь категорий включает test. Это
   transductive leakage схемы, хотя код непосредственно не передаёт test labels
   в classifier.fit. Его нельзя описывать как доказанную прямую утечку target.
2. Точный dedup выполняется после удаления time/IP/ports/payload и с учётом обеих
   label-колонок. Разные записи могут схлопнуться; одинаковые X с разными labels
   остаются. Соседние/связанные записи и один flow могут оказаться в обеих частях.
   Даже отсутствие точных duplicate не доказывает независимости train/test.
3. Random row split игнорирует capture/device/session/flow/time. Идентификаторы
   нельзя удалять до построения leakage-safe partitions: хранить их как metadata,
   исключая из predictive features. Проверять overlap групп/feature fingerprints.
4. LabelEncoder fitted на всех категориях использует знание пространства test
   labels, хотя labels исключены из X. Будущие правила class mapping должны быть
   явными; unseen test classes нельзя молча добавлять в train mapping.
5. dropna по всем колонкам изменяет class balance; статистики до/после нет.
   fillna(0) после coerce смешивает missing, невалидный token и реальное0. Infinity,
   boolean-vs-number и допустимые диапазоны не проверяются.
6. Validation-набора нет; нельзя выбирать параметры/порог по final test.
   IF contamination=auto задаёт технический порог без калибровки FPR на validation.
   Для RF тоже нет воспроизводимого validation-selection протокола.
7. classification_report даёт precision/recall/F1 и macro average, confusion matrix
   есть. Основной вывод строится вокруг accuracy; FPR, PR-AUC/ROC-AUC, score ranking,
   prevalence и ограничения отсутствующих классов не фиксируются.
8. Сохраняется estimator, но не encoder/preprocessing/schema/feature order. Повторный
   get_dummies на другом наборе не обеспечивает совместимость inference.
   StandardScaler не был fitted: нельзя приписывать ему утечку в этом notebook.

Дополнительный внешний риск: [Galal, arXiv2608.15761v1](https://arxiv.org/abs/2608.15761v1)
сообщает о label proxy в представлениях отсутствующих полей (0 против0.0) в
`dns.qry.name.len`, `mqtt.conack.flags`, `mqtt.protoname`, `mqtt.topic`.
Это исследовательский препринт; результат на нашем локальном CSV не проверен,
поскольку CSV отсутствует. Замена one-hot на другой encoder сама по себе не
устраняет provenance artifact. Нужны train-side аудит токенов/семантическая
нормализация или обоснованное исключение полей, затем замороженная методика.
Нельзя экспериментировать с исправлениями до тех пор, пока final test не станет
«хорошим»; при переиспользовании test нужен новый независимый holdout.

## 5. Доступность признаков в LightCrypto Manager

| Источник / файлы | Доступно | Чего это не подтверждает |
|---|---|---|
| publisher mqtt_pub.py:78 | независимые случайные temperature/humidity и UTC timestamp | Нет packet/flow признаков Edge-IIoTset и реалистичного normal baseline |
| telemetry.py:49,107 | validated sensor; authenticated device/epoch/sequence/topic binding | Нет IP/TCP/UDP/DNS/HTTP/Modbus capture данных |
| ingestion.py:26 | verified packet, PG configuration, replay, прежние пороги и delay | Порог temperature>60 / humidity>70 / delay>0.5s — не ML ground truth и не доказательство атаки |
| outbox.py:49 | device/epoch/sequence/profile, измерение, время приёма | Outbox содержит только проверенную телеметрию, не сетевой flow |
| mongo_repository.py:22,70 | UTC history с устройством и стабильной identity | received_at — приём ingestion, не время Mongo доставки |
| MQTT callbacks / metrics | topic/QoS/повторы и агрегаты входящих/reject/replay | Эти данные не равны датасетным frame/flow features без одинакового collector contract |

Topic технически известен приложению, но это ещё не воспроизводимый источник
всего IDS feature vector. TLS скрывает application payload от пассивного внешнего
наблюдателя; AEAD sensor-plaintext доступен только после допустимого расшифрования.
В текущем проекте нет PCAP/TShark/Zeek collector. Нельзя подставлять температуру
в TCP feature или считать отсутствие таких полей нулями для «online IDS».

## 6. Разделение будущих экспериментов

**Network IDS**: только offline RF binary/multiclass и IF до появления совместимого
collector. Явная схема признаков, provenance, split metadata; train/validation/test
по надёжным группам/времени с purge. Если таких metadata нет, не имитировать их
хешем произвольной строки: признать ограничения и не заявлять device/session holdout.
Проверять фактическое соответствие Attack_label0 ↔ Attack_typeNormal; противоречия
не исправлять автоматически. Нельзя объявлять fixed15 классов без manifest.

**Telemetry anomaly**: отдельный DEMO/RESEARCH baseline, per-device история.
Temperature/humidity, предыдущие значения, deltas, trailing mean/std, отклонение от
train-only индивидуального baseline, интервалы и expected-period gaps.
Статистики для событияt вычисляются из доступной на тот момент истории; будущее
и текущий тестовый ответ не участвуют в fit baseline/scaler/threshold.

Учитывать разницу measured_at и received_at: сортировка по measured_at задним числом
не доказывает отсутствие future leakage. Поздние/out-of-order документы, одинаковые
времена, epoch/sequence identity, незнакомые устройства и warm-up требуют явных
правил. Проверки пропуска сообщения без следующего поступления требуют таймера,
а не только разности соседних timestamps. Отклонение физического сенсора, поведения
устройства, сетевой атаки и криптографического нарушения — разные типы сигналов.
Существующие anomaly causes и модельный прогноз не являются достоверной разметкой
для precision/recall/F1 на немаркированной истории.

Общая подготовка train/inference: sklearn Pipeline/ColumnTransformer;
fit imputer/scaler/encoder только train; unknown-category policy; постоянные порядок
и версия схемы; model+transformations+manifest+dependency versions вместе.
См. [sklearn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html).
Model artifact из pickle/joblib можно загружать только из доверенного источника,
поскольку десериализация исполняет код; неизвестный artifact не является просто CSV.

## 7. Какие реальные данные ещё необходимы

- Достаточная длительность нормальной истории отдельных устройств, реальные
  режимы работы/допуски, интервалы, калибровка сенсоров и достоверные UTC часы.
- Идентифицированные периоды faults/обслуживания и независимые экспертные метки,
  временные границы, проверка drift/seasonality и контроль ложных тревог.
- Для IDS — разрешённые raw captures/совместимые extractors и достоверные
  device/session/capture/flow связи, версии extraction и семантика missing tokens.
- Для каждого файла: explicit source/license/version/SHA-256, row/device counts,
  time range, types, class balance, cleaning report и неизменяемый split manifest.

В этом блоке нет новых моделей, метрик классификации и синтетических «результатов
Edge-IIoTset». 210 тестов остаются результатом предыдущего этапа, здесь не
перезапускались: runtime код не менялся. Зафиксирован только аудит и его проверки.
Продолжение задания получено после первичного аудита. Дальнейшая реализация и
фактические проверки фиксируются отдельно в документации этапа6.
