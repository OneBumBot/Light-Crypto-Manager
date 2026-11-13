"""Program fixtures only; real parity is a separate network experiment."""
import io,json,math,struct
from pathlib import Path
import pytest
from src.shadow_ids.features import Flows,Unavailable,FEATURES,packet
from src.shadow_ids.journal import Journal

def frame(sequence=1,flags=2,window=74,src=1111,dst=8883,payload=b''):
 ip=bytearray(20);ip[0]=0x45;ip[2:4]=(40+len(payload)).to_bytes(2,'big');ip[9]=6;ip[12:16]=bytes([10,0,0,1]);ip[16:20]=bytes([10,0,0,2]);tcp=bytearray(20);tcp[:4]=struct.pack('!HH',src,dst);tcp[4:8]=sequence.to_bytes(4,'big');tcp[12]=0x50|((flags>>8)&15);tcp[13]=flags&255;tcp[14:16]=window.to_bytes(2,'big');return bytes(12)+b'\x08\x00'+bytes(ip)+bytes(tcp)+payload

def p(time=1,**kwargs):
 raw=frame(**kwargs);return packet(raw,len(raw),time)
def event(n=1):return dict(event_id='e'+str(n),ordinal=n,capture_id='capture',mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound')

def test_first_and_bidirectional_delta_and_raw_window():
 f=Flows();a=f.accept(p());assert list(a['features'])==list(FEATURES);assert a['features']['tcp.time_delta']==0 and a['features']['tcp.window_size_value']==74
 b=p(time=1.2,flags=16);b['wire']=tuple(reversed(b['wire']));assert f.accept(b)['features']['tcp.time_delta']==pytest.approx(.2)
@pytest.mark.parametrize('value',[None,float('nan'),float('inf'),True,-1,'1'])
def test_timestamp_unavailable(value):
 with pytest.raises(Unavailable):p(time=value)
def test_negative_delta_is_not_clamped():
 f=Flows();f.accept(p());r=f.accept(p(time=.5,flags=16));assert r['status']=='FEATURE_UNAVAILABLE';assert r['features']['tcp.time_delta']<0;assert f.accept(p(time=2,flags=16))['status']!='FEATURE_READY'
def test_two_streams_not_shared():
 f=Flows();f.accept(p());r=f.accept(p(time=2,src=2222));assert r['features']['tcp.time_delta']==0 and r['session']=='2';assert f.accept(p(time=3,flags=16))['features']['tcp.time_delta']==2
def test_reused_tuple_resets_generation():
 f=Flows();a=f.accept(p());f.accept(p(time=2,flags=4));r=f.accept(p(time=3,sequence=99));assert r['session']!=a['session'] and r['features']['tcp.time_delta']==0
@pytest.mark.parametrize('flags',[16,18,17,4])
def test_missing_syn_insufficient(flags):assert Flows().accept(p(flags=flags))['status']=='INSUFFICIENT_CONTEXT'
def test_gap_requires_new_generation():
 f=Flows();f.accept(p());f.gap();assert f.accept(p(time=2,flags=16))['status']=='INSUFFICIENT_CONTEXT';assert f.accept(p(time=3,sequence=100))['status']=='FEATURE_READY'
def test_syn_retransmission_not_new_generation():
 f=Flows();a=f.accept(p());b=f.accept(p(time=1.1));assert a['session']==b['session'] and b['features']['tcp.time_delta']==pytest.approx(.1)
@pytest.mark.parametrize('kind',['truncated','ethernet','ipv6','fragment','flags','ip_length','tcp_length'])
def test_unsupported_not_scored(kind):
 raw=bytearray(frame());original=len(raw)
 if kind=='truncated':raw=raw[:-1]
 if kind=='ethernet':raw[12:14]=b'\x00\x00'
 if kind=='ipv6':raw[12:14]=b'\x86\xdd'
 if kind=='fragment':raw[20:22]=b'\x20\x00'
 if kind=='flags':raw[46]=0x52
 if kind=='ip_length':raw[16:18]=b'\xff\xff'
 if kind=='tcp_length':raw[46]=0x10
 with pytest.raises(Unavailable):packet(bytes(raw),original,1)
def test_flow_bound_expiry():
 f=Flows(limit=1,expiry=2);f.accept(p());f.accept(p(src=2222));assert len(f.rows)==1;assert f.accept(p(time=5,flags=16))['status']=='INSUFFICIENT_CONTEXT'
def test_journal_duplicate_and_atomicity(tmp_path):
 db=Journal(tmp_path/'shadow.db');assert db.append(event());assert not db.append(event());assert db.db.execute('select count(*) from events').fetchone()[0]==1
 with pytest.raises(ValueError):db.complete({'id':'e1'},[dict(model_id='x',mode='SHADOW_ONLY',trusted_detector=True,device_binding='unbound')])
 assert len(db.pending())==1
 db.close()
def test_explicit_overflow(tmp_path):
 db=Journal(tmp_path/'shadow.db');db.append(event(),capacity=1)
 with pytest.raises(OverflowError):db.append(event(2),capacity=1)
 assert len(db.pending())==1;db.close()
def test_stale_clears_predictions_and_overflow_visible(tmp_path):
 db=Journal(tmp_path/'shadow.db');db.append(event());db.complete({'id':'e1'},[dict(model_id='x',mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound')]);db.status('capture',dict(heartbeat=1,queue_overflow=3));db.status('worker',dict(heartbeat=1));s=db.snapshot(now=100);assert not s['available'] and not s['results'];assert s['capture']['queue_overflow']==3;db.close()
@pytest.mark.parametrize('key,value',[('mode','RESEARCH'),('trusted_detector',True),('device_binding','device-alpha')])
def test_no_authenticated_device_or_trust_promotion(tmp_path,key,value):
 db=Journal(tmp_path/'shadow.db');e=event();e[key]=value
 with pytest.raises(ValueError):db.append(e)
 db.close()
def test_untrusted_model_role_rejected_before_load(tmp_path):
 from src.shadow_ids.models import load_models
 with pytest.raises(ValueError,match='Unauthorized'):load_models(tmp_path,['arbitrary-upload'])
def test_no_model_is_unavailable_not_normal(tmp_path):
 from src.shadow_ids.worker import process
 db=Journal(tmp_path/'shadow.db');e={**event(),'status':'FEATURE_READY','capture_timestamp':1,'feature_ready_at':2,'observer_id':'x','feature_version':'tcp-packet-passive-v1'};db.append(e);process(db,{},db.pending(),'MissingArtifact');rows=[json.loads(r[0]) for r in db.db.execute('select value from results')];assert rows and all(r['score'] is None and r['comparison'] is None and r['inference_status']=='MODEL_UNAVAILABLE' and r['device_binding']=='unbound' for r in rows);db.close()
def test_features_missing_metadata_order_and_version_rejected():
 from src.shadow_ids.models import scores
 good=dict(status='FEATURE_READY',feature_version='tcp-packet-passive-v1',features=dict(zip(FEATURES,[54,0,2,74,0])))
 for change in [dict(feature_version='network-core-v1'),dict(features={'device_id':'alpha',**good['features']}),dict(features=dict(reversed(list(good['features'].items())))),dict(features={**good['features'],'tcp.time_delta':None})]:
  with pytest.raises(ValueError):scores({},[{**good,**change}])
def test_stream_reader_truncated_record():
 from src.shadow_ids.pcap import record
 with pytest.raises(ValueError):record(io.BytesIO(b'\x01'),'<',1000000,65535)

def test_session_scores_are_causal_prefixes(tmp_path):
 from src.shadow_ids.sessions import aggregate
 db=Journal(tmp_path/'shadow.db')
 for n,score in [(1,.1),(2,.9)]:
  db.append(event(n));result=dict(event_id='e'+str(n),model_id='research75-rf_subsample-binary',model_role='rf_session',session_id='c:1',score=score,comparison=score>=.9,capture_timestamp=n,inference_finish=n+.1,mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound');db.complete({'id':'e'+str(n)},[result])
  values=db.session_values();assert values[0]['score']==pytest.approx(.1 if n==1 else .5);assert values[0]['through_timestamp']==n and not values[0]['final']
 values=aggregate(db,True);assert values[0]['final'] and values[0]['through_timestamp']==2;db.close()
def test_no_policy_or_control_side_effects(tmp_path,monkeypatch):
 from src.shadow_ids.worker import process
 import src.device_control.server as control
 import src.policy.state as state
 def forbidden(*args,**kwargs):raise AssertionError('Shadow emitted control or Policy signal')
 monkeypatch.setattr(control,'request_switch',forbidden)
 monkeypatch.setattr(state,'process',forbidden)
 # Offline source error remains a local journal record, never a trusted feed.
 db=Journal(tmp_path/'shadow.db');e={**event(),'status':'FEATURE_UNAVAILABLE','capture_timestamp':1,'feature_ready_at':2,'observer_id':'x','feature_version':'tcp-packet-passive-v1'};db.append(e);process(db,{},db.pending(),'Unavailable');assert db.db.execute('select count(*) from results').fetchone()[0]==4;db.close()
def test_worker_cannot_start_before_parity(tmp_path):
 from src.shadow_ids.worker import run
 p=tmp_path/'parity.json';p.write_text(json.dumps(dict(status='BLOCKED')))
 with pytest.raises(ValueError,match='parity gate'):run(tmp_path,tmp_path,['rf_binary'],3,p)
def test_complete_retry_does_not_duplicate_results_or_session(tmp_path):
 db=Journal(tmp_path/'shadow.db');db.append(event());r=dict(model_id='rf',model_role='rf_session',session_id='s',score=.1,comparison=False,capture_timestamp=1,inference_finish=2,mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound');db.complete({'id':'e1'},[r]);db.complete({'id':'e1'},[r]);assert db.db.execute('select count(*) from results').fetchone()[0]==1;assert db.session_values()[0]['score']==.1;db.close()
def test_transport_sequence_gap_invalidates_context():
 f=Flows();f.accept(p(sequence=100));f.accept(p(time=2,sequence=101,flags=16,payload=b'abc'));v=f.accept(p(time=3,sequence=110,flags=16,payload=b'x'));assert v['status']=='INSUFFICIENT_CONTEXT' and v['diagnostic']=='tcp_sequence_gap';assert f.accept(p(time=4,sequence=111,flags=16))['status']=='INSUFFICIENT_CONTEXT'
def test_transport_retransmission_not_a_gap():
 f=Flows();f.accept(p(sequence=100));f.accept(p(time=2,sequence=101,flags=16,payload=b'abc'));v=f.accept(p(time=3,sequence=101,flags=16,payload=b'abc'));assert v['status']=='FEATURE_READY'
def test_sequence_wrap_supported_without_gap():
 f=Flows();f.accept(p(sequence=0xfffffffe));f.accept(p(time=2,sequence=0xffffffff,flags=16,payload=b'xx'));assert f.accept(p(time=3,sequence=1,flags=16))['status']=='FEATURE_READY'

def test_frozen_model_hash_version_threshold_before_deserialization(tmp_path,monkeypatch):
 import hashlib
 from src.shadow_ids import models
 from src.classifier.ml import artifacts
 directory=tmp_path/'model';directory.mkdir();(directory/'manifest.json').write_text('known source manifest')
 pin=dict(model_id='frozen',model_version='14.0.0',artifact_sha256='original',manifest_sha256=hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),threshold=.9)
 good=dict(task='network_ids',algorithm='rf_binary',artifact_sha256='original',threshold=.9,feature_version='tcp-packet-passive-v1',mode='RESEARCH',trusted_detector=False,preprocessing={'feature_order':list(FEATURES)})
 monkeypatch.setattr(models,'frozen',lambda:{'rf_binary':pin});called=[];monkeypatch.setattr(artifacts,'load',lambda *a:(called.append(True) or ({},None)))
 for change in [dict(artifact_sha256='changed'),dict(feature_version='network-core-v1'),dict(threshold=.8),dict(trusted_detector=True),dict(preprocessing={'feature_order':list(reversed(FEATURES))})]:
  monkeypatch.setattr(artifacts,'verify',lambda *a,c=change:({**good,**c},directory))
  with pytest.raises(ValueError):models.load_models(tmp_path,['rf_binary'])
 assert not called,'Unauthorized artifact reached pickle loader'
def test_nonfinite_score_is_error_without_plain_normal(tmp_path,monkeypatch):
 import src.classifier.research.experiment as ex
 from src.shadow_ids.models import scores
 monkeypatch.setattr(ex,'risk',lambda *a:__import__('numpy').array([float('nan')]))
 pin=dict();valid=dict(status='FEATURE_READY',feature_version='tcp-packet-passive-v1',features=dict(zip(FEATURES,[54,0,2,74,0])))
 with pytest.raises(ValueError,match='Invalid inference'):scores({'rf_binary':(pin,None)},[valid])
def test_no_fit_or_old_holdout_during_shadow_model_scoring(monkeypatch):
 from src.shadow_ids.models import scores
 import src.classifier.research.experiment as ex
 def forbidden(*a,**k):raise AssertionError('Old holdout/fit was opened')
 monkeypatch.setattr(ex,'train',forbidden);monkeypatch.setattr(ex,'final_test',forbidden);monkeypatch.setattr(ex,'plan',forbidden)
 monkeypatch.setattr(ex,'risk',lambda *a:__import__('numpy').array([.5]))
 e=dict(status='FEATURE_READY',feature_version='tcp-packet-passive-v1',features=dict(zip(FEATURES,[54,0,2,74,0])));assert scores({'rf_binary':({},None)},[e])['rf_binary']==[.5]
def test_malformed_queued_event_is_diagnostic_not_poison_queue(tmp_path):
 from src.shadow_ids.worker import process
 db=Journal(tmp_path/'shadow.db');db.append(event());db.db.execute("UPDATE events SET packet='[]'");db.db.commit();process(db,{},db.pending());assert not db.pending();rows=[json.loads(r[0]) for r in db.db.execute('select value from results')];assert rows and all(r['score'] is None and r['inference_status']=='MALFORMED_EVENT' for r in rows);db.close()
def test_capture_loss_invalidates_already_queued_context(tmp_path):
 from src.shadow_ids.worker import process
 db=Journal(tmp_path/'shadow.db');e={**event(),'status':'FEATURE_READY','capture_timestamp':1,'feature_ready_at':2,'observer_id':'x','feature_version':'tcp-packet-passive-v1','features':dict(zip(FEATURES,[54,0,2,74,0]))};db.append(e);db.status('capture',dict(status='CAPTURE_INCOMPLETE',queue_overflow=1));process(db,{},db.pending());rows=[json.loads(r[0]) for r in db.db.execute('select value from results')];assert all(r['inference_status']=='CAPTURE_DROPPED' and r['score'] is None for r in rows);db.close()
