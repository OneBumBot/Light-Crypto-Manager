# Контролируемые сценарии 7.5b

Все действия — только `broker:8883` внутри internal-сети отдельного проекта.
Нет произвольного адреса/порта, словаря паролей, внешнего сканирования или flooding.
Каждый процесс завершает клиентов, сохраняет счётчики и журнал. Аварийная остановка:
Ctrl-C orchestrator либо `docker compose … stop lab-devices traffic-collector`.
Это не останавливает receiver/relay/DB/ML/Policy. SIGTERM orchestration и watchdog
описаны в DATASET_COLLECTION; принудительное завершение процесса может оставить
неполный захват, который нельзя включать в dataset.

| scenario | Действие | Разметка и подтверждение |
|---|---|---|
| regular | Корректная telemetry v2 через индивидуальный TLS/ACL | normal после PG accepted |
| jitter | Допустимый случайный сдвиг интервала с фиксированным seed | normal |
| reconnect | Disconnect и новое MQTT/TLS соединение после двух измерений | normal; новый connection ID |
| restart | Пересоздание MQTT client object; новые ID/сокет | normal; полный generator process также новый между captures |
| normal_burst | Кратковременный ×2 рост интенсивности в пределах общего limiter | normal, не автоматически атака |
| qos1_retry | Закрыть сокет до чтения PUBACK; reconnect тем же Paho client | normal даже при AEAD replay-отказе; DUP подтверждается sanitized Paho log flag |
| bad_credentials | Одна попытка с заведомо неверным тестовым password | controlled_violation при MQTT CONNACK reject; device identity не подтверждена |
| forbidden_acl | Один QoS1 publish в запрещённый topic | controlled_violation только при совпавшем client ID в Denied PUBLISH брокера; PUBACK недостаточен |
| replay | Сначала отдельное нормальное соединение с принятым пакетом; затем повтор того же ciphertext/sequence | controlled_violation при PG replay с точной исходной идентичностью |
| tampered | Изменить байт AEAD ciphertext тестового устройства | local AEAD reject + изолированный receiver rejected counter; серверное событие остаётся без device ID |
| bounded_rate | Ограниченное ×2 изменение частоты одного actor | Лабораторное отклонение шаблона, не доказанный DoS |
| pattern_change | Чередование интервалов ×0.5/×1.5 одного actor | Лабораторное отклонение шаблона, не доказанная атака |

В mixed run один actor и остальные normal clients. У каждого подключения есть
жизненный интервал и socket tuple. Пакеты другого устройства не наследуют метку
actor. Даже на actor connection метка относится к **активности соединения**, а не
доказывает вредоносность каждого TCP ACK. SYN/TLS handshake и границы могут быть
unknown. Один AEAD reject без контролируемого журнала не является ground truth.

Pilot:4 запуска,8 клиентов. Основная матрица:30 paired conditions × normal/mixed,
8/12/16/20 клиентов из общего пула24, интервалы0.3/0.5/0.7s, duration6s,
jitter0.08s, seed75000+i. Сценарии чередуются по шести типам; никаких новых моделей.
Запуски последовательные, предыдущие клиенты завершаются; это fresh processes,
TLS/TCP sessions и capture identities, но не доказательство статистической
независимости от общего хоста/ПО/стека.
