# Ground truth сетевых наблюдений

Версии: experiment schema1, `lcm-tshark-tcp-v1`, `tcp-packet-passive-v1`.
Предиктивные поля не менялись. Нет capture-wide метки атаки.

1. Orchestrator сохраняет experiment config, независимый ID, UTC start/end.
2. Paho callbacks регистрируют PID, opaque client ID, connection UUID,
   local/remote IP/port, открытие TLS socket, закрытие и результат CONNACK.
3. tshark экспортирует исходные frame number/time, tcp.stream и tuple. Требуются
   захваченный SYN, единственное соответствие записи сокета и один tuple потока.
   Повторно использованный tuple в пределах capture не угадывается: unknown.
4. Разметка возможна внутри `[TLS_open + margin, close - margin]`, с подтверждением
   активности. Для normal дополнительно требуется PG accepted для устройства в
   данном запуске. Для нарушений нужны основания из EXPERIMENT_SCENARIOS.
5. Все остальные пакеты остаются unknown/ambiguous. В observations.csv они есть,
   но в бинарном dataset.csv их нет. Нельзя заменять неизвестное label0.

Kernel PCAP timestamps и Python CLOCK_REALTIME используют часы одного Docker
host, без отдельного time namespace. Логируются разрешение clock, расхождение
wall/monotonic за запуск, margin=max(50µs,2×расхождение). Это **консервативный
инженерный интервал**, не измеренная абсолютная точность и не гарантия соответствия
UTC эталону. NTP jumps >5ms по порядку timestamps приводят к quarantine; небольшая
межпоточная перестановка kernel capture учитывается счётчиком reorder, не меняя
порядок tshark/tcp.time_delta. До исследования на разных хостах нужна независимая
проверка синхронизации/дрейфа. Внешний packet time сам по себе не основание метки.

Rejected credentials не подтверждают logical_device. Такое имя используется
только во внутреннем журнале actor, колонка authenticated_device остаётся пустой.
У tamper серверный reject остаётся анонимным: локальная проверка повреждения и
один контролируемый actor дают лабораторную связь, а aggregate PG reject — лишь
корроборацию. Это слабее серверного per-packet authenticated audit; при постороннем
invalid traffic такую связь нельзя считать доказанной.

Пакеты normal QoS1 retransmission остаются normal, даже если ingestion корректно
отклонил повторную запись. RESEARCH ML, security rejection и подтверждённая атака
не тождественны; результаты не поступают в live Policy Engine.

PCAP и приватные socket tuples не публикуются. В manifest сохраняются хэши PCAP,
header CSV, journal, broker allowlist и core snapshot. Validator может повторно
проверить все исходные хэши (`--captures`). Manifest не является цифровой подписью:
он обнаруживает изменение относительно сохранённой версии, но не защищает от
злонамеренной перезаписи доверенным владельцем хранилища.

## Исправление 7.5b-fix — текущий контракт

Предыдущая схема выше — архивная75b-v1; её packet_audited не является доказательством
malicious packet ground truth. Новая connection-evidence-v2.2 отделяет scenario,
connection/window activity и packet-specific evidence (последнее none под TLS).
Критерии/источники — [LABEL_SEMANTICS.md](LABEL_SEMANTICS.md), независимый oracle —
[GROUND_TRUTH_VERIFICATION.md](GROUND_TRUTH_VERIFICATION.md).

Без timed session evidence старый архив полностью unknown в новой версии:
33848known→unknown, итог46395unknown; исходники/план не перезаписаны. Новый probe
имеет отдельные broker lifecycle/MID/DUP, read-only PG events и keyless encrypted
payload digest witness. Anonymous AEAD reject не получает device identity.
Broker clock/log latency не имеет внешнего метрологического эталона; успешный
reconciliation не означает100%label accuracy и не оценивает качество RF/IF.
