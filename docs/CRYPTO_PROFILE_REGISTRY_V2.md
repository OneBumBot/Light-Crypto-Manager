# Crypto Profile Registry v2

Два профиля, без ранжирования «сильнее/слабее»:

| Profile ID | Wire profile/AAD | Key / nonce / tag | Реализация |
|---|---|---|---|
| ascon-aead128-v1 | Ascon-AEAD128 | 16 / 16 / 16 bytes | Существующая Python reference |
| aes-128-gcm-v1 | AES-128-GCM | 16 / 12 / 16 bytes | cryptography 50.0.2 AESGCM |

Telemetry schema_version остаётся 2. Primitive dispatch — crypto_profiles.py,
каталог возможностей — policy/profiles.py. Отдельные признаки server/device/KAT/
software E2E, activation permission и список реализаций. Подтверждён только
python-device-agent-v1, не произвольные физические устройства/ARM.
Конкретные capabilities и fingerprint provisioning закреплены в PG; gamma в
стенде разрешён только Ascon. Профиль в registry сам по себе не даёт разрешение
устройству: проверяются capabilities, ключи, baseline и текущий transition.
Simulation profiles не попадают в IMPLEMENTED и не активируются.

Ascon KAT: существующие независимые ascon-c Counts 1/2/34/35 сохранены.
AES: NIST GCM examples и CAVP CAVS14.0 gcmEncryptExtIV128.rsp, IVlen96/Taglen128,
включая PTlen0/AADlen0 и PTlen0/AADlen128 Count0. Ожидаемые байты фиксированы,
не вычисляются тестируемым encrypt. Источники:
[Ascon reference](https://github.com/ascon/ascon-c/blob/main/crypto_aead/asconaead128/LWC_AEAD_KAT_128_128.txt),
[CAVP vectors](https://github.com/pyca/cryptography/blob/main/vectors/cryptography_vectors/ciphers/AES/GCM/gcmEncryptExtIV128.rsp).
Это проверка реализации, не сертификация системы и не доказательство constant time.

«Магма» и CRISP не реализованы. Их последующее внедрение требует согласованных
спецификаций режима/протокола, key/nonce lifecycle, KAT, реализации обеих сторон,
capabilities, compatibility и recovery. AES-GCM их не заменяет.
