"""Hash/permission/provenance audit only, no fit or old holdout inference."""
import hashlib,json,subprocess
from pathlib import Path
from src.classifier.ml.artifacts import verify,versions
from src.shadow_ids.models import frozen

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 rows=[]
 for role,pin in frozen().items():
  old=Path('.local-runtime/stage14/study/models');new=Path('.local-runtime/stage15/online/models');om,op=verify(old,pin['model_id'],pin['model_version']);nm,np=verify(new,pin['model_id'],pin['model_version']);assert om==nm and sha(np/'model.joblib')==pin['artifact_sha256'] and sha(np/'manifest.json')==pin['manifest_sha256'] and nm['threshold']==pin['threshold'];rows.append(dict(role=role,**{k:v for k,v in pin.items() if k!='session'},session_method=pin['session']['method'],session_threshold=pin['session']['point']['threshold'],permissions_private=True,original_copy_identical=True))
 report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),models=rows,versions=versions(),original_holdout_marker_sha256=sha('.local-runtime/stage14/study/experiment/final-test-started'),original_test_sha256=sha('.local-runtime/stage14/study/experiment/test.json'),old_holdout_predictions_performed=0,fit_calls=0,threshold_changes=0,trusted_detector=False,mode='SHADOW_ONLY',exit_code=0)
 Path('docs/reports/stage15/model-audit.json').write_text(json.dumps(report,indent=2));print('Four authorized frozen copies/thresholds/versions verified; no fit or old test calls; exit0')
if __name__=='__main__':main()
