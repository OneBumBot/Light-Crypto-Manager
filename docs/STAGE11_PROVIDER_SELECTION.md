# Stage 11: выбор криптографического provider

Исходный код проекта: `d226fbc56068caa5a2685d31a89eb0c85f8efe4c`; ветка `feature/kuznyechik-mgm-integration`. Новые результаты относятся к рабочим изменениям этой ветки, а не к неизменённому baseline. Baseline на отдельном `lcm-stage11-kuznyechik-baseline`: 739 passed, exit 0.

| Реализация | Проверенные свойства | Решение |
|---|---|---|
| tarantool/go-gostcrypto `3791d459e0c35d051a691a3bd3a4a69f671258f5` | Kuznyechik `NewCipherCT`, MGM Seal/Open, полный tag16; BSD-2-Clause; Go>=1.24; нет внешних dependencies | Выбран для **явно разрешённого изолированного software validation**, не production |
| drobotun/gostcrypto `60d5338553a61c9dd9cbe70bc3a96dd253a84630` | Python Kuznyechik; MIT; режимы ECB/CBC/CFB/OFB/CTR/MAC | Нет готового MGM API, не выбран |
| gost-engine/engine | OpenSSL engine, отдельная сложность ABI/build; полнота пригодного MGM API в этом исследовании не установлена | Не выбран, не выдаётся за проверенный MGM provider |
| pedroalbanese/gogost `44a1f1ec2524a739e2fb8032aab96371052124ef` | Независимый Kuznyechik/MGM, GPL-3.0, отдельный проверочный executable | Только cross-check; не vendored/linked в runtime. Канонический git.cypherpunks.su недоступен; проверен именно указанный fork |

Источники: [RFC7801](https://www.rfc-editor.org/rfc/rfc7801), [RFC9058](https://www.rfc-editor.org/rfc/rfc9058), [выбранный upstream](https://github.com/tarantool/go-gostcrypto), [независимый fork](https://github.com/pedroalbanese/gogost). Значения из RFC проверяются побайтно, roundtrip не заменяет KAT.

Vendored subset `third_party/go-gostcrypto/PROVENANCE.json` содержит SHA256 каждого upstream-файла. Локальный `lcm_rfc7801_test.go` — дополнительный тест, явно не upstream. Runtime включает только Kuznyechik/MGM/служебные пакеты. Никакой реализации Magma в runtime не добавлено.

## Граница доверия

`NewCipherCT` помечен upstream как EXPERIMENT. Его S-box использует последовательное сканирование вместо secret-indexed lookup; это **не доказательство constant-time всего AEAD**. MGM `gfMul` содержит ветвление по промежуточному значению, зависящему от ключа, счётчики — ранний выход при переносе. Независимый аудит, timing-устойчивость целого provider и ARM не подтверждены. Python/Go GC не гарантируют уничтожение всех копий ключа. ГОСТ-алгоритм не означает сертификацию продукта.

Поэтому доступ к новой реализации ограничен `APP_ENV=test`, явным `LCM_KUZ_VALIDATION_AUTHORIZATION=1` и именем отдельного проекта `lcm-stage11-kuznyechik-*`. Обычные deployments не получают live activation. Это экспериментальный допуск, не разрешение production. Выполнение локальных KAT проверяется до административного запроса; capabilities, ключи и budget проверяются отдельно. Без этих условий отказ, без fallback.

## IPC и сборка

CGO отключён. Один ограниченный subprocess на операцию, без сетевого listener, shared instance и buffer ownership между языками. Ключ передаётся только в stdin pipe, никогда в argv/env/log. `Open(nil,…)` аутентифицирует полный tag через upstream `subtle.ConstantTimeCompare` до расшифрования. При ошибке stdout содержит только однобайтовый статус. Panic/process failure — инфраструктурная ошибка, не normal invalid packet. Ограничены frame, AAD1024, plaintext4096 и timeout5s.

Builder image: `golang:1.27.3-bookworm@sha256:dc0963f32053e4bc451d24d87e3892d42d01021b61f093e98eb95c0352bb84b0`; offline Go modules, `CGO_ENABLED=0`, `-trimpath`, без build ID. Частные ключи не входят в build context. Локальная Go toolchain дополнительно фиксируется в build JSON; её binary hash нельзя автоматически считать hash Docker binary.

## Фактические проверки

- `go test -json ./kuznyechik ./mgm` в pinned upstream: exit0, исходный журнал `upstream-provider-tests.jsonl`.
- `go test -json ./kuznyechik` в vendored subset: RFC7801 все 10 round keys через CT key schedule, exit0.
- Python cryptographic suite: 29 passed, exit0; RFC7801 block encrypt/decrypt и оба RFC9058 A.1 examples, tag/AAD/key/nonce negatives.
- Независимый executable: 54 размера/сочетания AAD, полное совпадение ciphertext+tag; 108 отказов damaged tag, exit0. Ключи случайные и в отчёт не записываются. Повторные данные не считаются независимым security audit.

Машиночитаемые результаты находятся в `docs/reports/stage11/`. Первая попытка переноса RFCplaintext содержала ошибку тестовой hex-константы, обнаруженную точным KAT; исправлена по строкам RFC. Это не дефект provider и не mutation detection.
