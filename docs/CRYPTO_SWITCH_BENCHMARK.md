# Методика benchmark этапа 8

Команды/цифры будут записаны в reports/stage8-* после фактических прогонов.

scripts.crypto_benchmark: одинаковые 64/256/1024 byte plaintext/AAD, warmup 20,
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
энергопотребления, аппаратных сенсоров или 10000 devices. CPU/RAM process peak и
Docker snapshots различаются; снимок docker stats не равен peak или интегралу CPU.
Скорость не определяет криптостойкость. ML-качество и криптостойкость не выводятся
из этих экспериментов.

## Фактические результаты (source 68c0767)

Docker Python 3.12.16/x86_64, cryptography 50.0.2, AES backend OpenSSL 4.0.3.
Micro:18 cases (2 profiles ×3sizes ×3 repeats), warmup 20 и 300 измеренных пар/case.
Для 256 bytes, среднее p50 трёх повторов:

| Реализация | Encrypt, µs | Authenticated decrypt, µs | CPU ms/pair | Pairs/s | Peak child RSS |
|---|---:|---:|---:|---:|---:|
| Python Ascon reference |387.921|391.351|0.780531|1278.98|26.81 MiB|
| native AESGCM |1.273|1.276|0.002732|365377.25|27.68 MiB|

Это end-to-end вызовы wrapper, включая Python overhead; не оценка intrinsic
сложности/стойкости алгоритма. CPU time включает измерительный loop. Отдельный
MAC verification timing не извлекался из decrypt. Raw64/1024 byte cases иp95/p99
также сохранены: reports/stage8-crypto-microbenchmark.json.

Сеть:3software devices, QoS1/TLS, alpha interval0.5 s, beta/gamma неизменно Ascon.
Три 8-second окна на профиль, warmup 2 s, порядок чередовался. Это повторные окна
одного стенда, не независимые физические устройства/хосты.

| Static profile alpha | Принято PG / найдено Mongo | Среднее window p50 / p95, ms | Наблюдаемая скорость | Max global backlog snapshot |
|---|---:|---:|---:|---:|
| Ascon |46/46|3.823/4.943|≈1.92 msg/s|1|
| AES |46/46|2.625/7.573|≈1.92 msg/s|3|

Не объявляется theoretical48−observed46 потерей: счётчика всех device attempts
нет, генератор планируется обычным software timer. Все 92 committed observations
окон найдены в Mongo. В окнах 0 наблюдаемых replay и 0global anonymous rejected;
это не оценка real attack detection/FPR. Backlog snapshot не равен потерям.
Window p50/p95 усредняются, а не выдаются за pooled percentile.

Четыре новых авторизованных перехода:

| Направление | Intent→effective, ms | ACTIVATE authorization→ACK receipt, ms | ACTIVATE authorization→verified telemetry, ms |
|---|---:|---:|---:|
| AES→Ascon |525.819|83.127|413.468|
| Ascon→AES |228.476|82.217|100.243|
| AES→Ascon |277.922|82.747|222.118|
| Ascon→AES |281.980|82.356|155.900|

Среднее intent→effective328.549 ms, диапазон 228.476–525.819 ms; n=4 слишком мало
для надёжной tail/generalization оценки. PG timestamps означают серверную выдачу
ACTIVATE intent, не точный сетевой TX timestamp и не hardware switching latency.
HTTP polling elapsed хранится отдельно в integration reports.

CPU/RAM Docker snapshots всех static окон сохранены raw; например первый Ascon
snapshot alpha7.75%,22.26 MiB, AES0.26%,21.93 MiB. Короткие snapshots шумны и не
являются средним/peak. Kernel VmHWM Python agent после всего benchmark40984 kB,
CPU 1.06 s за 402.84 s жизни процесса (~0.263% одного ядра), включая boot/warmup.
Изолированный transient switching CPU/peak RAM по этим данным не определяется;
измерения не приписываются отдельно только Ascon/AES.

После benchmark исправлена только обработка metadata позднего ACK (282a49f):
confirmed_at/effective_event не меняются, принятый late ACK теперь заполняет
reported_profile/acknowledged_at. Это не пересчёт/подбор опубликованных измерений.
Все первоначальные benchmark reports сохранены, source pinned68c0767.
