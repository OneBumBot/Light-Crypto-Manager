# Протоколы этапа 4

Дата: 2026-11-08. Отчёты очищены от известных секретов через scripts/run_check.py.
Каждый блок содержит команду, UTC, вывод и EXIT CODE. Ошибочные прогоны сохранены,
а не заменены выдуманным успехом. ANSI/хвостовые пробелы нормализованы.

| Файл | Содержание |
|---|---|
| [stage4-transport.txt](stage4-transport.txt) | Config/build/start, 108 baseline tests, реальный trusted/untrusted TLS, неверный пароль, ACL publish/read |
| [stage4-protocol.txt](stage4-protocol.txt) | 146 tests, v2/live smoke, ciphertext/AAD/replay, force-recreate receiver и повтор сохранённого пакета |
| [stage4-web.txt](stage4-web.txt) | Начальные неуспешные CSRF fixture прогоны и исправление изоляции; 172 tests; Chromium DOM-XSS; реальный HTTP/Socket.IO |
| [stage4-final.txt](stage4-final.txt) | Финальные 177 tests, ACL для receiver/web/publisher, replay/restart и проверка генератора материалов |

## Соответствие сценариям задачи

1. Publisher/TLS/live data: final smoke, admission raspb1 подтверждён PG replay-state.
2. Неверный пароль: transport/final scripts.mqtt_security_smoke.
3. ACL: запрещённый publish publisher/web/receiver; publisher не читает чужой topic,
   положительный reader получает контрольный probe.
4. Доверенный CA принят, недоверенный отклонён: реальный broker TLS handshake.
5–6. Повреждение ciphertext/AAD: unit и реальные MQTT сообщения.
7. Replay: две отправки одного корректного пакета не дают вторую аномалию.
8. Persistence: force-recreate receiver + --replay-only, а также новый PG engine.
9. Malformed JSON/schema/ranges/limits: unit; живой invalid JSON после которого
   принимается корректный пакет; state не продвигается до аутентификации.
10. Socket.IO: анонимный connect отклоняется, cookie/CSRF обязательны; реальный
    viewer получает MQTT событие и теряет соединение после logout.
11. Роли: viewer/operator не изменяют algorithms, operator изменяет разрешённый tag
    и не удаляет его; неизвестные роли fail closed.
12. CSRF остаётся включённой; межсессионный/неверный/отсутствующий токен отвергнут;
    безопасный next, generic DB errors, HTML escaping и Chromium DOM/attribute/script XSS.

Дополнительно: конкурентная подача 16 копий даёт одно принятие, sender SQLite
сериализует 24 конкурентных allocation; consumers receiver/web независимы,
rollback сохраняет возможность retry после DB ошибки. Финальный результат —
177 passed, без предупреждений; Chromium проверка отдельно, не включена в 177.

В первых двух web прогонах тест с общим outer app context кешировал CSRF rendering
между разными тестовыми клиентами. В helper очищен этот тестовый g cache, не защита
приложения. Итоговые положительные/отрицательные проверки прошли с CSRFProtect.
Браузерный tool pinned Playwright 1.56.0; запускался реальный Chromium headless.

Это не доказательство production readiness, lossless delivery, полного
криптографического соответствия, ARM64 или результатов нагрузочного/внешнего аудита.
Политики/ML/CRISP не реализовывались. Секретные файлы и raw private материалы
остаются локально вне Git/образов. Перед публикацией проведена отдельная проверка
отчётов на текущие и исходные секретные литералы.

## Этап 5

Текущий двухбазовый контур и матрица14 сценариев:
[STAGE5.md](STAGE5.md). Итог210 pytest; отдельные реальные outages/crash/
multi-device/TLS/ACL/web/Chromium проверки. Промежуточные failures сохранены.

## Этап 6

[STAGE6.md](STAGE6.md):233 pytest, реальные ML recovery/security/web/Chromium
проверки. Отдельно ограниченный real Edge эксперимент и synthetic telemetry DEMO;
машиночитаемые метрики рядом с протоколами. Кандидаты дополнительных данных —
[ML_DATASETS.md](../ML_DATASETS.md), новые наборы не скачивались.

## Этап 7

[STAGE7.md](STAGE7.md):255 pytest + реальные policy/PG/MQTT/ML/Mongo/security/web
проверки. [Синтетические52 policy runs](stage7-policy-experiment.json) отдельно от
инженерных тестов. Ascon — единственный реальный профиль; no live control/ACK.
