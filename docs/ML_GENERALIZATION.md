# Переносимость и scientific status

## Что не доказано

Нет нового корректного independent internal test для MQTTset, нет внешнего
MQTT-IoT-IDS2020 benchmark. Не обучены новые реальные RF/IF; не подтверждены рост
Recall/F1 или контроль population FPR. Старый Edge test просмотрен и используется
только как неизменная историческая диагностика, не новый tuning target.

Нормальный MQTTset capture один;1430 TCP streams одного attack capture не дают
1430 независимых captures. В reduced удалены время/IP/stream/packet number, поэтому
нельзя восстановить capture/session leakage или отделить одинаковые feature rows
разных реальных пакетов. Производные датасеты, использующие MQTTset/2020, не
рассматриваются как независимые без proof of provenance; не скачивались.

## Уровни будущей проверки

- Internal validation: выбор parameters и operating point только здесь.
- Frozen internal test: same source, новые целые captures, без split overlap.
- External source: исходники другого авторского dataset, совместимый extractor,
  независимые captures/hashes. Сохранить исходную class prevalence.
- TLS deployment: отдельные captures именно защищённого контура. Plaintext MQTT
  атакующие сценарии могут иначе выглядеть после TLS/auth/ACL; wire size меняется.
- Device transfer: новые физические устройства/дни/сети, clock/link type/NAT/packet
  loss. IP или tcp.stream не является криптографически подтверждённым device ID.

Ни packet CSV, ни uni/biflow агрегаты нельзя смешивать без общего определения
наблюдения. Native2020 ip len и MQTTset frame.len не тождественны. Неизвестные
поля нельзя заполнить нулями. При несовместимости external evaluator отвергает
источник вместо фиктивного successful benchmark.

## Неопределённость

Capture bootstrap resamples captures целиком, не отдельные коррелированные packets.
Предполагает независимость captures, которую одни разные IDs не доказывают.
При<5 captures CI недоступны. Zero-FP bootstrap может дать[0,0]; это не доказательство
нулевого риска. Отдельная верхняя95% граница относится к вероятности хотя бы одного
FP в capture, не к packet-level FPR. Empirical validation target5% не объявляется
подтверждённой population гарантией. Precision зависит от prevalence при deployment.

## Telemetry IF — самостоятельная будущая работа

Температура/влажность не становятся Network IDS features. Старые модели остаются
DEMO,320 synthetic records/4 устройства; их собственные predictions не labels.
Нужны длительные реальные normal baselines на устройствах с различными режимами,
достоверные measurement/receipt times и отдельно размеченные контролируемые fault
интервалы (sensor failure, drift, environment changes, missing data). Кибератаки
размечать независимо от физических аномалий. Разделять по времени/устройствам,
проверять causality и unseen-device поведение; не менять payload/Mongo schema ради
выдуманных labels. ARM64/Raspberry Pi время/энергия не измерялись.

## Policy Engine

DRY_RUN, trusted_detector=false, only Ascon, TLS/ACL/replay и роли не меняются.
Новый offline-network-risk-v1 не является разрешённым live Policy Signal. Он
не содержит подтверждённой device binding; Policy allowlist новых feature versions
не расширена. Новые артефакты не установлены в ML worker. Улучшение Recall в будущем
само по себе не докажет повышение криптостойкости или применение профиля.

Новый packet workflow ограничен TCP; UDP/ICMP исключения учитываются в provenance,
не входят в quality denominator и не подтверждают защиту от этих атак. Сравнение
с широким IoT corpus должно отдельно показывать эту границу покрытия.
