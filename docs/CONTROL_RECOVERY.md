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

## Уточнение 8-fix: действия оператора и пределы восстановления

Recovery logic в 8-fix не изменена. Старое значение effective — последнее
доказанное состояние, а не доказательство текущего состояния при неизвестном исходе.
Запрещено вручную обнулять replay, command ledger, nonce reservations или выставлять
EFFECTIVE_CONFIRMED по ACK/SQLite. До recovery сохранить read-only копии PG audit,
transitions, commands (включая committed wire), ACK/evidence и согласованную SQLite
backup; хранить их приватно, не публиковать ключи и wire credentials в отчётах.

### A. Истёк PREPARE, ACTIVATE не был committed

1. Остановить выдачу новых команд устройству и его publisher на время локального
   расследования. Зафиксировать device/epoch/transition/correlation ID и deadline.
2. Проверить авторитетную, не откаченную PG: для этого transition нет ни одной
   durable ACTIVATE (включая claimed/pending/expired), activated_at пуст; проверить
   также прежние transitions/commands той же identity/epoch. Worker сначала
   фиксирует команду в PG, только потом публикует: отсутствие строки в полной
   непрерывной истории исключает её выдачу штатным worker. После восстановления
   старой PG-копии или при компрометации controller key такой вывод недопустим.
3. Локально сверить device identity/epoch, SQLite profile, prepared transition,
   command seq/IDs/digests и nonce high-water с PG; исключить исполненную ранее
   ACTIVATE и противоречивые сохранённые команды. Проверить отсутствие свежей
   retained команды; штатные валидные команды никогда не retained. Старая
   expired команда не становится разрешённой после reconnect.
4. Даже если старый профиль доказан, текущий authorize блокирует telemetry после
   deadline, а SQLite сохраняет prepared. Endpoint reconcile не поддерживает
   PREPARE-only: он требует committed ACTIVATE. Поддерживаемой команды CANCEL/
   безопасной очистки этого состояния сейчас нет. НЕ удалять pending/prepared
   посредством SQL/SQLite и НЕ восстанавливать старый snapshot ради разблокировки.
5. Если нет пригодного согласованного состояния для восстановления, оставить
   identity изолированной и выполнить отдельно reviewed provisioning с новой
   эпохой и независимыми ключами. Старую identity/epoch закрыть в ACL/registry,
   сохранить audit и nonce/command history. Это операторская миграция, не новая
   функция 8-fix; `provision` специально отвергает конфликтующий fingerprint.
   Возврат в работу требует новой AEAD telemetry и durable evidence, не флага в БД.

Потеря READY до TTL: восстановить связь/worker, повторить существующие durable
PREPARE bytes; устройство возвращает cached ACK без повторного исполнения. После
TTL перейти к A, если ACTIVATE отсутствует; если READY уже породил ACTIVATE — к B.

### B. ACTIVATE мог быть исполнен

Не возвращать старый профиль автоматически. Сохранить UNKNOWN_OUTCOME и старое
verified evidence; проверенный ACTIVATE ACK сообщает только reported state.
При потере ACTIVATE ACK новая целевая AEAD telemetry в действующем grace window
подтверждает effective. При истечении окна проверить committed ACTIVATE, identity,
ключи, SQLite и server nonce authority, затем администратор с CSRF может вызвать
существующий `/api/control/<device>/reconcile` с тем же transition_id и TTL 15–120 s.
Это только ограниченное окно наблюдения: нет новой ACTIVATE и нет оживления
просроченных bytes. Только новая корректная целевая telemetry с новым sequence
меняет effective; без неё снова UNKNOWN_OUTCOME. Старый профиль этим путём не
разрешается как downgrade. Если новый boot не получает lease из-за расхождения
локального профиля и PG, reconcile/согласование нужно выполнить до запуска agent;
endpoint сам по себе не чинит потерянную SQLite.

### PostgreSQL, устройство и утрата state

* PG временно недоступна: восстановить исходный durable volume/WAL без отката
  состояния. Receiver не делает manual ACK после failed commit; проверить
  redelivery, единственную admission, replay/Outbox/evidence и доставку relay после
  восстановления. Отказ reject audit также оставляет пакет неподтверждённым.
* PG восстановлена из backup: до запуска устройств сверить все command counters,
  leases/sequence_reserved и replay/evidence с более новым локальным high-water.
  Нельзя доказать отсутствие уже использованного диапазона по одному last_sequence:
  устройство могло шифровать ещё не доставленные пакеты. При недоказанной
  непрерывности nonce authority — новая эпоха и новые ключи. Совместный rollback
  PG+SQLite особенно опасен: локальная проверка rollback его не обнаружит.
* Restart устройства с сохранной SQLite: не переинициализировать файл; проверить
  права 0600/каталог 0700, identity/epoch и ledger. Agent получает новый boot-bound
  PG range, выше всех прежних reservations; не восстанавливает неиспользованный
  остаток старого range. Restart worker сохраняет committed commands/identities.
* Потеря SQLite: agent останавливается с `Device state missing`; install не
  переинициализирует installed volume. Допустима только проверенная согласованная
  backup с доказанной свежестью command ledger и nonce reservations. Stale ledger
  либо overlapping range отвергаются. Если свежесть не доказана, новое reviewed
  provisioning с новой эпохой, независимыми telemetry/control keys и отзывом
  старого доступа; нельзя создавать пустую SQLite при старых ключах.

Новая эпоха/ключи нужны при потере/неопределённости nonce или command authority,
compromise ключей, исчерпании бюджета, недоказанном rollback либо утрате state без
согласованной копии. Обычные lost ACK, restart и краткий outage с сохранной
непрерывной durable историей сами по себе не требуют ротации.
