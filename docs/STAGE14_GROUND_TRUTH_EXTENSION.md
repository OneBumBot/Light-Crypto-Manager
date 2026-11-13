# Stage14 ground-truth extension

Новые данные получены после preregistration:9 pilot captures и60 primary captures в30 новых broker/CA/device-state/PG/Mongo realms. Один проект за раз,6 software clients/capture,12s primary duration; фактические sent counts/packet counts/границы записаны, configured rate не выдаётся за measured. Host/OS один, физических IoT нет. Коллектор eth0 namespace устройств видит исходные TCP/TLS соединения; MQTT observer работает отдельно и не получает Ascon keys.

Primary:35203 TCP observations,27969 normal,1894 ControlledViolation,5340 unknown (15.169%).424 connections имеют хотя бы одну corroborated row:396 normal,28 violation.2 TCP sessions полностью без known rows; boundary-unknown rows также встречаются в известных соединениях. Это не1894 независимых атак.60 PCAP SHA уникальны и не совпадают с историческими источниками.

Pilot:3781 observations,2726 normal,202 violation,853 unknown;55 normal/4 positive row-supporting connections. В pilot bad_credentials брокер подтвердил denial, но ни один наблюдённый packet не попал внутрь50us-margin activity window. Primary имеет всего7 eligible bad-credential rows из4 connections; validation positive support этого сценария отсутствует. Границы не ослаблены. Tamper pilot actor остаётся unknown: aggregate anonymous reject не является packet/device attribution.

Known activity требует broker-auth/session/ACL или timed accepted+non-DUP replay+independent ciphertext witness+PG replay. Rate/pattern проверяются по реальным publish intervals и normal peers, а не имени сценария. QoS1 retry сохраняет normal semantics. PG accepted/Outbox/Mongo и broker PUBACK различаются. Данные исключительно Ascon telemetry текущего Research Stand, не скрытая оценка AES/Kuz transfer.

Все PCAP/CSV/full journals/models остаются в .local-runtime/stage14 (700/600), вне Git/images. Public reports содержат hashes/config/агрегаты/метрики, не ciphertext/keys/raw captures. Исторические70 primary PCAP,59 выбранных/46395 unknown-after-fix и старый frozen plan не использовались как новая class support.
