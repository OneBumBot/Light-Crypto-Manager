"""Bounded keyless tcpdump stream. Only NET_RAW, no MQTT client, TLS decoding or key files."""
import argparse,hashlib,json,os,queue,re,resource,shutil,signal,socket,subprocess,threading,time,uuid
from pathlib import Path
from .features import Flows,Unavailable,packet,VERSION
from .pcap import header,record
from .journal import Journal

def run(root,duration,broker,capacity=512,max_packets=20000,extract_only=False):
 if not 3<=duration<=60 or not 1<=capacity<=512 or not 1<=max_packets<=20000:raise ValueError('Capture bounds')
 os.umask(0o077);root=Path(root);root.mkdir(mode=0o700,parents=True,exist_ok=True)
 if (root/'traffic.pcap').exists():raise ValueError('Existing capture preserved')
 if shutil.disk_usage(root).free<1024**3:raise ValueError('Disk floor')
 run_id=root.name+'-'+uuid.uuid4().hex;db=Journal(root/'shadow.db');flows=Flows();stop=threading.Event();incoming=queue.Queue(maxsize=capacity);reader_loss=[0];errors=[];ready=threading.Event();stats={'captured':0,'received_by_filter':None,'dropped_by_kernel':None};started=time.time();ordinal=0;overflows=0;unsupported=0;last_packet=None;reason='duration';cap=Path(root/'traffic.pcap').open('xb')
 command=['tcpdump','-p','-i','eth0','-U','-s','0','-B','4096','-c',str(max_packets),'-w','-','tcp and host '+broker+' and port 8883'];process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def reader():
  try:
   raw,endian,scale,snap=header(process.stdout);cap.write(raw);cap.flush();ready.set()
   while True:
    item=record(process.stdout,endian,scale,snap)
    if item is None:break
    head,raw,original,t=item;cap.write(head+raw);cap.flush()
    try:incoming.put_nowait((raw,original,t))
    except queue.Full:reader_loss[0]+=1
  except Exception as exc:errors.append(type(exc).__name__)
 def shutdown(*_):stop.set()
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,shutdown)
 thread=threading.Thread(target=reader,daemon=True);thread.start();deadline=time.monotonic()+duration;last_loss=0;sent_signal=False
 try:
  while True:
   if stop.is_set() or time.monotonic()>deadline or (root/'stop').exists():
    if not sent_signal:
     if process.poll() is None:process.send_signal(signal.SIGINT)
     sent_signal=True
   if not sent_signal and (root/'traffic.pcap').stat().st_size>32*1024**2:reason='size_limit';stop.set()
   if not sent_signal and shutil.disk_usage(root).free<512*1024**2:reason='disk_limit';stop.set()
   if process.poll() is not None and not thread.is_alive() and incoming.empty():break
   if reader_loss[0]!=last_loss:flows.gap();last_loss=reader_loss[0]
   try:raw,original,t=incoming.get(timeout=.05)
   except queue.Empty:
    if errors:reason='reader_error';stop.set()
    db.status('capture',dict(status='CAPTURING' if ready.is_set() else 'STARTING',heartbeat=time.time(),capture_id=run_id,started_at=started,last_packet=last_packet,reader_drops=reader_loss[0],queue_overflow=overflows,unsupported=unsupported));continue
   ordinal+=1;last_packet=t
   try:p=packet(raw,original,t);value=flows.accept(p);event={**value,'packet_sha256':p['raw_sha256'],'capture_timestamp':t}
   except Unavailable as exc:
    flows.gap();unsupported+=1;event=dict(status='FEATURE_UNAVAILABLE',diagnostic=str(exc),capture_timestamp=t)
   event.update(event_id=hashlib.sha256((run_id+':'+str(ordinal)).encode()).hexdigest(),ordinal=ordinal,capture_id=run_id,observer_id='stage15-keyless-observer',feature_version=VERSION,feature_ready_at=time.time(),mode='SHADOW_ONLY',trusted_detector=False,device_binding='unbound',context_dropped=bool(last_loss or overflows))
   try:
    db.append(event,capacity=capacity)
    if extract_only:db.complete({'id':event['event_id']},[])
   except (OverflowError,__import__('sqlite3').OperationalError):overflows+=1;flows.gap()
   if ordinal%20==0:db.status('capture',dict(status='CAPTURING',heartbeat=time.time(),capture_id=run_id,started_at=started,last_packet=last_packet,packets=ordinal,reader_drops=reader_loss[0],queue_overflow=overflows,unsupported=unsupported))
  thread.join(2)
 finally:
  if process.poll() is None:process.send_signal(signal.SIGINT)
  process.wait(timeout=5);thread.join(2);cap.close()
 output=process.stderr.read().decode(errors='replace')
 for label,key in [('packets captured','captured'),('packets received by filter','received_by_filter'),('packets dropped by kernel','dropped_by_kernel')]:
  found=re.search(r'(\d+) '+label,output);stats[key]=int(found.group(1)) if found else None
 complete=process.returncode==0 and reason=='duration' and not errors and not reader_loss[0] and not overflows and stats['dropped_by_kernel']==0
 state=dict(status='FINISHED' if complete else 'CAPTURE_INCOMPLETE',complete=complete,heartbeat=time.time(),capture_id=run_id,started_at=started,finished_at=time.time(),last_packet=last_packet,packets=ordinal,reader_drops=reader_loss[0],queue_overflow=overflows,unsupported=unsupported,stats=stats,reason=reason,errors=errors,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,user_cpu=resource.getrusage(resource.RUSAGE_SELF).ru_utime,capture_point='lab-devices eth0, Ethernet/IPv4/TCP; TLS opaque',interface='eth0',linktype=1,ip_versions=['IPv4'],namespace=os.readlink('/proc/self/ns/net'),snaplen=262144,offloads='not_changed; environment-specific, parity checked on actual frames',timestamp_source='kernel libpcap CLOCK_REALTIME shared-host',pcap_sha256=hashlib.sha256((root/'traffic.pcap').read_bytes()).hexdigest())
 db.status('capture',state);(root/'capture-status.json').write_text(json.dumps(state,indent=2));db.close();return state

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--duration',type=float,default=25);p.add_argument('--capacity',type=int,default=512);p.add_argument('--extract-only',action='store_true');a=p.parse_args();run(a.root,a.duration,socket.gethostbyname('broker'),a.capacity,extract_only=a.extract_only)
if __name__=='__main__':main()
