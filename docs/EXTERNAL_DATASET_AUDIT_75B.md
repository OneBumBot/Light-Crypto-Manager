# Внешние источники — только аудит пригодности

Проверено10.11.2026. Наборы не объединяются с собственным лабораторным dataset.
Не обучались новые модели, не выполнялся external benchmark. Проверены страницы
первоисточников и небольшой metadata/header preview; многогигабайтных загрузок нет.
Указанная лицензия относится к конкретной версии dataset, не только к статье.

| Источник | Доступность / условия | Единица / labels / независимость | MQTT/TLS и наша схема |
|---|---|---|---|
| MQTT_UAD v1 | Figshare public API, CC BY4.0;3CSV, суммарно83,266,698bytes. Получены metadata и первые4096bytes одного файла через HTTP206; сохранён только header | Packet/frame; normal/DoS/MitM/Intrusion по описанию авторов.3scenario files не доказывают ≥15 независимых capture groups/class. Нужны исходные capture/session boundaries и аудит frame labels | CSV header содержит frame.len, но нет tcp.len/flags/window_size_value/time_delta; MQTT topic/username/password/message columns не допустимы как passive TLS predictors. Текущий packet schema import несовместим; отсутствующие поля не заполняем0 |
| MQTTEEB-D repository v2 | Public Mendeley page, CC BY4.0. Публикуются raw и processed variants; файлы не загружены, exact sizes/hash не установлены | Packet-derived CSV, сценарии normal и нескольких MQTT нарушений. По исходной статье4loops; фактическая независимость captures, split coverage и точность разметки **не проверены** | Заявлены TCP-level признаки; наличие всех5полей и единицы delta требуют raw header/PCAP audit. MQTT application fields пассивно недоступны под TLS. Normalized/SMOTE variants нельзя использовать как готовый unbiased split |
| IoT-SFC v2, проверенная repository V6 | Mendeley V6 page CC BY4.0; latest listing указывает V8, но её содержимое не получено. Архивы не загружены | Смешанные Zeek log records, а не packets: conn/DNS/MQTT/SSL и др.; labels по attack sessions. Нужны проверка UID joins и независимых sessions. Нельзя склеивать sparse heterogeneous logs как одинаковые observations | Flow/connection counters и SSL metadata потенциально видимы при TLS; MQTT plaintext fields — нет. Прямо несовместим с tcp-packet-passive-v1. Требуется отдельный flow/log contract |

MQTT_UAD provenance: [Figshare dataset v1](https://doi.org/10.6084/m9.figshare.24420958.v1),
[авторская статья](https://pmc.ncbi.nlm.nih.gov/articles/PMC12590255/).
В metadata записано intellectual-property registration LE-229-18; публичная CC BY4.0
не отменяет требований attribution и проверки конфиденциальности raw credentials.
Downloaded bytes не являются полным dataset; SHA metadata/header нельзя выдавать
за SHA исходных больших CSV. Figshare предоставил MD5 файлов; локальный SHA-256
всего dataset отсутствует, потому что файлы не скачивались.

MQTTEEB-D: [repository V2](https://doi.org/10.17632/jfttfjn6tr.2),
[исходная статья](https://pmc.ncbi.nlm.nih.gov/articles/PMC12332880/).
Брать в будущем только raw data до глобальной нормализации/SMOTE и сохранять loops,
времена, capture/session provenance. Указание real-world testbed не доказывает
подходящий независимый holdout или переносимость на наш TLS-контур.

IoT-SFC: [repository V6](https://doi.org/10.17632/j9xffc2psb.6).
Заявленный CSV13.85GB/49,902,287records/88columns, archives857MB+927MB и attack
logs105KB — описание автора, не результат локального пересчёта. Сравнение версий
показывает, что лицензия менялась (V5 CC BY-NC3.0, V6 CC BY4.0): перед загрузкой
фиксировать конкретный DOI/условия, не переносить автоматически на latest V8.

Решение: все три остаются **кандидатами отдельной внешней оценки**, без импортов,
переименования отсутствующих признаков и искусственного zero-fill. Собственный
набор имеет отдельную ontology ControlledViolation и не называется real-attack
benchmark. На7.5c сначала заморозить методику, затем получить совместимый источник
с проверенной capture/session независимостью и untouched holdout.
