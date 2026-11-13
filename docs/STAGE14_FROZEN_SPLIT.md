# Frozen split

Collection-plan SHA c936b1f7f140a3274ab50c222364e1e3f941c951675e56974fc836a26b9f66c9 — записан до pilot/primary. Новый dataset SHA313ca398bf15d0ba88578faf208f5c5b3abdd584b4714d2bba042f3f2312d3e3. Linked split SHA b5beecdd4f9811022dc89f9acee70312fc46a7883a3bc85c20203e518785501f.

Новый private plan .local-runtime/stage14/study/plan.json; старый .local-runtime/stand75b/plan.json и другие plans не изменены.36/12/12captures в18/6/6 blocks. Indices и source/package/config hashes проверяются повторным детерминированным linked split; coherently rewritten indices с train/test overlap запрещены. Raw sources/source receipts immutable.

Train/validation selection завершены до final test; freeze SHA c8dccff4bbd36c8346269c60045af04f02d3d70974f5754b7732fd172332fc40. Единственная23-model holdout battery выполнена на commit20a6bab. Все параметры/thresholds/session choices/models сохранены, retuning не выполнялся.

После оценки выявлена guard weakness: per-experiment marker можно обойти другим experiment directory. Red test на synthetic empty evaluator воспроизвёл это без основной выборки. Добавлен dataset-scoped exclusive marker и запрет новых plan/train на consumed holdout. Existing actual-test marker перенесён в новый guard с явной after-the-fact migration receipt; исходная оценка не повторялась. Контрольный вызов на настоящем dataset отвергнут с prediction_calls0 и прежним test.json hash. Post-test diff содержит только lifecycle guards, не preprocessing/model/metrics/threshold logic; raw20a6bab method snapshot неизменён. Оба источника/время изменений отмечены в reports, не заявляется, что новый guard существовал до первой оценки.
