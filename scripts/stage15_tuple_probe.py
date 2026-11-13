"""Internal fresh-lab tuple reuse probe, real MQTT/TLS + independent AEAD sequences."""
import json,socket,struct,time
from pathlib import Path
from datetime import datetime,timezone
import paho.mqtt.client as mqtt
from src.mqtt_transport import configure_client
from src.sequence import next_sequence
from src.telemetry import load_registry,encode_packet

def main():
 folder=next(p for p in sorted(Path('/run/research').iterdir()) if p.is_dir() and p.name.startswith('lab'));identity=folder.name;registry=load_registry(folder/'registry.json');record=[];probe=socket.socket();probe.bind(('',0));port=probe.getsockname()[1];probe.close()
 for n in range(2):
  c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='stage15-reused-'+str(n));ready=[];c.on_connect=lambda client,u,f,reason,props:ready.append(reason==0);configure_client(c,username='device_'+identity,password_file=str(folder/'mqtt.password'),ca_file=str(folder/'ca.crt'));c.connect('broker',8883,30,bind_port=port);end=time.monotonic()+3
  while not ready and time.monotonic()<end:c.loop(timeout=.02)
  if ready!=[True]:raise RuntimeError('Tuple TLS authentication unavailable')
  seq=next_sequence('/state/sequence.db',identity,registry[identity]['key_epoch']);payload=encode_packet(dict(temperature=22.0,humidity=45.0,timestamp=datetime.now(timezone.utc).isoformat()),registry,identity,seq);info=c.publish(registry[identity]['topic'],json.dumps(payload),qos=1);end=time.monotonic()+3
  while not info.is_published() and time.monotonic()<end:c.loop(timeout=.02)
  record.append(dict(local_port=c.socket().getsockname()[1],remote_port=c.socket().getpeername()[1],mqtt_puback=info.is_published(),sequence_number=seq))
  c.socket().setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));c.socket().close();time.sleep(.2)
 print(json.dumps(dict(connections=record,tuple_reuse=record[0]['local_port']==record[1]['local_port'],source='Fresh Stage15 internal broker only',exit_code=0)))
if __name__=='__main__':main()
