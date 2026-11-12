# Kuznyechik-MGM: реализация и границы

Реальный AEAD: pinned tarantool/go-gostcrypto, Kuznyechik128-bit block/256-bit key, MGM, фиксированный tag128. Python bridge `src/kuz_provider.py` вызывает статический Go executable через bounded stdin/stdout. Ни сетевого crypto service, ни самописного CTR+MAC, ни FFI/cgo нет.

Provider block KAT и оба MGM examples проверены независимо от telemetry. Другая реализация дала те же bytes на54 сочетаниях длин. Полный tag сравнивается constant-time upstream; ciphertext расшифровывается только после успешного сравнения. На ошибке plaintext отсутствует. Это не означает constant-time всего MGM: branch-dependent multiplication, experimental CT cipher и отсутствие независимого security audit ограничивают применение изолированным software lab.

Сборка: `python -m scripts.build_kuz_provider`; Docker использует pinned Go builder digest. Исходники и лицензия BSD2 сохранены вместе с SHA256 manifest. GPL fork применяется отдельно для cross-check и в runtime не включён. Go>=1.24, CGO0, offline modules; среда x86_64. ARM/Raspberry Pi не проверены. Копии ключа в GC memory не гарантированно zeroized.

Управляемая telemetry использует новый независимый key32B на device/profile/epoch, строгий ICN и durable usage ledger. Сам primitive API не является nonce authority: экспериментальные KAT/benchmark получают отдельные эфемерные ключи, рабочий agent получает signed ranges. Пакет v2 сохраняет AAD и ограничения размера.

Обычный deployment не получает новый live target. Допуск требует test environment, явной lab authorization, stage11 namespace, provisioned capability/key и budgets. Источник verified effective — PostgreSQL receipt принятой AEAD telemetry, не ACK, UI или рекомендация Policy.
