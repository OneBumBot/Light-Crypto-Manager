# Независимая reconciliation и negative verification

Builder: dataset_v2/labels_v2. Oracle: label_verification, который не импортирует
и не вызывает builder, annotate, verdict или старый map_packets. Общие функции
только bounded чтение/hash/PCAP. Oracle отдельно вычисляет association/SYN/границы,
broker session outcomes, timed PG joins, ciphertext witness и window criteria.
Это два алгоритмических пути, но не два внешних научных эталона.

pcap_audit читает classic PCAP **потоково**, ≤16MiB/20000records. Ethernet/IPv4/TCP,
без fragments/truncation; другие форматы отклоняются. Независимо проверяет номера,
wire tuples, SYN/initial sequence/stream index, timestamps, lengths, flags,
window, TCP delta относительно tshark CSV. Структура формата:
[libpcap pcap-savefile(5)](https://man7.org/linux/man-pages/man5/pcap-savefile.5.html).
Это ограниченный reader проверенного стенда, не замена libpcap для произвольного PCAP.

По каждой физической packet identity сверяются source/capture/experiment/session/
packet IDs, connection ID, epoch, все5features, scenario/activity, scope/unit,
confidence, reason, device binding, source PCAP hash и binary label. Проверяются
Повторное использование одного PCAP под другим capture ID отклоняется builder и
отдельно oracle; experiment ID проверяется по источнику. Проверяются sets/counts/ordering: лишних/пропущенных/повторных строк нет; training table точно
равна известному subset observations. Unknown promotion запрещён. Производные
hashes проверяются, но НЕ заменяют логическую проверку.

В v1 legacy reconciliation повторяет слабые исторические правила отдельным
кодом, чтобы выявлять несоответствие CSV исходникам. Она прямо не аттестует labels.
В v2 отсутствующее независимое доказательство даёт unknown. Все исходные файлы
открываются read-only; новый output — immutable path; старый frozen plan не меняется.
PCAP/tables/evidence ограничены по размеру; observer≤4000events, PG≤10000rows,
суммарно≤100000observations. Переполнение/unsupported input → fail, не truncation.

## Независимые записи нового стенда

- `broker-evidence.json`: Docker timestamps, endpoint/client/username, CONNACK,
  ACL/PUBLISH/MID/DUP/session close; allowlist без passwords/payload.
- `core.json`: timed authenticated security_observations с row IDs/identity;
  `SET TRANSACTION READ ONLY`. Rejected device identity всегда null.
- `mqtt-observer.json`: отдельный read-only subscriber своим TLS connection,
  только CA+readonly web-role password **своего** lab broker; Ascon keys не mounted.
  Сохраняет canonical ciphertext-envelope SHA256 и untrusted AD candidate identity,
  не ciphertext/payload/credentials. Не делит network namespace с publisher:
  collector не принимает observer→broker за publisher→broker.

Local Docker/PG/MQTT sources независимы от producer flag, но доверяют владельцу
стенда и одному хосту. Нет подписи независимого регистратора; согласованная
перезапись всех evidence/PCAP владельцем не исключена. Clock/log delay, ambiguity,
model generalization и malicious packet accuracy этим audit не измеряются.

## Запуск

```bash
.venv/bin/python -m src.research_stand.dataset_v2 --captures /private/captures --output /private/new-v2.2
.venv/bin/python -m src.research_stand.label_verification --dataset /private/new-v2.2 --captures /private/captures --output /private/reconciliation.json
.venv/bin/python -m scripts.mutate_ground_truth --output /private/mutations.json
```

Mutation runner сначала требует успешный **unmutated baseline**, затем меняет
исходники исключительно в temporary copies. Syntax/import errors не засчитывает.
Positive pipeline tests должны упасть при испорченном builder; negative tests —
при пропущенном oracle check. Каждый targeted failure и exit code сохранён в
reports/stage75b-fix-mutations.json. Первоначальный слишком узкий target не поймал
удаление missing-broker guard; добавлен explicit no-source test, старый отчёт
сохранён как mutations-initial. Отдельный fixture-edit NameError исправлен; он
не является доказательством killed mutant. Для этого введён baseline preflight.

Реальные probes: scripts/verify_ground_truth_hardening.py, новый project/volumes.
A:normal TLS→PG/outbox/Mongo+TCP; B:control только на actor; C:journal/digest conflict
на private copies; D:реальный broker DUP1 normal; E:реальное завершение observer
во время генерации +отсутствующий journal; F:collector stop с socket/records checks.
Проверяются actual files/rows/counters/connections; строка PASS не служит oracle.
Документируются и неудачные промежуточные попытки. Coverage checks не делают
model.predict и не открывают финальный ML holdout для настройки.
