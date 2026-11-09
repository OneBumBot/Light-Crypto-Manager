# Протоколы этапа 5

Ветка feature/mongodb-telemetry-storage от d9a000f. Linux x86_64, Python3.12.16,
Docker29.9.2/Compose5.6.1; отдельный project lcm-stage5 и отдельные volumes. Прежние
volumes lcm-stage4 не использовались. Все .txt очищены runner от известных secrets,
private PEM и credential URLs; полный поиск известных литералов проверен аудитом.

**Итоговый pytest: 210 passed, без skips/warnings.** Предыдущие177 тестов сохранены
(фикстуры переведены на миграции, ожидаемое число таблиц обновлено). Тесты включают
реальные PG schemas и authenticated MongoDB. Это не замер производительности.

| Требуемый сценарий | Доказательство |
|---|---|
| 1 publisher → MQTT → ingestion → PG → Mongo | stage5-final.txt, dual_database_probe demo; stage5-mqtt-regression.txt |
| 2 независимые устройства | stage5-final.txt: alpha/beta/gamma, отдельные TLS credentials/topic/key, history по стабильной identity |
| 3 replay не создаёт новый outbox | stage5-tests.txt, test_outbox.py; stage5-final.txt после restart |
| 4 retry не дублирует Mongo | stage5-tests.txt: parallel inserts/conflict; stage5-final.txt process crash |
| 5 rollback не продвигает replay | stage5-tests.txt: outbox insert constraint failure откатывает anomaly/replay/outbox |
| 6 Mongo unavailable → backlog | stage5-final.txt: настоящий stop mongo, pending с attempts >=1 |
| 7 Mongo restored → delivered | stage5-final.txt: up mongo + проверка всех трёх identity |
| 8 crash после Mongo write до PG acknowledge | stage5-final.txt: отдельный процесс os._exit(19), lease expiry, один документ на identity |
| 9 restart receiver/relay | stage5-final.txt: force-recreate receiver/restart relay + replay; также настоящий PG stop/up и QoS1 redelivery |
| 10 concurrent relay | stage5-final.txt: два реальных relay процесса; stage5-tests.txt: SKIP LOCKED concurrency и fencing |
| 11 authorized history | stage5-live-web.txt: настоящий HTTP login/history/page/admin metrics; stage5-tests.txt: bounds/date/sort/pagination/empty/503 |
| 12 TLS/ACL/CSRF/Socket.IO | stage5-mqtt-regression.txt, stage5-live-web.txt, stage5-browser.txt |
| 13 прежние тесты | stage5-tests.txt: все210, включая прежние177; src/web/ascon и classifier неизменны |
| 14 new/legacy migration | stage5-tests.txt: empty schema, legacy rows/replay preserved, повторный upgrade, отказ несовместимости |

Дополнительно: stage5-storage.txt — Mongo health/config/build; stage5-retention.txt
— явное создание 10-летнего TTL и немедленное отключение (старые документы не
удалялись; полный TTL lifecycle не проверен). stage5-audit.txt — Git/working tree/
image/material permissions. stage5-static.txt — Ruff/compileall/Node/uv/diff.

Промежуточные failures не удалены: первоначальный concurrency test пытался получить
Flask engine в потоке без context (исправлено передачей engine); новый auth test
делил g._login_user между клиентами внешней fixture (исправлен сам тест); два ACK
теста запускались из образа со старым Mock вместо контекстного MagicMock.
После пересборки и проверки актуального теста полный прогон210 прошёл. Защита
приложения не отключалась. Первый integration run отказал на demo Tag_Name:
provisioning теперь принимает существующее корректное demo имя и проверяет
конфигурацию, не перезаписывая её. Повторные integration run успешны.

Команды для воспроизведения — ../COMPOSE.md. Полные stdout/stderr и коды каждого
запуска находятся в .txt, включая неуспешные. Внутренний exit19 fault-test ожидаем;
верхний check_dual_database.py обязан завершаться0. Сохранившиеся тестовые данные
и счётчики нужны для повторения; не удаляйте state volumes с прежними ключами.
