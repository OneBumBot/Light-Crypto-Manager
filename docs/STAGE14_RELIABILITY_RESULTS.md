# Этап14 — реальные отказы и отрицательные проверки

Все источники находятся в новых Stage14 projects. Никаких старых volumes, destructive reset, down-v или model installation. Scientific60 captures завершены до этих failure tests; fault captures не добавлялись в frozen dataset.

## Настоящие процессы и сервисы

[reliability-core.json](reports/stage14/reliability-core.json): настоящий observer child shutdown и collector stop-after2s прерывают генерацию, сохраняют raw evidence, дают failed/quarantined. Продолжение PG admission/Outbox проверялось отдельно. Поля no-model-training в этом файле относятся к reliability probe, а не ко всему этапу: научные23 fits выполнены отдельно.

[service-faults.json](reports/stage14/service-faults.json):

| Fault | Наблюдаемый результат | Длительность проверки, с |
|---|---|---:|
| PostgreSQL остановлен | quarantine | 9.92 |
| MongoDB остановлена | quarantine | 11.93 |
| Broker logging unavailable | quarantine | 16.79 |
| Receiver restart | complete diagnostic capture, исключён из dataset | 12.76 |
| Tight disk watchdog | quarantine | 4.00 |
| Collector memory24MiB | quarantine, настоящий Docker OOM event | 12.28 |
| Collector CPU0.01 | readiness watchdog, quarantine | 14.98 |

Это время выполнения fault probe, а не гарантированное recovery RTO. Disk case использует намеренно малый1-byte limit при реально измеренном размере, не заполняет физический диск. После восстановления Outbox pending0, quotas восстановлены; raw источники и volumes сохранены. Partial capture не объявляется complete.

## Security replay и нормальный QoS1

[transport-contrast.json](reports/stage14/transport-contrast.json):7 реальных сценариев. QoS1 retry имеет4 broker DUP и остаётся Normal/unknown (0 ControlledViolation). Controlled replay подтверждён broker/witness/PG и имеет45 positive rows; это не45 независимых replay attacks. Wrong epoch,wrong sequence,tag corruption имеют PG reject и unknown actor labels: точная passive атрибуция не выдумывается. Broker reconnect разрывает обязательный observer и даёт quarantine; receiver restart сохраняет пригодность diagnostic capture. Crypto/parser/admission code не менялся. Никаких predictor server categories и model predictions в этих probes.

## Source и oracle negatives

[real-negatives.json](reports/stage14/real-negatives.json):30 изменений копий настоящих источников; оригиналы неизменны. PCAP absent/truncated/hash, timestamps/nonfinite/drift/boundaries, broker/witness/PG identity/digest/epoch/sequence, coherent CSV+manifest tampering, unknown promotion, duplicate physical capture и label scope проверяются независимо. Изменённые копии не засчитываются как новые captures/experiments.

[mutations-verified.json](reports/stage14/mutations-verified.json):27/27 поведенческих дефектов обнаружены, unmutated baseline exit0, mutant tests exit1 именно по assertion/поведению. Не засчитываются SyntaxError/ImportError/dependency failures. Сохранены неуспешные предварительные mutation harness отчёты: после добавления второго once-only guard старый broad selector попадал не в тот guard; selector уточнён, защиту не удаляли. Все финальные27 повторно проверены.

## Полная регрессия

Новый isolated regression project, настоящие PG/Mongo, исходные тесты сохранены: **967 passed,0 skipped,53.44s,exit0**. Baseline922/0/exit0. Старые KAT Ascon/AES/Kuz, tag negatives, TLS/ACL/replay/nonce, control/effective/recovery, Outbox/Mongo, RBAC/CSRF, ground-truth v2.2 и Stage13 golden/throughput checks остаются в suite. Web views не менялись, отдельный новый browser journey этап14 не запускался. Отчёт: full-regression.txt и full-regression.commands.json.

Проверки script-based research fault integration находятся вне pytest count. Они имеют отдельные команды/exit codes. Все Stage14 services остановлены после проверок, приватные данные остаются для воспроизведения. Никакого post-test refit/retuning.
