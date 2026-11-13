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
