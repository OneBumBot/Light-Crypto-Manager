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
