# Recovery без ложного применения

| Отказ | Поведение |
|---|---|
| PREPARE без ACTIVATE | Устройство сохраняет старый AEAD; prepared state durable |
| Потеря READY | Durable PREPARE повторяется, device возвращает прежний ACK |
| ACTIVATE ACK потерян | Нет автоматического rollback; авторизованная новая telemetry может подтвердить effective |
| Worker restart до/после publish | Command bytes/identity committed, retry идемпотентен |
| PG до commit | Ни intent/counter/evidence не должны фиксироваться частично |
| PG после publish | Intent уже durable; receiver не подтверждает до успешного собственного commit |
| Broker outage | Нет fake ACK/effective; reconnect/retry в пределах TTL |
| Device restart | SQLite профиль/command ledger сохраняются, новый boot nonce range |
| State потерян/устарел | Fail closed, recovery; не silent initialization/downgrade |
| Deadline истёк | UNKNOWN_OUTCOME, bounded grace закрывается |

Manual reconcile endpoint открывает новое ограниченное ОКНО НАБЛЮДЕНИЯ только
для ранее авторизованной ACTIVATE того же transition. Он не посылает новый профиль,
не меняет effective и не оживляет просроченные command bytes. Требуется новая
проверенная telemetry целевого AEAD. Без неё outcome остаётся unknown.
PREPARE-only expiry нельзя превратить в ACTIVATE этим endpoint. Если устройство
так и не применило профиль или потеряло ledger, необходима локальная операторская
проверка/восстановление правильной копии либо новое reviewed provisioning с epoch;
универсальная удалённая починка повреждённого state не заявляется.

Старый retained command не является свежей авторизацией: MAC/topic/TTL/sequence/
transition проверяются. Параллельные requests одному device сериализуются PG row
lock, второй conflicting switch отвергается. MQTT publish вне SQL transaction.

Retention по умолчанию ничего не удаляет. Pending один на device; claims/queues
ограничены; leases≤10000/device требуют reviewed maintenance. Command replay,
nonce reservations, effective evidence и identities нельзя сбрасывать ради
cleanup. Audit/commands растут с операциями: мониторинг/архивирование нужны;
автоматический purge без reviewed tombstone policy не реализован.
