# Кандидаты для дополнения Network IDS — поиск 2026-11-09

Дополнительный запрос пользователя: найти данные, способные улучшить RF. Ни один
новый набор из списка пока не скачан/не обучен в проекте. Улучшение не доказано.
Основной этап6 продолжается; ниже план отдельного исследования, не изменение
проверенного test до получения желаемой метрики.

| Приоритет / набор | Проверено по первоисточнику | Применение и границы |
|---|---|---|
| 1 MQTTset, Vaccari et al. | [Статья создателей](https://pmc.ncbi.nlm.nih.gov/articles/PMC7698741/), [авторская публикация данных](https://www.kaggle.com/datasets/cnrieiit/mqttset): MQTT raw captures; нормальный трафик и DoS/SlowITe/flood/brute-force/malformed сценарии | Наиболее близок MQTT части. Условия конкретной загруженной версии CSV/PCAP проверить отдельно; CC BY статьи не заменяет dataset license. Не равен MQTT-IoT-IDS2020 |
| 2 MQTT-IoT-IDS2020, Hindy et al. | [University of Strathclyde](https://pureportal.strath.ac.uk/en/datasets/mqtt-iot-ids2020-mqtt-internet-of-things-intrusion-detection-data/), DOI10.21227/bhxy-ep04:12 simulated sensors/broker/camera/attacker, normal+4 attack scenarios; PCAP, packet/uni-flow/bi-flow | Хороший независимый MQTT holdout; симуляционный origin и иная гранулярность признаков. Доступ и условия конкретного IEEE DataPort файла подтвердить перед скачиванием |
| Дополнительный MQTT_UAD | [Статья создателей, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12590255/): три CSV, 67 полей на frame; normal/DoS/MitM/intrusion, реальный лабораторный MQTT стенд | Кандидат для независимой проверки MitM и посторонних клиентов. Схема отличается от Edge; endpoint Figshare вернул403 при проверке, файлы/лицензия конкретной версии не проверены. Не считать сразу совместимым train augmentation |
| 3 CICIoT2023 | [UNB CIC](https://www.unb.ca/cic/datasets/iotdataset-2023.html):105 устройств,33 атаки, PCAP и extracted CSV | Более широкая внешняя проверка IoT атак. Готовые агрегаты отличаются от Edge packet columns; потребуются общий extractor/schema и согласование taxonomy |
| Отдельный исследовательский источник TON_IoT | [UNSW](https://research.unsw.edu.au/projects/toniot-datasets): есть network и telemetry, PCAP/Zeek, independent ground-truth timestamps; академическое использование разрешено, коммерческое — по согласованию с автором | Для разных задач отдельные источники/метрики. Нельзя автоматически считать network attack label доказательством физической sensor аномалии. OS компоненты/Windows не добавляются в проект |

Первый выбор — MQTTset; MQTT-IoT-IDS2020 сначала держать внешним test. CICIoT2023
использовать для следующей проверки domain transfer. Это рекомендация по близости
задачи/доступности raw capture, а не обещание роста F1.

## Что необходимо до объединения

1. Зафиксировать source/version/license/hash каждого файла; проверить capture,
   device/session IDs и timestamp semantics, а также отсутствие копий одних PCAP
   под разными именами/из разных зеркал.
2. Извлечь одну и ту же единицу наблюдения и признаки одним parser/version.
   Packet rows и агрегированные bidirectional flows нельзя смешивать как одни
   наблюдения. Protocol-absent0 допустим только как единая документированная
   семантика extractor; отсутствующую неизвестную CSV колонку нельзя просто занулить.
3. Согласовать binary normal/attack. Для multiclass использовать явную общую
   taxonomy или раздельные задачи; разные имена атак не всегда эквивалентны.
4. Dataset/capture/device provenance хранить для split/audit, исключить из X.
   Проверить placeholder/label proxies, disjoint connected groups и duplicates.
   Балансировать train по source/class при обосновании, не модифицировать final test.
5. Сравнить на новом независимом holdout: текущий RF, новый RF, IF baseline;
   precision/recall/F1/FPR/PR-AUC, per-source и per-device результаты. Сохранить
   результат, даже если добавление данных ухудшит переносимость.

Уже просмотренный Edge holdout остаётся замороженным диагностическим результатом,
а не целевой функцией дальнейшего выбора набора/признаков. Доля normal train,
представительность normal validation и provenance leakage важны не меньше числа
строк. В текущем исследовании бинарный RF при validation FPR constraint выбрал
threshold>1, то есть не выдаёт attack-сигналов; RF multiclass также плохо перенёс
нормальный holdout. Дополнительный CSV сам по себе это не исправляет.

Нормальная телеметрия собственного TLS/MQTT стенда и физических устройств нужна
для Telemetry Anomaly Detection отдельно; network datasets не подменяют её.

## TLS и наблюдаемость

MQTT-specific поля в открытых captures могут относиться к незашифрованному MQTT.
В нашем TLS-контуре пассивный сетевой коллектор не получает plaintext MQTT payload
и внутренние MQTT заголовки. Перед переносом модели требуется явно определить
доступные transport/flow признаки либо доверенную instrumentation на стороне
брокера/клиента. Не отключать TLS ради совместимости с датасетом.

Найденные агрегированные наборы BCCC MQTT используют MQTTset и MQTT-IoT-IDS2020
как источники ([описание создателей](https://www.yorku.ca/research/bccc/ucs-technical/cybersecurity-datasets-cds/bccc-mqtt-augmented-ids-2026-developed-and-designed-for-large-language-models-llm/)).
Их нельзя считать независимым test по отношению к этим исходникам без проверки
provenance и пересечений. Поэтому они не предложены как первоочередное дополнение.
