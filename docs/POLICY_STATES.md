# Риск, рекомендация и подтверждённая конфигурация

NORMAL — имеются достаточные свежие наблюдения, нет оснований для адаптации.
WATCH — требуется наблюдение; ALERT — устойчивые условия правила; CRITICAL —
достоверное критическое условие; UNKNOWN — информации недостаточно.
Это состояния политики, не оценки криптостойкости.

Начальное состояние UNKNOWN. Явная таблица ALLOWED находится в engine.py;
фактический переход дополнительно ограничен evidence, cooldown и recovery.
Обычные повышения идут NORMAL/UNKNOWN → WATCH → ALERT; проверенное критическое
условие допускает быстрый CRITICAL. CRITICAL не снижается до WATCH/ALERT по
слабому сигналу. Восстановление в NORMAL требует полного положительного окна.
Из любого состояния допустим UNKNOWN при деградации, с сохранением guard.

Отдельные значения в PG/UI:

- observed_risk: наблюдаемое состояние и guard в сохранённой FSM;
- recommended: рекомендация профиля и recommended_state в решении;
- requested: управляющее намерение, если оно создано, не отправленная команда;
- configured_profile: Ascon из единственного текущего поддерживаемого контура;
- applied: NULL, поскольку аутентифицированного подтверждения устройства нет;
- effective_security_state: unconfirmed, не выдуманный applied.

При неизвестном профиле статус unsupported_profile, configured profile сохраняется.
При отсутствии capabilities TLS/AEAD/v2 — minimum_protection_violation.
Профиль не выбирается по произвольной числовой «силе» алгоритма. Каждый decision
имеет policy_version, decision_at, причины, IDs использованных сигналов,
current/recommended/observed states, applicable=false и execution_status.

SIMULATION хранит отдельные результаты, не меняет эти PG Applied Configuration.
В реальной БД CHECK запрещает applied!=NULL до реализации отдельного проверенного
device protocol и последующей миграции. Состояния guard и положительные основания
переживают перезапуск через PostgreSQL, а не через память worker.

Устройство без учтённых событий ещё не имеет строки policy_device_states.
Отсутствие строки/результата не означает NORMAL. Начальное состояние FSM — UNKNOWN.
