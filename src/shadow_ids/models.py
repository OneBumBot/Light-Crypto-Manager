"""Only packaged, reviewed Stage14 artifacts. Never fits, recalibrates or opens old data."""
import hashlib,json,math
from pathlib import Path
from .features import FEATURES,VERSION

def frozen():return json.loads(Path(__file__).with_name('frozen.json').read_text())['models']
def load_models(root,roles):
 from src.classifier.ml.artifacts import verify,load
 allowed=frozen();out={}
 if not roles or len(roles)!=len(set(roles)) or not set(roles)<=set(allowed):raise ValueError('Unauthorized model role')
 for role in roles:
  pin=allowed[role];meta,path=verify(root,pin['model_id'],pin['model_version'])
  if hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()!=pin['manifest_sha256'] or meta['artifact_sha256']!=pin['artifact_sha256'] or meta['threshold']!=pin['threshold'] or meta['feature_version']!=VERSION or meta.get('mode')!='RESEARCH' or meta.get('trusted_detector') is not False or meta.get('preprocessing',{}).get('feature_order')!=list(FEATURES):raise ValueError('Frozen artifact contract mismatch')
  _,pipeline=load(root,pin['model_id'],pin['model_version']);out[role]=(pin,pipeline)
 return out

def risk(pipeline,frame,algorithm):
 # Exact frozen Stage14 scoring formula, without importing train/plan/oracle.
 from src.classifier.research.metrics import scores_checked
 if algorithm=='if':return scores_checked(-pipeline.score_samples(frame))
 classes=list(pipeline.classes_);normal='Normal' if 'Normal' in classes else 0
 if normal not in classes:raise ValueError('Fitted normal class missing')
 return scores_checked(1-pipeline.predict_proba(frame)[:,classes.index(normal)])

def scores(loaded,events):
 import numpy as np,pandas as pd
 from src.classifier.research.schema import packet_frame
 if not events:return {}
 for event in events:
  features=event['features']
  if event.get('feature_version')!=VERSION or list(features)!=list(FEATURES) or event.get('status')!='FEATURE_READY':raise ValueError('Feature contract/context')
  if any(type(x) not in (int,float) or not math.isfinite(x) for x in features.values()):raise ValueError('Missing/nonfinite feature')
 frame=pd.DataFrame([e['features'] for e in events],columns=FEATURES);packet_frame(frame)
 out={}
 for role,(pin,pipeline) in loaded.items():
  values=risk(pipeline,frame,'if' if role.startswith('if') else 'rf')
  if len(values)!=len(events) or not np.isfinite(values).all():raise ValueError('Invalid inference scores')
  out[role]=[float(x) for x in values]
 return out
