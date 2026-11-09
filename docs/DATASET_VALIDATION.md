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
