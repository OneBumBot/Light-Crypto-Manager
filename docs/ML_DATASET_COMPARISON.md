# Аудит источников этапа 7.5

Дата2026-11-10. Данные и веса не публикуются; hashes/агрегаты доступны в reports.
Научные статьи не заменяют лицензию конкретного файла.

| Источник | Что проверено | Лицензия/доступ | Пригодность сейчас |
|---|---|---|---|
| MQTTset v5 | Официальные metadata/list API; исходный parser; raw bruteforce14501 строк; reduced330926 строк | Dataset metadata: CC BY-NC-SA4.0, версия5 от2021-07-14; публичные файлы получены без аккаунта | Raw TCP packet import работает, но одного normal capture недостаточно для нового независимого split |
| MQTT-IoT-IDS2020 | Страница Strathclyde/DOI и статья создателей; packet, uniflow, biflow — разные единицы | Landing page200; metadata CC BY4.0; UI загрузки предлагает login/subscription, архивы не получены | Внешний benchmark не выполнен; native IP length нельзя подменить Ethernet frame length |
| Edge-IIoTset | Исторический источник2219201 строк, frozen subset11851,3 fitted network artifacts | Локально предоставлен пользователем, условия публикации не подтверждены | Только неизменный исторический baseline; просмотренный test не используется для нового подбора |
| CICIoT2023 | UNB:105 устройств,33 атаки, PCAP/агрегированные CSV | Условия UNB требуют citation; не скачивался | Второстепенный domain-transfer кандидат, агрегаты нельзя смешивать с packets |
| TON_IoT | UNSW:network PCAP/Zeek, telemetry, ground-truth timestamps | Academic use с citation; коммерческое использование требует отдельной проверки условий; не скачивался | Разные задачи/схемы; OS данные не подключаются к системе |

Первоисточники:
[MQTTset article](https://www.mdpi.com/1424-8220/20/22/6578),
[Kaggle dataset](https://www.kaggle.com/datasets/cnrieiit/mqttset),
[dataset metadata API](https://www.kaggle.com/api/v1/datasets/view/cnrieiit/mqttset),
[Strathclyde](https://pureportal.strath.ac.uk/en/datasets/mqtt-iot-ids2020-mqtt-internet-of-things-intrusion-detection-data/),
[MQTT-IoT-IDS2020 article](https://strathprints.strath.ac.uk/75251/1/Hindy_etal_INC2020_Machine_learning_based_IoT_Intrusion_Detection_System.pdf),
[UNB](https://www.unb.ca/cic/datasets/iotdataset-2023.html),
[UNSW](https://research.unsw.edu.au/projects/toniot-datasets).

## MQTTset: фактические файлы и ограничения

Официальный listing: общий объём9570862030 bytes. Normal raw CSV
legitimate_1w.csv3303925599 bytes и normal PCAP capture_1w.pcap1093676216 bytes.
Для атак по одному raw CSV/PCAP: bruteforce, flood, malaria/DoS, malformed, slowite.
Raw attack rows не считаются автоматически отдельными независимыми captures:
tcp.stream1430 в bruteforce всё ещё относятся к одному исходному capture.

Получены ограниченные файлы: bruteforce.csv4239465 bytes,
mqttdataset_reduced.csv59392755 bytes, README и два parser/training source файла.
Их SHA-256, команды и реальные counts — stage75-data-access.json,
stage75-mqttset-audit.json, stage75-access.txt. Normal3.3GB и весь9.57GB архив
не загружались: это не устраняет отсутствие независимых normal captures.

Reduced classes: legitimate165463, dos130223, bruteforce14501,
malformed10924, slowite9202, flood613. 209499 совпадающих полных reduced строк
из330926. Это не доказательство копирования физических пакетов: после удаления
provenance разные пакеты могут иметь одинаковые признаки.

Author rawparsing_normal.py назначает target по исходному файлу, fillna(0),
удаляет frame.time_epoch/frame.number/tcp.stream/IP/ports, затем shuffle(seed10).
Итак, reduced labels — capture-scenario labels; per-packet attack ground truth
не проверен. В processingdata_ml.py categories кодируются до random-row split;
вариант separate train/test кодирует категории независимо. Augmented вариант
статьи реплицирует attacks; он не скачан и не используется до split.

Raw header содержит60 полей, включая MQTT payload/username/password. Эти поля
не загружаются нашим extractor, не входят в модель и не попадают в отчёты/образы.
Сохраняется только allowlist numeric TCP и provenance. Авторский код изучен как
текст, не запускался. Paper говорит о8 sensors, README содержит более длинную
таблицу; число достоверных физических устройств не выводится из IP cardinality.

## Что нужно для следующей научной оценки

Независимые raw captures с нормальным трафиком и атаками, сохранёнными timestamp,
session IDs и проверяемой разметкой (включая normal background во время attacks).
Предпочтительно повторные дни/запуски/устройства и окончательный untouched holdout.
Default gate требует1000 normal rows и5 содержащих соответствующий класс captures
в каждой части; нужны не менее15 captures с normal и15 с attack в сумме
(смешанные captures могут входить в обе категории). Одни новые имена файлов не
доказывают независимость. Возможен пересмотр требований только заранее, с явным
обоснованием статистической мощности, а не для получения красивых метрик.
