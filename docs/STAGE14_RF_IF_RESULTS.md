# Этап 14 — RF/IF: результаты единственного holdout

Оценка выполнена один раз на исходниках `20a6bab`. Выбор кандидатов, threshold и session aggregation зафиксирован до test. Все 23 результата сохранены в [rf-if-results.json](reports/stage14/rf-if-results.json); сводка и 14 ablations — в [model-comparison.csv](reports/stage14/model-comparison.csv). Никакого выбора лучшего кандидата по test не проводилось.

Holdout: 2090 сохранённых packet observations (1986 Normal,104 ControlledViolation),78 sessions (73 Normal,5 ControlledViolation),6 acquisition blocks/12 captures. Label unit — connection_activity/window_behavior; положительная строка не доказывает конкретный malicious packet.

| Заранее выбранный победитель | Precision | Recall | F1 | FPR | PR-AUC | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| rf_binary / research75-rf_tuned_1-binary | 0.910714 | 0.490385 | 0.637500 | 0.002518 | 0.543880 | 0.737986 |
| if / research75-if_tuned_0-binary | 0.097561 | 0.076923 | 0.086022 | 0.037261 | 0.140871 | 0.798062 |
| rf_session / research75-rf_subsample-binary | 0.666667 | 0.400000 | 0.500000 | 0.013699 | 0.352512 | 0.526027 |
| if_session / research75-if_tuned_1-binary | 0.333333 | 0.200000 | 0.250000 | 0.027397 | 0.223524 | 0.584932 |

Packet RF: TN1981/FP5/FN53/TP51; IF: TN1912/FP74/FN96/TP8. Session RF: TN72/FP1/FN3/TP2; session IF: TN71/FP2/FN4/TP1. Accuracy вспомогательная: доля Normal в holdout95.02%; всегда-Normal baseline уже имеет такую accuracy.

## Validation и пороги

RF supervised; IF fitted только на Normal train. Imputer/scaler fitted только на train. Validation FPR target0.05. Все validation distributions, feasibility, thresholds, confusion matrices и timings сохранены в train-freeze.json. RF probabilities не калиброваны как вероятность реальной атаки.

- rf_binary: `research75-rf_tuned_1-binary`; packet threshold `{'threshold': 0.9335469686522243, 'method': 'validation-only attack F1 under empirical normal FPR constraint; no test tuning', 'empirical_fpr_target': 0.05, 'validation_normal': 1700, 'validation_attack': 116, 'status': 'selected', 'validation_attack_f1': 0.7539267015706806}`; frozen session method `mean`, session threshold `0.24018363741290058`.

- if: `research75-if_tuned_0-binary`; packet threshold `{'threshold': 0.5971711560322518, 'method': 'validation-only attack F1 under empirical normal FPR constraint; no test tuning', 'empirical_fpr_target': 0.05, 'validation_normal': 1700, 'validation_attack': 116, 'status': 'selected', 'validation_attack_f1': 0.3179916317991632}`; frozen session method `mean`, session threshold `0.6134362036202531`.

- rf_session: `research75-rf_subsample-binary`; packet threshold `{'threshold': 0.9, 'method': 'validation-only attack F1 under empirical normal FPR constraint; no test tuning', 'empirical_fpr_target': 0.05, 'validation_normal': 1700, 'validation_attack': 116, 'status': 'selected', 'validation_attack_f1': 0.723404255319149}`; frozen session method `mean`, session threshold `0.19333333333333336`.

- if_session: `research75-if_tuned_1-binary`; packet threshold `{'threshold': 0.652579820387762, 'method': 'validation-only attack F1 under empirical normal FPR constraint; no test tuning', 'empirical_fpr_target': 0.05, 'validation_normal': 1700, 'validation_attack': 116, 'status': 'selected', 'validation_attack_f1': 0.06451612903225806}`; frozen session method `fraction`, session threshold `0.10344827586206896`.

## Per-scenario packet recall выбранных packet-моделей

| Scenario | RF recall | IF recall | Holdout rows (Normal+CV) |
|---|---:|---:|---:|
| regular | not_evaluable | not_evaluable | 620 |
| jitter | not_evaluable | not_evaluable | 334 |
| qos1_retry | not_evaluable | not_evaluable | 139 |
| bad_credentials | 0.000000 | 1.000000 | 312 |
| forbidden_acl | 0.000000 | 0.500000 | 174 |
| replay | 0.000000 | 0.047619 | 124 |
| tampered | not_evaluable | not_evaluable | 0 |
| bounded_rate | 0.729167 | 0.000000 | 184 |
| pattern_change | 0.500000 | 0.156250 | 203 |

Сценарии имеют лишь1–2 test groups; bad_credentials крайне мало positive rows и отсутствует положительная validation support. Tampered не имеет подтверждённых положительных меток и не оценивается. Нельзя выдавать эти значения за устойчивую оценку редких атак. Session и capture metrics всех кандидатов доступны в исходном JSON.

## Неопределённость и shortcuts

Cluster bootstrap:200 resamples acquisition blocks,6 clusters, условная независимость в одном host. Интервалы широкие и являются описательной оценкой, а не доказательством переносимости. Пакеты не считались независимыми экспериментами. Worst-case и per-capture metrics сохранены без удаления неудобных captures.

Ablations были заранее заданы:all5/no frame.len/no time_delta/no window/no flags/timing-only/size-only ×RF/IF baseline. Их23-model matrix не использовалась для post-test перевыбора. Графики строятся из сохранённых metrics; новых holdout predictions после оценки не делали.

Полный количественный descriptive leakage audit выполнен после holdout только на train/validation. Это отклонение порядка работы: результаты не использовались для выбора, но нельзя утверждать завершённый количественный pre-test shortcut audit. Metadata exclusion/group guards/fingerprint purge были зафиксированы раньше.

Один Docker host, общий stack/CA configuration, короткие sessions, сильный fingerprint purge и сценарные транспортные эффекты ограничивают выводы. External/domain-shift validation=not_performed. Detection time=not_measured_offline. Успешный offline test не доказывает online IDS.

## Обнаруженная lifecycle ошибка

После единственной оценки synthetic red test обнаружил обход once-only через новый experiment directory. Исправлен dataset-scoped marker и запрет нового plan/train для использованного holdout. Исходный marker мигрирован с явной after-the-fact записью; оригинальный test не перезаписан. Реальная повторная попытка заблокирована до inference (0 prediction calls). Вычислительные методы/thresholds/models не менялись; patch и red/green reports сохранены. Файловые guards не являются защитой от владельца, согласованно копирующего/меняющего всё хранилище.
