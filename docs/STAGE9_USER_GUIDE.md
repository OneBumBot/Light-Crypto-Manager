# Пользовательский сценарий

1. Войти через `/login`. Имя/пароль выдаются оператором стенда; пароль не публичный.
2. Открыть «Мониторинг». Сводка различает provisioning и свежую telemetry. `Recent`
   означает PG admission ≤15 s, а не подключение к broker. Каждый компонент имеет
   источник, время проверки и freshness TTL. Отсутствие evidence не означает безопасность.
3. Выбрать alpha/beta/gamma. Карточка показывает последнее принятое измерение,
   measured_at и received_at в локальном часовом поясе, current epoch/sequence и
   event ID. Профиль последнего packet не подменяет отдельный verified receipt.
4. В «Измерения» выбрать временной интервал. Ввод локальный, запрос преобразуется
   в UTC. Mongo history bounded (50/страница), графики сортируются по measured_at,
   пропуски >15 s не соединяются и нулями не заполняются. Сбой Mongo явно указан.
5. «Безопасность» показывает device-bound факты; anonymous rejected находятся
   отдельно. Replay может быть обычной QoS1 redelivery; высокая температура —
   физическое наблюдение, не доказанная атака. Policy risk — оценка, не факт атаки.
6. «Оценки» показывает DRY_RUN, rule version/freshness, причины и signal IDs.
   Длинные списки evidence раскрываются отдельно. ML Research/DEMO не является
   вероятностью кибератаки и не даёт право управления. Без результата нет оценки.
7. Viewer/operator только просматривают. Admin выбирает поддерживаемый профиль,
   нажимает «Запросить переключение», проверяет device/target и подтверждает dialog.
   Pending transition, отсутствующий verified baseline, disabled device/worker и
   unsupported target блокируют кнопку; сервер независимо повторяет проверки.
8. После 202 показывается transition ID, а не обещание успешной смены. В timeline
   отдельно видны request, commands, broker PUBACK, DEVICE_READY, authenticated ACK,
   telemetry event и confirmed_at. Быстрые промежуточные фазы могут пройти между
   polling обновлениями; их durable события остаются в timeline.
9. Только новая принятая target AEAD telemetry подтверждает effective. После ACK
   без неё старый verified profile остаётся прежним. UNKNOWN_OUTCOME/expired не
   означает успеха. Используйте CONTROL_RECOVERY.md, не сбрасывайте counters/state.
10. Admin может открыть bounded reconcile только для уже авторизованной ACTIVATE.
    Это окно наблюдения, не команда rollback и не исправление потерянной SQLite.
11. Обновление страницы заново получает server state. При PG failure current data
    очищаются, control блокируется. Исторический Mongo график не является live state.
12. Logout доступен отдельной POST+CSRF кнопкой. Основной UI работает без CDN assets.

Навигация и формы имеют подписи/keyboard focus; native confirmation dialog работает
клавиатурой. На мобильном таблицы прокручиваются внутри секции, не расширяя страницу.
График дополнен таблицей точных значений. Размеры проверены на 1366×900 и 390×844.

## Расширенная страница /policy

JSON свернут по умолчанию в native details/summary. Фильтр device_id ограничивает
выборку; overview содержит observed_risk, версию и worker freshness, decisions —
reasons/used_signals, signals — исходные события, transitions — изменения риска,
intents — предложения без отправки. Для обычного просмотра используйте карточку
устройства. Admin-форма версии правил также свернута: её активация меняет только
DRY_RUN правила и не означает ACTIVATE криптопрофиля.
