# Проверки качества исследовательского набора

Команда `src.research_stand.dataset build` создаёт:

- `observations.csv`: все mapped/unknown TCP headers, source/capture/experiment/
  session/packet IDs, UTC epoch, connection provenance, direction, scenario,
  label confidence/source/reason и source PCAP hash; без payload/credentials.
- `dataset.csv`: только verified normal0 / ControlledViolation1; unknown исключены.
- `dataset.manifest.json`: SHA-256 outputs/inputs, версии extractor/schema/tools,
  конфигурации и показатели каждого capture, список quarantined sources.
- `validation.json`: распределения, normal/violation/unknown counts, class capture
  support, повторные/конфликтующие feature vectors и оговорки shortcut learning.

Проверяются source hashes, PCAP/header count, linktype Ethernet1, известный нулевой
kernel drop counter, завершённость generator, отсутствие ошибок/превышения capture
limits, bounded sizes, physical packet/connection uniqueness, конечность timestamps,
clock backstep, все5 numeric features с диапазонами прежней схемы. Отсутствующие
значения не превращаются в0. Первый `tcp.time_delta=0` — значение tshark для первого
пакета соединения, не imputation. Небольшие глобальные packet reorder фиксируются;
`tcp.analysis.lost_segment` отдельно от реальной статистики kernel drops.

`validate --captures PATH` повторно читает исходные файлы и сверяет все input hashes.
Без --captures проверяются output hashes и prepared schema, но не доступность PCAP.
Сырые IP/ports используются только для mapping и не попадают в prepared predictors.
Feature order строго `frame.len,tcp.len,tcp.flags,tcp.window_size_value,tcp.time_delta`.
Source metadata никогда не входят в модель, MQTT/TLS не расшифровывается.

После валидации применяется прежний `prepare_split`: capture-level SGKF5 60/20/20,
каждый класс≥5 независимых capture groups в каждой части, normal≥1000 в каждой,
без случайного split строк и без ослабления поддержки. Все exact feature fingerprints,
пересекающие части, удаляются с отчётом об изменении распределения. Capture/session
intersections запрещены. Неоднозначная независимость устройств остаётся отдельной
оговоркой, даже если capture IDs различны.

Shortcut review: paired normal/mixed configurations, общий пул устройств, разные
seeds/intensities, normal background внутри mixed captures, одинаковая точка
сбора и versions. Считаются одинаковые/конфликтные vectors и feature distributions.
Это **не доказывает отсутствие shortcut learning**: короткие ACL/auth connections,
одинаковый TCP stack и loop scheduling могут давать простую лабораторную эвристику.
В 7.5c нужны per-scenario ablations, held-out host/device/stack, независимые реальные
источники и проверка normal traffic в иных условиях. Отсутствие показателей RF/IF
на этом этапе намеренно: инженерный успех не является quality metric IDS.

## Фактическая курация до обучения

Первая матрица60 captures обнаружила протокольные shortcuts: неверный пароль был
длиной33 вместо48 символов, запрещённый topic — другой длины. Эти10captures
сохранены, но исключены явным `selection.json` с capture ID, исходным PCAP SHA256 и
причиной. Новый wrong password имеет длину48 и заведомо не соответствует hex
credentials; denied topic `iot/sensors/lab000` имеет ту же длину, что и разрешённый.
Повторены10сценариев без изменения normal background/config/seed. Новые captures
собраны позже отдельной batch; такой остаточный фактор времени/нагрузки отмечен
как ограничение, отсутствие shortcuts не доказано. На свежем стенде исправление
действует с самого начала, специальная курация не нужна.

Для существующего сбора команда build использовала
`--selection .local-runtime/stand75b/selection.json`. Она не удаляет исходники,
проверяет hash каждого исключённого PCAP, сохраняет причины в manifest. Это
предварительная очистка ошибочных условий эксперимента, не отбор по ML-метрикам.
`primary-a-20-n` помещён в quarantine: отрицательный tcp.time_delta, значение не
исправлялось/не округлялось до0. Итог59captures; строгий plan прошёл без послаблений.

Builder ограничен100000 observations суммарно и100captures, не обрезает молча.
Большие объёмы требуют отдельного streaming решения; не увеличивайте лимит ради
обхода ограничений памяти. Для жёстких CPU/RAM ограничений offline обработки
допустим отдельный контейнер tests image с `--network none --cpus 1 --memory 768m`,
с private input mount и user UID/GID владельца данных, без DB/MQTT credentials.

## Текущая независимая проверка 7.5b-fix

Старые SHA checks выше не сверяли полностью сохранённые labels с источниками:
coherent-hash normal→violation подмена действительно проходила. Теперь validate
с raw path dispatch по label_rules_version: v1 — отдельная historical reconciliation
без scientific attestation, v2.2 — независимый per-packet oracle. Для v2 без raw
sources валидация labels запрещена. Missing/extra/foreign IDs, изменённые labels,
connection/reason/time/capture, unknown promotion и header stream spoof отвергаются
даже при согласованных производных hashes/counts. Исходный PCAP отдельно сверяется
с headers.csv по wire/sequence/stream/length/flags/window/time; whole-file RAM нет.

Старый build воспроизводится только с --archive-v1. По умолчанию создаётся v2;
legacy --selection без этого флага отвергается, не игнорируется. Для архивной
переразметки используйте dataset_v2 --parent-manifest, который сохраняет source
selection и parent hashes. Новый путь обязателен. Любая версия label semantics
отделена от неизменной tcp-packet-passive-v1 feature schema.

Все исходные файлы7.5b сохранены. Original split/purge не менялся; repeated
packet_id0 не доказывает отсутствие duplicate wire capture. Exact feature equality
не является physical duplicate. После старого purge нет positive replay/pattern
в test и bad_credentials/bounded_rate в validation. Seed-pairs пересекают части
7/9/2раза; риск связанных условий не исчезает при capture disjointness.

Новая archived reannotation:0known groups; небольшой real probe:normal9/positive5
capture groups. Оба plan отклонены с exit2; thresholds не ослаблены, планы не
созданы. Внешняя label accuracy и real IDS metrics остаются unproven.
