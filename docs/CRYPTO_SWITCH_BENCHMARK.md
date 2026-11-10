# Методика benchmark этапа 8

Команды/цифры будут записаны в reports/stage8-* после фактических прогонов.

scripts.crypto_benchmark: одинаковые64/256/1024byte plaintext/AAD, warmup20,
три повтора с чередованием порядка, bounded iterations. Каждый case — отдельный
process и свежий ephemeral key. Измеряются encryption и authenticated decryption
p50/p95/p99, paired throughput, process CPU и peak RSS. Отдельный authentication-only
cost высокоуровневый AESGCM не раскрывает: decrypt включает проверку tag.

Реальный MQTT/TLS benchmark использует неизменные devices/QoS1/interval, static
Ascon, static AES и новые авторизованные Ascon↔AES transitions. Time-to-ACK и
time-to-effective сохраняются отдельно по PG timestamps, HTTP roundtrip отдельно.
PG→Mongo accepted-count parity — не доказательство отсутствия всех потерянных
publisher messages. Rejected/replay/backlog записываются как наблюдаемые counters.

Сравнение native optimized AESGCM/OpenSSL с pure Python Ascon reference —
сравнение этих реализаций, не чистое свойство алгоритмов. Нет измерений ARM,
энергопотребления, аппаратных сенсоров или 10000devices. CPU/RAM process peak и
Docker snapshots различаются; снимок docker stats не равен peak или интегралу CPU.
Скорость не определяет криптостойкость. ML-качество и криптостойкость не выводятся
из этих экспериментов.
