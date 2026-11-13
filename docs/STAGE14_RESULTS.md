# Этап14 — independently corroborated ground truth и offline RF/IF

## Исходное состояние и границы результата

Исходная ветка `feature/policy-engine-throughput-hardening`, SHA `21a99bbc6669ca440a1b174e1285a24ac7b323c2`. Новая ветка `feature/rf-if-ground-truth-validation`. Научные методы и23-model matrix зафиксированы в `20a6babeebf6a9f11494d40b22a9c41e51585075` до обучения/test. Lifecycle/source failure hardening зафиксирован в `29dba06`; итоговый docs/report commit — следующий HEAD, точный SHA доступен через `git rev-parse HEAD`. Полный список изменений находится в [changed-files.txt](reports/stage14/changed-files.txt). Main `c352d817386a17fb244d3567b287af0412eed4e4` не изменён. Push/merge/rebase не выполнялись.

**ЧастьA: внутренний data-quality gate PASS. ЧастьB:23 заранее заданных offline fits и один final holdout выполнены. Это ограниченное исследование контролируемых лабораторных отклонений, не подтверждённый live IDS.** Существенные ограничения: один host,5 положительных holdout sessions, сильный fingerprint purge; полный количественный shortcut audit завершён после test, только на train/validation. Модели и thresholds после test не менялись.

## Baseline и сохранность

Новый baseline project:922 passed,0 skipped,49.33s,exit0. Alembic head0011_policy_throughput, новых migrations нет. Прочитаны7.5b/7.5b-fix/Stage13 sources/reports. После работы967 passed,0 skipped,53.44s,exit0 в новом PG/Mongo project. [Исходный аудит](STAGE14_BASELINE_AUDIT.md), [полная регрессия](reports/stage14/full-regression.txt), [команды](reports/stage14/full-regression.commands.json).

70 первичных исторических PCAP Stage7.5b сохранены; всего снимок содержит113 исторических PCAP paths/99 уникальных физических SHA, включая диагностические копии. Старые59 selected captures/46395 observations после независимого пересмотра остаются all-unknown и не дают разрешения на обучение. Прежний9-capture2269-row probe не использован для увеличения новой class support. Старые frozen plans,764-file archive manifest, models/registry/SQLite/keys/replay/control/DB volumes сохранены.

Before/after сравнение:1183 protected tracked paths и4060 private files полностью совпали; старые Docker projects/volumes/времена состояния и main совпали. Это hash/metadata audit, не чтение каждого блока исторического Docker volume. Старые проекты не запускались и не сбрасывались. [preservation-after.json](reports/stage14/preservation-after.json).

## Новый контур и реальные источники

`lcm-stage14-ground-truth-*`:34 новых realm inputs (baseline,pilot,30 primary blocks,contrast,regression). Отдельные сети, named PG/Mongo/Outbox/capture state volumes, fresh TLS CA/credentials, независимые Ascon device keys. Нет host ports, primary capture cohorts не запускались одновременно. Keyless MQTT witness получает ciphertext digest; парсер broker log даёт реальные session/auth/ACL/publish/DUP evidence, PG read-only snapshots подтверждают authenticated admission/replay. Сырые TCP packets захвачены namespace tcpdump при настоящем MQTT/TLS, не synthetic fixtures.

В этом исследовательском stand не запускались manual crypto transitions и Control Worker; HMAC/control проверяются сохранённой регрессией. Никакого использования старых control keys или создания вымышленных control ACK. Actual research telemetry — Ascon; AES/Kuz совместимость проверена suite и byte equality working machinery, не новыми Stage14 static benchmarks.

Пилот9 captures/3781 observations исключён из primary:2726 Normal,202 ControlledViolation,853 unknown (22.56%). Bad credentials демонстрирует короткое независимое denial window без eligible packet: actor остаётся unknown; boundary guard не ослаблялся.

Основной сбор: **60 новых физических PCAP,60 experiments,30 matched acquisition blocks/30 broker realms**,6 software clients/12s per capture, частоты задавались интервалами0.35/0.45/0.60s с jitter0.08. Каждый block — отдельные TLS/keys/state; две captures block не считаются независимыми друг от друга.30 повторных блоков на одном host — условные экспериментальные группы, а не доказанная универсальная IID independence. Ещё fault/contrast captures существуют только для reliability, не входят в60. Негативные копии и per-case views не засчитываются как новые физические captures.

Primary: **35203 observations:27969 Normal,1894 ControlledViolation,5340 unknown (15.169%)**.426 TCP sessions:396 имеют Normal known support,28 ControlledViolation,2 вообще не имеют known rows. Unknown boundary rows встречаются и в остальных sessions;28 sessions не равны1894 независимым нарушениям. Точные per-scenario/session counts в [coverage.json](reports/stage14/coverage.json).

Подтверждаются auth rejection,ACL denial,non-DUP replay через prior accepted+timed identity+независимый digest+PG replay, measured bounded_rate/pattern_change. Tampered остаётся unknown без точной receiver digest association. Anonymous auth reject не получает authenticated device ID. TLS handshake/закрытие,collector/observer completion,clock margins,drops,hashes проверяются на каждом источнике. Отсутствие witness/log/core/частичный capture даёт quarantine. Сценарий генератора не является label oracle.

## Oracle, независимость и split

Builder `labels_v2.py` и oracle `label_verification.py` не вызывают правила назначения друг друга. Oracle повторно читает физический PCAP, проверяет TCP stream/packet identities,features/time,broker/witness/PG evidence и ожидаемые допустимые labels. Это независимость программных правил, не внешний абсолютный ground truth. Нет заявления100% accuracy разметки.

[Collection plan](STAGE14_COLLECTION_PLAN.md) и JSON зафиксированы до primary. Seeds уникальны между blocks; общий broker/device authority объединяет matched captures в один block. Partition predeclared:train18/validation6/test6 blocks (36/12/12 captures). Пересечения PCAP SHA,capture,session,linked block запрещены. Source hashes привязаны к immutable acquisition receipts с реально выполнявшимися container code hashes/image IDs. Один host и общий collector/генератор остаются confounders.

Feature schema `tcp-packet-passive-v1`:frame.len,tcp.len,tcp.flags,tcp.window_size_value,tcp.time_delta. IP/ports/device/capture/session/scenario/label metadata не predictors. TLS не отключался. Старый exact-five-feature crossing fingerprint guard сохранён:удалены19872 known rows (11946/3678/4248), хотя одинаковый vector не доказывает одинаковый packet. Это консервативное заранее заданное transductive isolation правило использует holdout feature values, меняет population/prevalence и ограничивает генерализацию; оно не скрывается.

| Partition | Rows | Normal | CV | Positive blocks | Normal blocks |
|---|---:|---:|---:|---:|---:|
| train |6085|5669|416|15|18|
| validation |1816|1700|116|5|6|
| holdout |2090|1986|104|5|6|

Минимумы1000 Normal и5 class-bearing independent groups на часть выполнены, capture/session/source пересечений нет. Dataset family lightcrypto-lab-v1,version stage14-lightcrypto-lab-v1. Unknown сохранён в observations, исключён из supervised known CSV. Новый приватный frozen plan `.local-runtime/stage14/study/plan.json`, старые plans не менялись. [Gate](reports/stage14/data-quality-gate.json), [freeze](STAGE14_FROZEN_SPLIT.md), [integrity](reports/stage14/frozen-integrity-final.json).

Bad_credentials имеет только7 known positive packet rows/4 sessions в полном primary и0 positive validation support; class-level PASS не доказывает per-scenario power. Tampered отсутствует как confirmed CV. При отсутствии класса recall=null/not_evaluable, не100%.

## Offline обучение и единственная оценка

5 RF base candidates (baseline,balanced,balanced_subsample,2 tuned),4 IF (baseline,StandardScaler,2 tuned с заранее заданными scaler settings),14 заранее заданных baseline ablations =23 fits. Точный candidate set в [training-config.json](reports/stage14/training-config.json); никакого дополнительного multiclass training. IF fit только Normal train; preprocess fit только train. Validation выбирает candidate/threshold/aggregation mean|max|fraction при target FPR0.05. Missing features не подменяются необоснованным0; fixed schema/imputer contract сохранён.

Перед test сохранены artifacts,preprocessing,thresholds,split hashes,freeze и pre-test audit. Один frozen23-model test battery: не23 независимых holdouts. Final freeze SHA `c8dccff4bbd36c8346269c60045af04f02d3d70974f5754b7732fd172332fc40`. После test не было retuning/refitting/reselection, исходные test.json и модели совпали по SHA. Не устанавливались в Model Registry.

| Validation-selected result | Precision | Recall | F1 | FPR | PR-AUC | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| packet RF tuned1 |0.910714|0.490385|0.637500|0.002518|0.543880|0.737986|
| packet IF tuned0 |0.097561|0.076923|0.086022|0.037261|0.140871|0.798062|
| session RF subsample |0.666667|0.400000|0.500000|0.013699|см.JSON|см.JSON|
| session IF tuned1 |0.333333|0.200000|0.250000|0.027397|см.JSON|см.JSON|

Результаты не высококачественный универсальный детектор. RF пропустил53/104 positive observations,IF96/104. Всего5 positive sessions в holdout:RF обнаружил2,IF1. Bootstrap по6 blocks,не по2090 независимым packets; статистическая мощность мала. Session winners отличаются от packet winners, выбраны на validation. Все23 reports,confusions,per-capture иper-scenario результаты,feasibility,wide cluster intervals сохранены. [RF/IF подробности](STAGE14_RF_IF_RESULTS.md).

9 семейств PNG/SVG в [figures](reports/stage14/figures):labels,independent units,train/validation distributions,base metrics,4confusions,ablations. Только сохранённые raw counts/metrics,без интерполяции или дополнительных holdout predictions.

## Обнаруженные ошибки и методологические ограничения

1. Observer мог остаться process-alive после потери MQTT связи. Теперь unexpected disconnect/loop failure делает capture incomplete и abort; реальные observer/broker fault tests подтверждают.
2. Once-only защита была привязана только к experiment directory. Synthetic red test после научной оценки обнаружил обход новым directory. Добавлены dataset-wide exclusive marker и запрет нового plan/train после consumption. Старый marker мигрирован явно после оценки, original report не изменён. Реальный повторный вызов отклонён до inference,0 prediction calls; никакой второй научной оценки. Это post-evaluation hardening, не задним числом пройденный предварительный gate.
3. Полный quantitative leakage/shortcut audit завершён после test, только train/validation. Это отклонение требуемого порядка. Metadata/group/fingerprint restrictions были заранее, но нельзя заявить завершённый quantitative pre-test shortcut audit. Выборы после этого не менялись;11 conflicting-label feature vectors и228 repeated-value rows вtrain/validation показывают предел5features. Не удалялись неудобные samples по scores.
4. Один host/stack,короткие sessions,weak bad_credentials support,rate/size/TLS-lifecycle shortcuts,множество сравнений и единственный model seed остаются ограничениями. Недостаточно данных для переносимости/редких атак. External/domain-shift validation=not_performed. Новые источники не загружались; metadata-only audit MQTTEEB-D V2/IoT-SFC V6 не означает совместимую external evaluation.

## Негативные проверки, failures и безопасность

30real-source corruption cases и27/27 behavioral mutations detected. Детали и промежуточные failed red/harness outputs сохранены. Assertions действительно проверяют oracle/grouping/preprocessing/train-test/threshold/unknown/QoS/label scope/trust/noControl/partialsource/once-only поведение; Syntax/Import failures не засчитываются.

Настоящие Collector/Observer shutdown,PG/Mongo outages,broker logging loss,receiver restart,quota/watchdog failures,replay vs QoS1,wrong epoch/sequence/tag,broker reconnect проверены отдельно. Все fault raw sources сохранены. Broker reconnect обоснованно quarantine из-за witness loss. Memory case имеет реальный OOM event;disk case искусственно малый лимит,не физический full disk. [Матрица/время/ограничения](STAGE14_RELIABILITY_RESULTS.md), [transport contrast](reports/stage14/transport-contrast.json).

Security audit:884 независимых новых telemetry keys в34 realms,сравнение с1318 историческими значениями;reuse0. Permission violations0,exact-secret matches0 в1774 проверенных файлах,425container-log tails (последние1000строк),3applicationimages. Это bounded scan,не обещание отсутствия секретов во всех когда-либо созданных log bytes. Raw PCAP/CSV/joblib/private credentials не добавлены вGit,на внешние сервисы не передавались.23 model files дополнительно приведены к0600,содержимое не менялось. [security-release.json](reports/stage14/security-release.json).

Ascon/AES/Kuz parser/provider,nonce/replay/usage authority,PGadmission/Outbox,manualcontrol иStage13worker/state/engine byte-equal исходному baseline. Policy DRY_RUN,trusted_detector=false,manual-onlycontrol сохранены. Kuz lab-only,Magma absent. Новых webviews нет;RBAC/CSRF/XSS regression сохранена. ВсеStage14 services остановлены,volumes/raw/state остаются;ничего не удалено.

## Воспроизведение и следующий этап

[Команды и provenance](reports/stage14/execution-summary.json). Existing paths immutable: повтор train/test запрещён. Для новой научной итерации требуются новый независимый collection plan,dataset,holdout и отдельное разрешённое исследование, а не сброс markers. Простое повторение проекта не создаёт независимый hardware domain.

Безопасная остановка конкретного нового realm:

```bash
.venv/bin/python -m scripts.stage14_lab stop --directory .local-runtime/stage14/contrast
```

Перезапуск служебного stand с сохранёнными ключами/volumes допускает только существующий state; missing used volume fail-closed. Primary скрипт не сбрасывает частичный предыдущий run. Для повторной suite нужен новый project/root/subnet, затем stage14_lab baseline --build;он останавливает свои сервисы и не трогает старые volumes. Нельзя запускать train/test над уже использованным holdout.

Научно допустимый вывод: создан более обоснованный software-lab dataset и воспроизводимая ограниченная оценка способности5passive features различать corroborated Normal/ControlledViolation. Недопустимые выводы: доказанный malicious packet attribution,качество real-world IDS,переносимость наIoT/ARM,вероятность атаки из RF score,production/ГОСТ certification,готовность ML→control.

Готова база для следующего **отдельно разрешённого** исследования transport observer: sensor placement,stream identity,online tcp.time_delta,timed provenance,freshness,unattributed observations. Рекомендуемый этап15: сначала независимые temporal/host domains и перспективный pre-registered shortcut audit; затем shadow-only online feature-equivalence validation без control. Online IDS не включён. См.[readiness](STAGE14_ONLINE_IDS_READINESS.md). Этап15 не начинался.
