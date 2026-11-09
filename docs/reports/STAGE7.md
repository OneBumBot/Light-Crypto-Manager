# Этап 7 — протокол проверок

Ветка feature/adaptive-policy-engine от6aedf52. Изолированный Compose project
lcm-stage7 с новыми volumes, MQTT TLS/ACL и отдельными тестовыми секретами.
Использован прежний private DEMO telemetry model этапа6, без переобучения.

## Фактические результаты

Последний полный запуск: **255 passed in24.45s**, без skips/warnings,
[stage7-final.txt](stage7-final.txt). Включены прежние233 и22 новых теста.
Результаты предыдущих этапов не выдаются за проверку новых возможностей.

| Проверка | Доказательство |
|---|---|
| FSM, counts, critical escalation, positive recovery | tests/test_policy_engine.py |
| Hysteresis, cooldown, fast-stream rate limit, absent/stale ML | те же13 pure tests; stage7-unit.txt |
| ML trust/scale/versions/malformed data | test_ml_untrusted_semantics_and_unavailable_not_normal |
| Device isolation / unverified victim binding | stage7-policy-recovery.txt, реальные MQTT packets трёх устройств |
| Min protection / capabilities / unsupported registry | test_profile_registry_minimum_and_capabilities |
| Command expiry/replay/epoch/auth/simulator restart | test_command_contract_auth_replay_ttl_and_no_applied |
| No applied configuration from missing ACK | test_deterministic_simulation_and_unconfirmed_config, PG CHECK, real probe |
| Atomic rollback / dedupe | test_idempotent_atomic_decision_and_restart |
| Concurrent same-device event16 attempts | test_concurrent_device_processing_one_event |
| Version immutability / activation / guard / command sequence | test_version_immutability_activation_and_minimum, test_policy_version_change_retains_guard_and_command_counter |
| Source capacity/overflow and source dedupe | test_source_journal_bounded_unattributed_and_worker_dedupe |
| Explicit retention preserves replay/state/identity | test_explicit_retention_preserves_identity_state_and_replay |
| Stage6 migration preservation / repeated upgrade | test_stage6_upgrade_preserves_ml_and_replay + old migration tests |
| Two workers / process restart / policy off | stage7-policy-recovery.txt |
| Actual PG outage/readiness removed/fresh recovery heartbeat | stage7-policy-recovery.txt |
| Previous Mongo/PG outage/QoS1/crash-after-write/two relays | stage7-storage-regression.txt |
| ML missing-model/restart/hash/dedupe/Mongo recovery | stage7-ml-regression.txt |
| Flask authorization/admin activation/CSRF | test_policy_auth_roles_csrf_activation_validation, stage7-live-web.txt |
| TLS/wrong password/untrusted CA/forbidden publish/read | stage7-security.txt |
| Socket.IO/redirect/role/CSRF/login/logout | stage7-live-web.txt + prior tests |
| DOM XSS in legacy/ML/policy views | stage7-browser.txt, actual Chromium12 payload checks |
| Deterministic52 runs / synthetic configs/time | stage7-policy-experiment.json, stage7-simulation.txt, unit repeat equality |
| Static checks/source preservation | stage7-static.txt |
| Known secrets/permissions/Git/history/three image filesystems | stage7-audit.txt |

## Команды

```bash
docker compose --env-file .local-runtime/stage7.env run --rm --no-deps tests
python3 scripts/check_policy_system.py --env-file .local-runtime/stage7.env
python3 scripts/check_dual_database.py --env-file .local-runtime/stage7.env
python3 scripts/check_ml_system.py --env-file .local-runtime/stage7.env
```

ML smoke впервые выполнялся с пустым model volume и проверял missing model,
после установки immutable artifact для повтора нужен --reuse-installed-model.
Все фактические команды с environment/exit codes записаны в txt. Recovery scripts
ограничены явными isolated stage project names, volumes не удаляют.

## Промежуточные ошибки и исправления

- Первый полный запуск:247 passed/1 failed. Старый callback unit mock не учитывал
  capture; добавлен mock журнала и assert, что rejected не передаёт device identity.
- Следующие web unit failures: внешний app context тестовой PG fixture кешировал
  g между клиентами; новый helper использует отдельный app context на HTTP request.
  После login CSRF берётся с dashboard, поскольку /login перенаправляет уже вошедшего.
  В приложении CSRF/LoginManager не отключались и роли не ослаблялись.
- Первый новый Chromium assert ожидал неэкранированную строку внутри JSON.stringify;
  сравнение исправлено через json.loads текста. Payload сохраняется как текст,
  DOM execution отсутствует. Проверки script/img/svg не удалены.
- Buildx plugin отсутствует; classic builder успешно собрал образы. Это не
  подтверждает multi-arch/ARM64 сборку.

## Границы доказательств

13 сценариев ×4 политики — синтетическое моделирование управления. Оно не
доказывает реальное обнаружение атак или криптостойкость. Trusted critical online
source и защищённый device control handler отсутствуют. authentic=True ACK
симулятора — тестовая предпосылка, не криптографическая аутентификация.

Configured Ascon, recommended/requested, simulated и applied различимы. Реальных
command sends/ACK/applied изменений нет. Production readiness, DB least privilege,
HA/DB TLS и10000 устройств не проверены. Source/audit retention имеет границы,
описанные в POLICY_ARCHITECTURE.md и KNOWN_ISSUES.md.

После проверок изолированный контур остановлен без --volumes:
[stage7-shutdown.txt](stage7-shutdown.txt). БД, model/security/counter volumes
сохранены. Полный список изменений — [stage7-files.txt](stage7-files.txt).
