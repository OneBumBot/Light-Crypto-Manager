"""Compare live journal to independent historical PCAP parser, no model inference."""
import csv,json,hashlib
from pathlib import Path
from src.research_stand.pcap_audit import packets
from .journal import Journal
from .features import VERSION
TOLERANCE=1.1e-6

def compare(root):
 root=Path(root);db=Journal(root/'shadow.db',readonly=True);rows=[json.loads(r[0]) for r in db.db.execute('SELECT packet FROM events ORDER BY ordinal')];reference=list(packets(root/'traffic.pcap'));last={};integers=0;deltas=0;matched=0;unavailable=0
 if len(rows)!=len(reference):raise ValueError('Physical packet/journal count mismatch')
 for event,ref in zip(rows,reference):
  key=tuple(sorted((ref['wire'][:2],ref['wire'][2:])));delta=ref['time']-last.get(key,ref['time']);last[key]=ref['time']
  if event['ordinal']!=ref['number'] or abs(event['capture_timestamp']-ref['time'])>TOLERANCE:raise ValueError('Packet identity/timestamp mismatch')
  if event['status']!='FEATURE_READY':unavailable+=1;continue
  f=event['features'];integers+=sum(f[k]!=v for k,v in [('frame.len',ref['length']),('tcp.len',ref['payload_length']),('tcp.flags',ref['flags']),('tcp.window_size_value',ref['window'])]);deltas+=int(abs(f['tcp.time_delta']-delta)>TOLERANCE);matched+=1
 tshark_mismatches=0
 if (root/'headers.csv').exists():
  with (root/'headers.csv').open() as stream:export=list(csv.DictReader(stream))
  if len(export)!=len(reference):raise ValueError('Independent tshark packet count')
  for event,row in zip(rows,export):
   if event['status']!='FEATURE_READY':continue
   for key in ['frame.len','tcp.len','tcp.flags','tcp.window_size_value','tcp.time_delta']:
    v=int(row[key],0) if key=='tcp.flags' else float(row[key]);f=event['features'][key]
    tshark_mismatches+=int(abs(f-v)>(TOLERANCE if key=='tcp.time_delta' else 0))
 else:raise ValueError('Independent tshark source required')
 state=json.loads((root/'capture-status.json').read_text());db.close()
 return dict(status='PASS' if matched>=100 and not integers and not deltas and not tshark_mismatches and state['complete'] else 'BLOCKED',feature_version=VERSION,parser_sha256=hashlib.sha256(Path(__file__).with_name('features.py').read_bytes()).hexdigest(),supported_packets=matched,physical_packets=len(reference),unavailable_packets=unavailable,integral_mismatches=integers,delta_mismatches=deltas,tshark_mismatches=tshark_mismatches,tolerance_seconds=TOLERANCE,pcap_sha256=state['pcap_sha256'],capture_complete=state['complete'],reference='Unchanged Stage14 pcap_audit.packets; bidirectional tuple delta; fresh generation scope',scope='Engineering feature parity, not model quality')
