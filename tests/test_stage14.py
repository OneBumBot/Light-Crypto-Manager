"""Program-only fault fixtures; never scientific MQTT/TLS ground truth."""
import json
from types import SimpleNamespace
import pytest
from src.research_stand import observer


@pytest.mark.parametrize('lost',[False,True])
def test_observer_connection_loss_cannot_be_success(tmp_path,monkeypatch,lost):
 class Client:
  def __init__(self,*args,**kwargs):pass
  def connect(self,*args):pass
  def loop(self,**kwargs):
   self.on_subscribe(self,None,1,[SimpleNamespace(is_failure=False)],None)
   if lost:
    self.on_disconnect(self,None,None,1,None)
    return observer.mqtt.MQTT_ERR_CONN_LOST
   (tmp_path/'stop-observer').touch();return observer.mqtt.MQTT_ERR_SUCCESS
  def disconnect(self):self.on_disconnect(self,None,None,0,None)
  def loop_write(self):pass
 monkeypatch.setattr(observer.mqtt,'Client',Client);monkeypatch.setattr(observer,'configure_client',lambda *args,**kwargs:None)
 if lost:
  with pytest.raises(RuntimeError,match='observer incomplete'):observer.run(tmp_path,3)
 else:observer.run(tmp_path,3)
 result=json.loads((tmp_path/'mqtt-observer.json').read_text());assert result['completed'] is (not lost);assert result['disconnected_unexpectedly'] is lost;assert result['ready_observed']


def test_stage14_namespaces_are_narrow():
 from scripts.stage14_lab import PREFIX
 assert PREFIX.fullmatch('lcm-stage14-ground-truth-block-00')
 assert not PREFIX.fullmatch('lightcrypto') and not PREFIX.fullmatch('lcm-stage13-policy-qa') and not PREFIX.fullmatch('lcm-stage14-ground-truth-a;echo-x')


def split_fixture():
 import pandas as pd
 rows=[];parts={}
 for g in range(16):
  group='g'+str(g);parts[group]='train' if g<6 else 'validation' if g<11 else 'test'
  for i in range(203):
   rows.append(dict(zip(['frame.len','tcp.len','tcp.flags','tcp.window_size_value','tcp.time_delta'],[100+i%10,48,24,4096,g*10+i*.001]),independence_group=group,capture_id='c'+str(g),session_id=f'c{g}:'+('p' if i==202 else 'n'),source_pcap_sha256=str(g),scenario_category='fixture',label=int(i==202)))
 return pd.DataFrame(rows),parts


def test_linked_split_preserves_shared_groups_and_fixed_assignment():
 from src.research_stand.stage14 import linked_split
 f,p=split_fixture();r=linked_split(f,p)
 assert [r['summary'][n]['independent_class_groups']['1'] for n in ['train','validation','test']]==[6,5,5]
 assert all(f.iloc[i].independence_group.map(p).eq(name).all() for i,name in zip(r['indices'],['train','validation','test']))
 assert linked_split(f,p)==r


@pytest.mark.parametrize('field',['capture_id','session_id','source_pcap_sha256'])
def test_shared_lineage_cannot_hide_behind_new_capture_name(field):
 from src.research_stand.stage14 import linked_split
 f,p=split_fixture();f.loc[f.independence_group=='g11',field]=f.loc[f.independence_group=='g6',field].iloc[0]
 with pytest.raises(ValueError,match='intersection'):linked_split(f,p)


def test_fixed_gate_support_cannot_be_lowered():
 from src.research_stand.stage14 import linked_split
 f,p=split_fixture()
 with pytest.raises(ValueError,match='cannot be weakened'):linked_split(f,p,min_class_groups=1)
 f=f.loc[f.independence_group!='g11']
 with pytest.raises(ValueError,match='Insufficient'):linked_split(f,p)


def test_stage14_blocked_training_never_allows_fit(tmp_path):
 from src.research_stand.stage14 import training_gate
 from src.research_stand.pcap_audit import digest
 data=tmp_path/'dataset.csv';data.write_text('private fixture')
 manifest=tmp_path/'dataset.manifest.json';manifest.write_text(json.dumps({'dataset_version':'stage14-lightcrypto-lab-v1'}))
 gate=tmp_path/'data-quality-gate.json';gate.write_text(json.dumps({'status':'BLOCKED_BY_INDEPENDENCE','dataset_sha256':digest(data),'manifest_sha256':digest(manifest)}))
 with pytest.raises(ValueError,match='training forbidden'):training_gate(data,manifest)


def source_fixture(tmp_path):
 from test_ground_truth_hardening import fixture
 folder=fixture(tmp_path)
 def patch(name,**fields):
  p=folder/name;value=json.loads(p.read_text());value.update(fields);p.write_text(json.dumps(value))
 patch('capture.json',started_at=1.0,finished_at=10.0)
 patch('ground-truth.json',experiment_started_at=1.0,experiment_finished_at=10.0)
 p=folder/'ground-truth.json';v=json.loads(p.read_text());v['experiment']['duration']=9;v['clock']['wall_monotonic_drift_seconds']=0;p.write_text(json.dumps(v))
 patch('core.json',postgres='available',mongo='available')
 (folder/'mqtt-observer.json').write_text(json.dumps(dict(source='independent_read_only_mqtt_fanout',completed=True,ready_observed=True,overflow=False,disconnected_unexpectedly=False,events=[{'fixture_only':True}])))
 return folder


@pytest.mark.parametrize('fault',['observer_lost','observer_empty','broker_missing','pg_missing','partial_capture','early_generator','nonfinite_clock','clock_drift'])
def test_source_loss_and_partial_data_cannot_be_complete(tmp_path,fault):
 from scripts.stage14_collect import check_source
 folder=source_fixture(tmp_path);assert check_source(folder)['packets']>0
 name='mqtt-observer.json' if fault.startswith('observer') else 'broker-evidence.json' if fault=='broker_missing' else 'core.json' if fault=='pg_missing' else 'capture.json' if fault=='partial_capture' else 'ground-truth.json'
 p=folder/name;r=json.loads(p.read_text())
 if fault=='observer_lost':r['completed']=False
 elif fault=='observer_empty':r['events']=[]
 elif fault=='broker_missing':r['sessions']=[]
 elif fault=='pg_missing':r['postgres']='unavailable'
 elif fault=='partial_capture':r['finished_at']=2
 elif fault=='early_generator':r['experiment_finished_at']=2
 elif fault=='clock_drift':r['clock']['wall_monotonic_drift_seconds']=4
 else:r['clock']['boundary_margin_seconds']=float('nan')
 p.write_text(json.dumps(r))
 with pytest.raises(ValueError):check_source(folder)



def test_frozen_collection_plan_cannot_be_modified(tmp_path):
 import hashlib
 from src.research_stand.stage14 import checked_collection_plan
 p=tmp_path/'plan.json';payload={'schema_version':1,'seed':75,'groups':['a','b']};payload['sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();p.write_text(json.dumps(payload))
 assert checked_collection_plan(p)==payload
 payload['seed']=76;p.write_text(json.dumps(payload))
 with pytest.raises(ValueError,match='plan hash mismatch'):checked_collection_plan(p)


def replay_fixture(tmp_path):
 """Synthetic PCAP with independently represented replay predicates; not real traffic."""
 import csv,struct
 from test_ground_truth_hardening import fixture
 from src.research_stand.pcap_audit import digest
 folder=fixture(tmp_path,kind='forbidden_acl');truth=json.loads((folder/'ground-truth.json').read_text());broker=json.loads((folder/'broker-evidence.json').read_text());core=json.loads((folder/'core.json').read_text());rows=list(csv.DictReader((folder/'headers.csv').open()))
 data=(folder/'traffic.pcap').read_bytes();records=[];offset=24
 for row in rows:
  sec,micro,caplen,wirelen=struct.unpack_from('<IIII',data,offset);body=data[offset+16:offset+16+caplen];offset+=16+caplen
  if row['tcp.stream']=='1':row['frame.time_epoch']=str(float(row['frame.time_epoch'])+6)
  records.append((row,body,wirelen))
 records.sort(key=lambda v:float(v[0]['frame.time_epoch']));rebuilt=bytearray(data[:24]);last={}
 for i,(row,body,wirelen) in enumerate(records,1):
  stamp=float(row['frame.time_epoch']);sec=int(stamp);micro=round((stamp-sec)*1e6);row['frame.number']=str(i);row['tcp.time_delta']=str(stamp-last.get(row['tcp.stream'],stamp));last[row['tcp.stream']]=stamp;rebuilt+=struct.pack('<IIII',sec,micro,len(body),wirelen)+body
 (folder/'traffic.pcap').write_bytes(rebuilt)
 with (folder/'headers.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows([r for r,_,_ in records])
 truth['experiment']['scenario']='replay';truth['connections'][0]['closed_at']=7;broker['sessions'][0]['closed_at']=7
 actor=truth['connections'][1];actor['activity']='replay';actor['logical_device']='lab001'
 for field in ['attempt_started_at','tls_open_at','closed_at']:actor[field]+=6
 for action in actor['actions']:action['sent_at']+=6
 session=broker['sessions'][1];session['username']='device_lab001'
 for field in ['opened_at','authenticated_at','closed_at']:session[field]+=6
 for event in session['events']:event.update(kind='publish',topic='iot/sensors/lab001',at=event['at']+6)
 for action in actor['actions']:core['security_events'].append(dict(device_id='lab001',category='replay',key_epoch=action['key_epoch'],sequence_number=action['sequence_number'],occurred_at=action['sent_at']+.002))
 witness=dict(source='independent_read_only_mqtt_fanout',overflow=False,events=[dict(at=a['sent_at']+.001,candidate_identity=['lab001',a['key_epoch'],a['sequence_number']],payload_sha256=a['payload_sha256']) for c in truth['connections'] for a in c['actions']])
 for name,obj in [('ground-truth.json',truth),('broker-evidence.json',broker),('core.json',core),('mqtt-observer.json',witness)]: (folder/name).write_text(json.dumps(obj))
 for name in ['capture.json','extractor.json']:
  p=folder/name;obj=json.loads(p.read_text());obj['pcap_sha256']=digest(folder/'traffic.pcap')
  if name=='extractor.json':obj['csv_sha256']=digest(folder/'headers.csv')
  p.write_text(json.dumps(obj))
 return folder


@pytest.mark.parametrize('fault',[None,'missing_digest','wrong_digest','wrong_epoch','wrong_sequence','missing_prior','late_prior','qos1_normal'])
def test_replay_requires_independent_timed_identity_and_qos1_is_normal(tmp_path,fault):
 import pandas as pd
 from src.research_stand.dataset_v2 import build
 folder=replay_fixture(tmp_path/'raw');core=json.loads((folder/'core.json').read_text())
 if fault in ['missing_digest','wrong_digest']:
  p=folder/'mqtt-observer.json';w=json.loads(p.read_text())
  if fault=='missing_digest':w['events']=[]
  else:
   for e in w['events']:e['payload_sha256']='f'*64
  p.write_text(json.dumps(w))
 elif fault in ['wrong_epoch','wrong_sequence','missing_prior','late_prior']:
  for e in core['security_events']:
   if e['category']=='accepted':
    if fault=='wrong_epoch':e['key_epoch']=9
    if fault=='wrong_sequence':e['sequence_number']+=100
    if fault=='late_prior':e['occurred_at']=14
  if fault=='missing_prior':core['security_events']=[e for e in core['security_events'] if e['category']!='accepted']
  (folder/'core.json').write_text(json.dumps(core))
 elif fault=='qos1_normal':
  p=folder/'ground-truth.json';t=json.loads(p.read_text());t['experiment']['scenario']='qos1_retry';t['connections'][1]['activity']='normal';p.write_text(json.dumps(t))
  p=folder/'broker-evidence.json';b=json.loads(p.read_text())
  for e in b['sessions'][1]['events']:e['dup']=1
  p.write_text(json.dumps(b))
 out=tmp_path/'dataset';build(folder.parent,out);rows=pd.read_csv(out/'observations.csv',keep_default_na=False);actor=rows.loc[rows.connection_id=='connection-1']
 assert not actor.empty
 if fault is None:assert actor.ground_truth.eq('controlled_violation').any()
 elif fault=='qos1_normal':assert actor.ground_truth.eq('normal').any() and not rows.ground_truth.eq('controlled_violation').any()
 else:assert actor.ground_truth.eq('unknown').all()


def test_validation_selection_cannot_read_holdout(tmp_path,monkeypatch):
 import src.classifier.research.experiment as ex
 from test_research75 import fixture,settings
 data,manifest,_=fixture(tmp_path);path=tmp_path/'plan.json';p=ex.plan(data,manifest,settings(),path)
 from src.classifier.research.datasets import read_prepared
 frame,_=read_prepared(data,manifest);allowed=set(frame.iloc[p['split']['indices'][1]].packet_id);forbidden=set(frame.iloc[p['split']['indices'][2]].packet_id);original=ex.risk;calls=[]
 def observed(pipeline,x,algorithm):
  assert set(x.packet_id)<=allowed and not set(x.packet_id)&forbidden,'Threshold selection touched holdout'
  calls.append(len(x));return original(pipeline,x,algorithm)
 monkeypatch.setattr(ex,'risk',observed);ex.train(data,manifest,path,tmp_path/'models',tmp_path/'experiment');assert calls


def test_no_oversampling_or_fit_before_group_split(tmp_path,monkeypatch):
 import src.classifier.research.experiment as ex
 from test_research75 import fixture,settings
 from src.classifier.research.datasets import read_prepared
 data,manifest,_=fixture(tmp_path);frame,_=read_prepared(data,manifest);original=ex.prepare_split;observed=[]
 def split(x,*args,**kwargs):
  assert list(x.packet_id)==list(frame.packet_id) and not x.packet_id.duplicated().any(),'Source rows duplicated/resampled before split'
  observed.append(True);return original(x,*args,**kwargs)
 monkeypatch.setattr(ex,'prepare_split',split);ex.plan(data,manifest,settings(),tmp_path/'plan.json');assert observed


def test_coherently_modified_partition_still_rejected(tmp_path):
 from test_research75 import fixture,settings
 from src.classifier.research.experiment import plan,checked_plan
 from src.classifier.research.datasets import canonical_hash
 data,manifest,_=fixture(tmp_path);path=tmp_path/'plan.json';value=plan(data,manifest,settings(),path);value['split']['indices'][0].append(value['split']['indices'][2][0]);value['split'].pop('sha256');value['split']['sha256']=canonical_hash(value['split']);value.pop('plan_sha256');value['plan_sha256']=canonical_hash(value);path.write_text(json.dumps(value))
 with pytest.raises(ValueError,match='partition mismatch'):checked_plan(data,manifest,path)


def test_offline_risk_is_untrusted_unattributed_and_cannot_request_control(monkeypatch):
 import numpy as np
 from src.classifier.research.inference import predict
 from src.classifier.research.schema import PacketSchema,FEATURES,VERSION
 from src.device_control import server
 f,_=split_fixture();f['device_id']='UNTRUSTED';calls=[]
 monkeypatch.setattr(server,'request_switch',lambda *args,**kwargs:calls.append((args,kwargs)))
 class Model:
  classes_=[0,1]
  def predict_proba(self,x):return np.tile([.01,.99],(len(x),1))
 m=dict(task='network_ids',algorithm='rf_binary',feature_version=VERSION,mode='RESEARCH',trusted_detector=False,model_id='fixture',model_version='14.0.0',threshold=.5)
 records=predict(m,Model(),f.iloc[:3],VERSION,'packet')
 assert records and all(v['trusted_detector'] is False and v['binding']=='unattributed' for v in records)
 assert calls==[],'Offline RF inference attempted live control'
 matrix=PacketSchema().transform(f);assert list(matrix)==FEATURES and matrix.shape[1]==5
 m['trusted_detector']=True
 with pytest.raises(ValueError,match='trust invariant'):predict(m,Model(),f.iloc[:3],VERSION,'packet')


def test_coherent_source_metadata_cannot_replace_physical_pcap_digest(tmp_path):
 from test_ground_truth_hardening import fixture
 from src.research_stand.dataset_v2 import build
 folder=fixture(tmp_path/'raw')
 for name in ['capture.json','extractor.json']:
  p=folder/name;r=json.loads(p.read_text());r['pcap_sha256']='0'*64;p.write_text(json.dumps(r))
 with pytest.raises(ValueError,match='Source capture/header hash mismatch'):build(folder.parent,tmp_path/'dataset')


def test_declared_synthetic_capture_never_authorizes_research_dataset(tmp_path):
 from src.research_stand.stage14 import verify_source_receipt
 folder=source_fixture(tmp_path);(folder/'acquisition.json').write_text(json.dumps(dict(status='complete',experiment_id='capture')))
 with pytest.raises(ValueError,match='Synthetic fixture'):verify_source_receipt(folder,{'primary':[]})


def test_changed_frozen_configuration_cannot_reach_fit(tmp_path,monkeypatch):
 from test_research75 import fixture,settings
 import src.classifier.research.experiment as ex
 data,manifest,_=fixture(tmp_path);path=tmp_path/'plan.json';r=ex.plan(data,manifest,settings(),path);r['config']['seed']=1;path.write_text(json.dumps(r));original=ex.fit_candidate;called=[]
 def observed(*args,**kwargs):called.append(True);return original(*args,**kwargs)
 monkeypatch.setattr(ex,'fit_candidate',observed)
 try:ex.train(data,manifest,path,tmp_path/'models',tmp_path/'exp')
 except ValueError:pass
 assert not called,'Modified frozen configuration reached model fitting'


def test_session_aggregation_threshold_is_validation_only_and_unknown_scenario_not_perfect():
 import copy,numpy as np
 from src.classifier.research.group_metrics import calibrate,evaluation,sessions
 frame,_=split_fixture();scores=np.where(frame.label.to_numpy()==1,.9,.1);chosen=calibrate(frame,scores,.5,.05);before=copy.deepcopy(chosen)
 result=evaluation(frame,scores,.5,chosen,75)
 assert chosen==before and result['session']['recall']==1 and result['session']['fpr']==0
 assert result['per_scenario']['tampered']['status']=='not_evaluable' and result['per_scenario']['tampered']['metrics'] is None
 assert result['packet_cluster_uncertainty']['groups']==16
 bad=frame.copy();bad.loc[0,'label']=1
 with pytest.raises(ValueError,match='Ambiguous session'):sessions(bad,scores,'mean',.5)
 failed=calibrate(frame,np.full(len(frame),.5),.5,.05)
 assert failed['selected']['point']['status']=='no_detection_operating_point' and failed['selected']['validation']['recall']==0


@pytest.mark.parametrize('columns',[['device_id'],[['tcp.len']],[],['tcp.len','tcp.len']])
def test_ablation_never_accepts_identifiers_or_malformed_columns(columns):
 from src.classifier.research.schema import FeatureSubset
 from src.classifier.research.experiment import config_checked
 from test_research75 import settings
 f,_=split_fixture()
 with pytest.raises(ValueError,match='ablation'):FeatureSubset(columns).transform(f)
 config=settings();config['candidates'][0]['features']=columns
 with pytest.raises(ValueError,match='passive features'):config_checked(config)


def test_stage14_holdout_cannot_be_reopened_via_new_experiment_directory(tmp_path,monkeypatch):
 """No real holdout/model: isolate lifecycle guard using an empty synthetic evaluator."""
 import pandas as pd
 from src.classifier.research import experiment as ex
 from src.classifier.research.datasets import canonical_hash
 data=tmp_path/'dataset.csv';data.write_text('synthetic guard fixture only');manifest=tmp_path/'manifest.json';manifest.write_text('{}');plan=dict(plan_sha256='fixture-plan',config={'seed':75},split={'indices':[[],[],[]]});source=dict(dataset_version='stage14-lightcrypto-lab-v1',schema_version=1,synthetic=True)
 monkeypatch.setattr(ex,'checked_plan',lambda *args:(pd.DataFrame(),source,plan))
 for name in ['experiment-one','experiment-two']:
  folder=tmp_path/name;folder.mkdir();freeze=dict(plan_sha256='fixture-plan',models=[]);freeze['sha256']=canonical_hash(freeze);(folder/'freeze.json').write_text(json.dumps(freeze))
 ex.final_test(data,manifest,'unused',tmp_path/'no-models',tmp_path/'experiment-one')
 with pytest.raises(FileExistsError):ex.final_test(data,manifest,'unused',tmp_path/'no-models',tmp_path/'experiment-two')


def test_consumed_stage14_holdout_prevents_new_plan_or_train(tmp_path):
 from src.classifier.research import experiment as ex
 data=tmp_path/'data.csv';data.write_text('fixture');manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'dataset_version':'stage14-lightcrypto-lab-v1'}));(tmp_path/'stage14-holdout-started').write_text('already-used')
 with pytest.raises(ValueError,match='already consumed'):ex.plan(data,manifest,{},tmp_path/'new-plan')
 with pytest.raises(ValueError,match='already consumed'):ex.train(data,manifest,'missing-plan',tmp_path/'models',tmp_path/'new-experiment')
 assert not (tmp_path/'new-plan').exists() and not (tmp_path/'models').exists()
