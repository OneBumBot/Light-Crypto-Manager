# Этап 13: надёжность и ограничения доказательств

Тесты используют новую схему/новые Stage13 credentials; ни один старый authority не сбрасывается. Полный результат реальных fault experiments фиксируется отдельно в `reports/stage13/policy-reliability.json`; если файл отсутствует или exit_code отличен от0, соответствующий эксперимент не считается завершённым.

Регрессия PostgreSQL проверяет rollback полного batch, retry, duplicate markers/decisions/proposals, state revision, late insertion, version activation против открытого batch, retention против обработки и 2/4 конкурентных worker. Все новые worker сериализуют batch по существующему advisory transaction lock. Это корректность конкурирующих попыток, не горизонтальная обработка разных устройств.

Новая очередь содержит committed source snapshots. Claim не оставляет отдельного permanently claimed состояния: удаление pending и signal/FSM/decision/transition/proposal коммитятся вместе. При отказе до commit всё откатывается. Настоящие SIGKILL после claim и перед commit должны подтвердить неизменность authoritative rows и сохранение pending identities; они не заменяются Python exception-тестом.

Late committed T+5 после обработанного T+10 обязательно появляется в очереди; pure FSM выдаёт прежний late diagnostic. Timestamp cursor и UUID high-water отсутствуют. На activation seed повторно обнаруживает retained события без marker выбранной версии; история immutable. Транзакция не смешивает версии. Кэш Rules существует только внутри transaction и проверяет binding версии.

Synthetic stale откладывается для устройства с pending real source; backlog другого устройства не блокирует диагностику молчащего. Генерация bounded, сохраняет guard/UNKNOWN. Это намеренное изменение scheduling, не заявление полной эквивалентности старому глобальному idle-only расписанию. Golden equivalence сравнивает одинаковый порядок/время реальных входов; отдельные тесты проверяют новое scheduling.

ML committed status snapshots не теряются при последующем обновлении mutable ML row. Fairness чередует доступные источники; turn durable, odd batch/restart/rollback проверены. trusted_detector остаётся false, отсутствие model/score — не NORMAL. Это не запуск доверенного RF/IF и не обучение модели.

Обнаружен реальный дефект: внутренний ValueError FSM при ML обработке перехватывался как ошибка source contract, после чего источник потреблялся. Red test сохранён (`ml-fsm-failure-before.txt`, exit1). После сужения exception boundary внутренний отказ откатывает transaction и сохраняет source; targeted/full regression проходят. Внешняя эксплуатация дефекта не заявляется.

Mutation: `mutations-final.json` —24/24 поведенческих нарушений обнаружены, runner exit0, baseline контроль зелёный. Ранние20/22 показали два пробела покрытия (synthetic clock и barrier row lock); исправлены тестовые clock/barrier, повторены все24. Первоначальная ошибка metadata Git и build/import failures не считаются обнаружением поведения.

Upgrade0010→0011 проверен на заполненной схеме16 authoritative tables, включая active/inactive policy, guards, rate_limited marker, replay/Outbox, live command history/effective receipt и MGM usage reservations. Canonical hashes строк до/после и повторного upgrade одинаковы; нет нулевого fictitious backfill crypto usage.

Остаточные ограничения: один глобально сериализованный processor, bounded journal100000 (consumed history тоже занимает capacity до retention), activation-time replay/seed может задержать worker, большие ML status histories увеличивают durable pending. Не поддерживается mixed old/new worker rollout. Старый worker надо остановить до additive migration, затем запускать новый; receiver/keys/state сохраняются. Политика не делает live crypto commands.

## Фактически завершённый Policy fault run

`policy-reliability.json`, exit0: новые три устройства продолжают настоящую1Hz MQTT/TLS telemetry. Worker остановлен92s; real backlog растёт, admission продолжается. Явный lab-only slow-consumer fault500ms/batch1 используется только для DOM состояния ready+stale+lagging, не performance-результат. Admin HTTP активирует `stage13-recovery-v2` с новым rules SHA; retention удаляет0 молодых unread rows. После восстановления normal worker pending0 при продолжающемся входе.

SIGKILL after_claim:20 pending IDs сохранены, authoritative state/signal/decision/transition/proposal/schedule rows неизменны; recovery6.503s. SIGKILL before_commit:21 IDs сохранены, тот же rollback invariant; recovery9.159s. Advisory lock release проверен непосредственно, не только ожиданием времени. PostgreSQL outage восстанавливается на том же volume за11.725s до наблюдаемого нового admission/empty pending/ready UI. Это bounded polling-observed recovery, не точный outage SLA.

Последний snapshot759 security observations/759 consumed/0 pending, overflow0. До ручных crypto E2E в этом стенде live_control_commands0, duplicate_signals0/duplicate_decisions0: Policy не создаёт commands. В реальном Chromium подтверждены stale data clearing при PG outage и fresh после восстановления. HTML/attribute injection и malformed response — отдельно отмеченные DOM fixtures, не реальные security incidents. Browser page errors0. Source/evaluation times, old/new SHA, argv/exit codes и snapshots сохранены в JSON.

## Реальный криптографический и браузерный regression в новом Stage13 cohort

`crypto-final.json`, exit0:16/16 manual transitions EFFECTIVE_CONFIRMED,30 authenticated ACK (два ACTIVATE ACK намеренно потеряны),19 effective receipts (16 переходов и3 исходных). PG accepted1814=Mongo managed1814=Outbox delivered1814; final Policy1909 source observations consumed1909/pending0/overflow0, live Policy applied0, unknown transitions0. Все сервисы этого стенда остановлены с сохранением volumes/keys/SQLite.

Dashboard Chromium и отдельная `/control` страница выполнили по4 настоящих перехода Ascon→Kuz→AES→Kuz→Ascon; соседи неизменны, gamma capability bound. Viewer read-only, operator/admin negatives, CSRF/ACL/HMAC/forged ACK/key-reference contracts проверены прежним реальным control_security_probe. XSS/malformed/other-device API fixtures отделены от настоящего устройства. Page errors0, reload/mobile проверены.

Lost ACTIVATE ACK: при своевременной новой AEAD telemetry effective подтверждён receipt без ACK; при задержке20s наблюдался UNKNOWN_OUTCOME, затем явная reconciliation и новая receipt. ACK не является ни необходимым, ни достаточным доказательством effective: authority — принятая authenticated telemetry/PG commit.

Семь реальных service faults на Kuz: Mongo, Control Worker, Policy Worker, PG, broker, device-alpha и receiver. После restore наблюдаемый recovery2.226–2.359s (без времени остановки/старта контейнера; total/start/restore отдельно в JSON); pre-restore cohort доставлен, false_effective=false во всех семи. Mongo Outbox pending25/claimed1 во время outage — backlog, не число потерянных сообщений; финальная доставка завершена. Намеренные delivery_error5/retry5 не скрываются.

MQTT poison MGM:19 malformed sent/19 rejected, затем3 accepted, duplicate admission0/replay1; неверные type/tag/AAD не меняют admission/replay state, rejected identity unbound. Receiver processing failures0, malformed-induced subscriptions/connections0; после явного receiver restart counters не выросли от повторной доставки poison. Приватные ключи/пакеты не входят в отчёт. Набор failures строго лабораторный, не обещание абсолютной доступности.
