"""Three bounded real static-profile windows through MQTT/TLS and durable stores."""
import argparse,json,time,subprocess
from pathlib import Path
from scripts.kuz_lab import Lab
from scripts.performance_run import login,resources
from scripts.performance_reliability import switch
from scripts.benchmark_switching import SAMPLE
from src.crypto_profiles import ASCON,AES,KUZ,PROFILES


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    lab=Lab(a.directory);session,url,token=login(lab);rows=[];transitions=[]
    for profile in [ASCON,AES,KUZ]:
        current=session.get(url+'/api/monitoring/alpha',timeout=8).json()['items'][0]['effective_profile']
        if current!=profile:transitions.append(switch(lab,session,url,token,'alpha',profile))
        time.sleep(1)
        r=lab.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-c',SAMPLE)
        data=json.loads(r.stdout)
        assert data['wire_profile']==PROFILES[profile]['algorithm'] and data['pg_accepted']==data['mongo_stored'] and data['pg_accepted']>0
        rows.append(dict(profile=profile,**data,resources=resources(lab)))
    transitions.append(switch(lab,session,url,token,'alpha',ASCON))
    a.output.write_text(json.dumps(dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),windows=rows,transitions=transitions,
        limitations=['Single 8-second window per profile, not independent replicated network benchmark','Within-window p95/p99 descriptive only, sample too small for tail inference','Same-host wall clock; received timestamp precedes SQL commit; no isolated network/PG commit latency claim','docker stats snapshots, not peak CPU/RAM'],commands=lab.commands,exit_code=0),indent=2))
    print('Three real static AEAD windows and transitions: exit 0')

if __name__=='__main__':main()
