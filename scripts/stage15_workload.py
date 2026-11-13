"""Stage15-only bounded extension of existing TLS/AEAD generator; no old limits changed."""
import argparse,json,threading,time
from pathlib import Path
from src.research_stand.config import Experiment
from src.research_stand.driver import run
class Workload(Experiment):
 def validate(self):
  # Reuse every established scenario/type/duration/rate check on a <=24 proxy,
  # then separately enforce Stage15 concurrent identities and aggregate resource bound.
  Experiment(**{**self.__dict__,'clients':min(self.clients,24)}).validate()
  if type(self.clients) is not int or not 2<=self.clients<=50 or self.clients/self.interval>120:raise ValueError('Stage15 bounded50 clients/120messages per second')
  return self
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args();cfg=Workload(**json.loads(Path(a.config).read_text()));counters=dict(formed_aead_packets=0,publish_calls=0,queued=0,puback=0,scheduled_publications='not_measured_event_driven_loop');lock=threading.Lock();infos=[]
 import src.research_stand.driver as driver
 original_encode=driver.encode_packet;original_publish=driver.mqtt.Client.publish
 def encoded(*args,**kwargs):
  value=original_encode(*args,**kwargs)
  with lock:counters['formed_aead_packets']+=1
  return value
 def published(self,*args,**kwargs):
  with lock:counters['publish_calls']+=1
  info=original_publish(self,*args,**kwargs)
  with lock:counters['queued']+=int(info.rc==0);infos.append(info)
  return info
 driver.encode_packet=encoded;driver.mqtt.Client.publish=published
 result=run(cfg,'/research');counters['puback']=sum(int(info.is_published()) for info in infos);counters.update(device_identities=len(result['devices']),units='AEAD formations/publish invocations/client queues/broker PUBACK; not durable admissions',actual_duration=result['experiment_finished_at']-result['experiment_started_at']);Path('/research',cfg.experiment_id,'stage15-counters.json').write_text(json.dumps(counters,indent=2))
