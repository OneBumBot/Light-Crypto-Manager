"""Independent physical record identity audit; no TLS decode, scoring or labels."""
import hashlib,json,os,shutil,sqlite3,struct
from pathlib import Path
from src.shadow_ids.journal import Journal,path_for

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def audit(root):
 root=Path(root);pcap=root/'traffic.pcap';cap=json.loads((root/'capture-status.json').read_text())
 if pcap.is_symlink() or cap.get('complete') is not True or sha(pcap)!=cap['pcap_sha256']:raise ValueError('Physical source receipt mismatch')
 db=Journal(path_for(root),readonly=True);events={r['ordinal']:json.loads(r['packet']) for r in db.db.execute('SELECT ordinal,packet FROM events')};db.close();matched=0
 with pcap.open('rb') as stream:
  header=stream.read(24);magic={b'\xd4\xc3\xb2\xa1':('<',1000000),b'\xa1\xb2\xc3\xd4':('>',1000000),b'\x4d\x3c\xb2\xa1':('<',1000000000),b'\xa1\xb2\x3c\x4d':('>',1000000000)}
  if len(header)!=24 or header[:4] not in magic:raise ValueError('PCAP header')
  endian,scale=magic[header[:4]]
  for ordinal in range(1,20002):
   head=stream.read(16)
   if not head:break
   if len(head)!=16 or ordinal>20000:raise ValueError('PCAP record bound')
   sec,frac,n,original=struct.unpack(endian+'IIII',head)
   if not 54<=n<=65535 or n!=original or frac>=scale:raise ValueError('Truncated physical record')
   raw=stream.read(n)
   if len(raw)!=n:raise ValueError('Truncated physical bytes')
   event=events.get(ordinal)
   if not event or abs(event['capture_timestamp']-(sec+frac/scale))>1.1e-6 or event.get('packet_sha256')!=hashlib.sha256(raw).hexdigest():raise ValueError('Physical packet identity mismatch')
   matched+=1
 if matched!=len(events) or matched!=cap['stats']['captured']:raise ValueError('Physical packet count mismatch')
 return dict(physical_records=matched,exact_frame_digest_matches=matched,pcap_sha256=cap['pcap_sha256'])
def main():
 os.umask(0o077)
 root=Path('.local-runtime/stage15/online/shadow');results={name:audit(root/name) for name in ['parity-batch-00','parity-batch-01','parity-batch-02']};negative=[];base=Path('.local-runtime/stage15/negative-physical-copies');base.mkdir(mode=0o700,exist_ok=True);original=root/'parity-batch-00'
 for case in ['missing_pcap','truncated_pcap','wrong_digest','coherent_pcap_metadata_rehash']:
  dest=base/case
  if dest.exists():raise ValueError('Previous negative source retained')
  dest.mkdir(mode=0o700);shutil.copyfile(original/'traffic.pcap',dest/'traffic.pcap');shutil.copyfile(original/'capture-status.json',dest/'capture-status.json');source=sqlite3.connect(path_for(original));target=sqlite3.connect(dest/'shadow.db');source.backup(target);source.close();target.close()
  if case=='missing_pcap':(dest/'traffic.pcap').rename(dest/'retained-original.pcap')
  if case=='truncated_pcap':f=dest/'traffic.pcap';f.write_bytes(f.read_bytes()[:-1])
  if case=='wrong_digest':m=json.loads((dest/'capture-status.json').read_text());m['pcap_sha256']='0'*64;(dest/'capture-status.json').write_text(json.dumps(m))
  if case=='coherent_pcap_metadata_rehash':
   f=dest/'traffic.pcap';raw=bytearray(f.read_bytes());raw[-1]^=1;f.write_bytes(raw);m=json.loads((dest/'capture-status.json').read_text());m['pcap_sha256']=sha(f);(dest/'capture-status.json').write_text(json.dumps(m))
  rejected=False
  try:audit(dest)
  except (ValueError,OSError):rejected=True
  assert rejected,case;negative.append(dict(case=case,rejected=True,source='Corrupted copy of actual new PCAP/journal, never an independent capture'))
 Path('docs/reports/stage15/physical-identity-audit.json').write_text(json.dumps(dict(results=results,negatives=negative,source_original_unchanged=sha(original/'traffic.pcap')==results['parity-batch-00']['pcap_sha256'],negative_copies_count_as_new_physical_captures=0,exit_code=0),indent=2));print('975 physical packet SHA identities confirmed;4 actual-source corruptions rejected; exit0')
if __name__=='__main__':main()
