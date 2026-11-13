"""Independent bounded Ethernet/IPv4/TCP streaming parser; never decodes TLS."""
import hashlib,ipaddress,math,struct
from collections import OrderedDict
FEATURES=('frame.len','tcp.len','tcp.flags','tcp.window_size_value','tcp.time_delta')
VERSION='tcp-packet-passive-v1'
class Unavailable(ValueError):pass

def packet(raw,original,timestamp):
 if type(timestamp) not in (int,float) or not math.isfinite(timestamp) or timestamp<0:raise Unavailable('timestamp')
 if type(raw) is not bytes or type(original) is not int or len(raw)!=original or not 54<=original<=65535:raise Unavailable('truncated_frame')
 if raw[12:14]!=b'\x08\x00':raise Unavailable('unsupported_ethernet_protocol')
 ip=raw[14:];ihl=(ip[0]&15)*4
 if ip[0]>>4!=4 or ihl<20 or len(ip)<ihl+20 or ip[9]!=6 or int.from_bytes(ip[6:8],'big')&0x3fff:raise Unavailable('unsupported_ip_or_fragment')
 n=int.from_bytes(ip[2:4],'big');tcp=ip[ihl:];offset=(tcp[12]>>4)*4;flags=((tcp[12]&15)<<8)|tcp[13]
 if offset<20 or n>len(ip) or n<ihl+offset or flags>511:raise Unavailable('invalid_tcp_header')
 a=(str(ipaddress.IPv4Address(ip[12:16])),int.from_bytes(tcp[:2],'big'));b=(str(ipaddress.IPv4Address(ip[16:20])),int.from_bytes(tcp[2:4],'big'))
 return dict(time=float(timestamp),wire=(a,b),key=tuple(sorted((a,b))),sequence=int.from_bytes(tcp[4:8],'big'),flags=flags,length=original,payload_length=n-ihl-offset,window=int.from_bytes(tcp[14:16],'big'),raw_sha256=hashlib.sha256(raw).hexdigest())

class Flows:
 def __init__(self,limit=1024,expiry=60):
  if not 1<=limit<=4096 or not 1<=expiry<=300:raise ValueError('Flow bound')
  self.limit=limit;self.expiry=expiry;self.rows=OrderedDict();self.generation=0
 def gap(self):
  for r in self.rows.values():r['complete']=False
 def accept(self,p):
  t=p['time'];key=p['key'];syn=bool(p['flags']&2 and not p['flags']&16);old=self.rows.get(key)
  regressed=old is not None and t<old['last']
  new=not regressed and (old is None or t-old['last']>self.expiry or (syn and (old['closed'] or old['initial']!=p['sequence'])))
  if new:
   self.generation+=1;r=dict(last=t,initial=p['sequence'] if syn else None,complete=syn,diagnostic=None if syn else 'missing_syn',closed=False,generation=self.generation,expected={});self.rows[key]=r;delta=0.0
   if len(self.rows)>self.limit:self.rows.popitem(last=False)
  else:
   r=old;delta=t-r['last']
   if delta<0:r['complete']=False;r['diagnostic']='timestamp_regression'
   r['last']=t;self.rows.move_to_end(key)
  sender=p['wire'][0];expected=r['expected'].get(sender);consumed=p['payload_length']+int(bool(p['flags']&2))+int(bool(p['flags']&1));end=(p['sequence']+consumed)&0xffffffff
  if expected is None:
   if not p['flags']&2:r['complete']=False
   r['expected'][sender]=end
  else:
   distance=(p['sequence']-expected)&0xffffffff
   if 0<distance<2**31:r['complete']=False;r['diagnostic']='tcp_sequence_gap'
   if distance<2**31:r['expected'][sender]=end
   elif (end-expected)&0xffffffff<2**31:r['expected'][sender]=end
  if p['flags']&5:r['closed']=True
  status='FEATURE_READY' if r['complete'] else 'INSUFFICIENT_CONTEXT'
  if delta<0 or delta>86400:status='FEATURE_UNAVAILABLE'
  return dict(status=status,diagnostic=r['diagnostic'],session=str(r['generation']),direction=0 if p['wire'][0]==key[0] else 1,closed=r['closed'],features=dict(zip(FEATURES,(p['length'],p['payload_length'],p['flags'],p['window'],delta))))
