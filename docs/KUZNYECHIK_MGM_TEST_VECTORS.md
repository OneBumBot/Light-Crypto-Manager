# Независимые test vectors

Источники: [RFC7801 §§5.4–5.6](https://www.rfc-editor.org/rfc/rfc7801), [RFC9058 AppendixA.1](https://www.rfc-editor.org/rfc/rfc9058#appendix-A.1). Точные публичные hex bytes находятся в `tests/test_kuz_provider.py`; все10 round keys — в `third_party/go-gostcrypto/kuznyechik/lcm_rfc7801_test.go`.

- Kuznyechik: fixed key32B, plaintext `1122334455667700ffeeddccbbaa9988`, expected block `7f679d90bebc24305a468d42b9d4edcd`; decrypt проверяется отдельно.
- MGM A.1.1: ICN16B, AAD41B, plaintext67B; точные ciphertext67B и tag `cf5d656f40c34f5c46e8bb0e29fcdb4c`.
- MGM A.1.2: другой key, тот же ICN, AAD16B, пустой plaintext; tag `7901e9ea2085cd247ed249695f9f8a85`.

Negative tests меняют key/nonce/AAD/ciphertext/tag, укорачивают/удлиняют tag; требуют конкретный ValueError и отсутствие возвращённого plaintext. Неверные размеры, MSB1 ICN, неправильные типы всех параметров, оба пустых входа, максимальные размеры/частичные блоки проверяются отдельно. Недоступный executable требует ProviderUnavailable, а не normal invalid packet.

Независимый cross-check: отдельный GPL fork executable, pinned revision в provider selection; 54 сочетания P0..4096B/AAD0..1024B, включая partial blocks. Полное побайтовое совпадение ciphertext/tag и108 отказов invalid tag. Эфемерные ключи в отчётах отсутствуют. Published vectors подтверждают соответствие алгоритму на проверенных входах; это не независимый security audit.
