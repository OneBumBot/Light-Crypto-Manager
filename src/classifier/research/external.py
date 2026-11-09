"""Independent-source compatibility gate and frozen evaluation; no adaptation/refit."""
import json
from pathlib import Path
from src.classifier.ml.artifacts import load
from .datasets import read_prepared,canonical_hash
from .experiment import risk
from .metrics import binary_metrics,cluster_intervals


def evaluate_external(data,manifest_path,models_dir,experiment_dir,output):
    frame,source=read_prepared(data,manifest_path)
    folder=Path(experiment_dir);freeze=json.loads((folder/'freeze.json').read_text());digest=freeze.pop('sha256')
    if canonical_hash(freeze)!=digest:raise ValueError('Modified model selection freeze')
    if not (folder/'test.json').is_file():raise ValueError('Complete frozen internal test before independent external evaluation')
    results=[]
    for row in freeze['models']:
        model,pipeline=load(models_dir,row['model_id'],row['model_version']);original=model['dataset']
        if original['source_url']==source['source_url']:raise ValueError('Same source is not an independent external dataset')
        if set(f['sha256'] for f in original['raw_files'])&set(f['sha256'] for f in source['raw_files']):raise ValueError('Source capture content overlaps')
        if set(f['capture_id'] for f in original['raw_files'])&set(f['capture_id'] for f in source['raw_files']):raise ValueError('External capture identity overlap')
        if model['artifact_sha256']!=row['artifact_sha256'] or model['threshold']!=row['threshold']['threshold']:raise ValueError('Frozen external model modified')
        scores=risk(pipeline,frame,row['algorithm']);metrics=binary_metrics(frame.label,scores,model['threshold'],frame.attack_type,row['timing']['fit_attack_types'])
        metrics['uncertainty']=cluster_intervals(frame.label,(scores>=model['threshold']).astype(int),frame.capture_id)
        results.append(dict(model_id=row['model_id'],artifact_sha256=model['artifact_sha256'],threshold=model['threshold'],metrics=metrics,
            multiclass_type_evaluation='not merged across source taxonomies; this external route evaluates binary risk only'))
    result=dict(scope='independent_external_source',dataset=source,fit_performed=False,threshold_changed=False,results=results,
        synthetic=source['synthetic'],trusted_detector=False,
        limitations=['Source labels and capture independence require separate audit; scores are not calibrated probabilities'])
    with Path(output).open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return result
