# Независимость и единица оценки

30 acquisition blocks/30 broker realms, fresh CA/Ascon keys/SQLite/DB per realm;60 primary captures, unique physical source digests. Matched normal/violation captures одной инфраструктуры — одна группа. Repeated literal lab001 относится к разным private broker/key authorities, не заявляется разными физическими устройствами. Общий host/OS/producer/collector остаётся confounder; новые PID/time/UUID сами по себе не доказывают IID.

Пререгистрированное fold=(repeat+scenario_index)%5:18/6/6 blocks train/validation/test;36/12/12 captures. Нет capture/session/source-PCAP/group intersections. Source receipts проверяют совпадение group/project/config и disjoint seed identity; physical-copy duplicates запрещены. Никакого random-row split/oversampling.

После фиксированного crossing-fingerprint guard:train6085 rows(5669 normal/416 positive),validation1816(1700/116),test2090(1986/104). Independent positive groups15/5/5, normal18/6/6. Допустимая нижняя поддержка соблюдена, но5 positive sessions/6blocks вholdout — малая statistical power, не сильная оценка редких нарушений.

Из29863 known rows удалены11946/3678/4248 crossing feature-value rows по исходным частям. Это совпадение5значений, не копирование физических packets. Guard transductively использует feature collisions всех preregistered частей, был задан до collection; меняет выборку/условную prevalence и ограничивает переносимость. Retained metrics не описывают весь raw TLS stream. Таблица/распределения: reports/stage14/independence-analysis.json.

Packet rows не единицы независимости. Метрики отдельно packet,session(known-row aggregation),per-capture known subset. Bootstrap resamples6 acquisition blocks, а не12 paired captures/2090packets. Интервалы условны на независимость повторных блоков внутри одного host; cross-host/day/hardware independence не подтверждена.
