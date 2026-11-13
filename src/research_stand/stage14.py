"""Stage14 offline source/independence gate. No fitting, prediction or live control."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from src.classifier.research.schema import FEATURES,packet_frame
from src.classifier.research.datasets import canonical_hash
from .pcap_audit import load_json,digest


def checked_collection_plan(path):
 plan=load_json(path);expected=plan.pop('sha256')
 if hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()!=expected:raise ValueError('Collection plan hash mismatch')
 return {**plan,'sha256':expected}


def linked_split(frame,partitions,min_normal_rows=1000,min_class_groups=5):
 """Preregistered acquisition blocks; no random row or per-file independence."""
 if type(min_normal_rows) is not int or min_normal_rows<1000 or type(min_class_groups) is not int or min_class_groups<5:raise ValueError('Stage14 support cannot be weakened')
 if not {'independence_group','session_id','source_pcap_sha256'}<=set(frame):raise ValueError('Missing independence metadata')
 if frame.independence_group.isna().any() or not frame.independence_group.map(lambda v:isinstance(v,str) and bool(v)).all():raise ValueError('Invalid acquisition group')
 if set(frame.independence_group)-set(partitions) or set(partitions.values())!={'train','validation','test'}:raise ValueError('Unassigned acquisition group')
 names=['train','validation','test'];parts=[np.flatnonzero(frame.independence_group.map(partitions).to_numpy()==name) for name in names]
 before={name:len(p) for name,p in zip(names,parts)}
 # Value collisions are not duplicate physical packets. Retain the original conservative guard explicitly.
 fp=pd.util.hash_pandas_object(packet_frame(frame),index=False);sets=[set(fp.iloc[p]) for p in parts];cross=(sets[0]&sets[1])|(sets[0]&sets[2])|(sets[1]&sets[2]);removed=[]
 for i,p in enumerate(parts):parts[i]=p[~fp.iloc[p].isin(cross).to_numpy()];removed.append(len(p)-len(parts[i]))
 summary={}
 for name,p in zip(names,parts):
  sub=frame.iloc[p];support={str(label):int(sub.loc[sub.label==label].independence_group.nunique()) for label in [0,1]};normal=int((sub.label==0).sum());positive=int((sub.label==1).sum())
  if normal<min_normal_rows or min(support.values())<min_class_groups or positive<1:raise ValueError('Insufficient independent group/class/normal support after fixed fingerprint isolation: '+name+' '+str(dict(normal=normal,positive=positive,groups=support)))
  summary[name]=dict(rows=len(sub),normal=normal,positive=positive,attack=positive,class_groups={str(label):int(sub.loc[sub.label==label].capture_id.nunique()) for label in [0,1]},independent_class_groups=support,captures=int(sub.capture_id.nunique()),sessions=int(sub.session_id.nunique()),scenarios={str(k):int(v) for k,v in sub.scenario_category.value_counts().items()})
 for field in ['capture_id','session_id','source_pcap_sha256','independence_group']:
  sets=[set(frame.iloc[p][field]) for p in parts]
  if any(sets[a]&sets[b] for a,b in [(0,1),(0,2),(1,2)]):raise ValueError('Linked split intersection: '+field)
 value=dict(schema_version=1,method='stage14_preregistered_acquisition_blocks_60_20_20',indices=[p.tolist() for p in parts],group_partitions=partitions,minimum_normal_rows=min_normal_rows,minimum_class_captures=min_class_groups,minimum_class_independent_groups=min_class_groups,summary=summary,before_fingerprint_isolation=before,duplicate_purged_rows=removed,duplicate_policy='all crossing exact feature values removed, not proof of physical duplicates',independent_devices_verified=False,single_host_domain=True)
 value['sha256']=canonical_hash(value);return value


def verify_source_receipt(folder,plan):
 from scripts.stage14_collect import check_source
 receipt=load_json(Path(folder)/'acquisition.json')
 if load_json(Path(folder)/'ground-truth.json').get('synthetic_unit_fixture'):raise ValueError('Synthetic fixture cannot authorize scientific dataset')
 expected={r['config']['experiment_id']:r for r in plan['primary']}
 eid=Path(folder).name
 if eid not in expected or receipt['experiment_id']!=eid or receipt['status']!='complete':raise ValueError('Failed/unplanned acquisition source')
 spec=expected[eid]
 for name in ['group','partition','project']:
  if receipt[name]!=spec[name]:raise ValueError('Source acquisition grouping conflict: '+name)
 if receipt['config']!=spec['config'] or receipt['plan_sha256']!=plan['sha256']:raise ValueError('Acquisition plan/config conflict')
 actual=check_source(Path(folder))
 if actual['pcap_sha256']!=receipt['pcap_sha256'] or actual['source_hashes']!=receipt['source_hashes']:raise ValueError('Acquisition receipt source hashes changed')
 return receipt


def training_gate(data,manifest):
 source=load_json(manifest)
 if source.get('dataset_version')!='stage14-lightcrypto-lab-v1':return
 gate=load_json(Path(data).parent/'data-quality-gate.json')
 if gate.get('status')!='PASS' or gate.get('dataset_sha256')!=digest(data) or gate.get('manifest_sha256')!=digest(manifest):raise ValueError('Stage14 training forbidden: data quality gate not PASS or frozen source changed')
 required=['raw_sources','label_oracle','source_novelty','independence','feature_schema','strict_split','frozen_holdout','no_resource_truncation']
 if any(gate.get('checks',{}).get(k) is not True for k in required):raise ValueError('Stage14 gate dimensions incomplete')
 if gate.get('training_permission')!='OFFLINE_RESEARCH_ONLY' or gate.get('trusted_detector') is not False:raise ValueError('Stage14 trust contract')

    # Recheck independent evidence, not merely coherently updated CSV hashes.
 from .label_verification import reconcile
 plan=checked_collection_plan(gate['collection_plan'])
 if plan['sha256']!=gate['collection_plan_sha256']:raise ValueError('Frozen collection plan changed')
 captures=Path(gate['raw_capture_root'])
 if {r['capture_id'] for r in source['raw_files']}!={r['config']['experiment_id'] for r in plan['primary']}:raise ValueError('Missing planned source capture')
 for row in source['raw_files']:verify_source_receipt(captures/row['capture_id'],plan)
 reconcile(Path(data).parent,captures)
 frame=pd.read_csv(data)
 if linked_split(frame,source['stage14_group_partitions'])['sha256']!=gate['split_sha256']:raise ValueError('Frozen linked split changed')
