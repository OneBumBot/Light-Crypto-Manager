"""Predeclared3-device1Hz static network matrix and real manual switching."""
import argparse,json,time,subprocess
from pathlib import Path
from datetime import datetime,timezone
from scripts.crypto_research_lab import Lab
from scripts.performance_run import login,resources
from scripts.performance_reliability import switch
from src.crypto_profiles import ASCON,AES,KUZ,PROFILES


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable report')
    lab=Lab(a.directory);session,url,token=login(lab);windows=[];transitions=[]
    def current():return session.get(url+'/api/monitoring/alpha',timeout=8).json()['items'][0]['effective_profile']
    def read_journal(device,start,end):
        code="import json;from pathlib import Path;r=[json.loads(l) for l in Path('/device/research-events.jsonl').read_text().splitlines()];print(json.dumps([v for v in r if "+str(start)+"<=v['wall_ns']<"+str(end)+"]))"
        return json.loads(lab.run('exec','-T','device-'+device,'python','-c',code).stdout)
    for profile,backend in [(ASCON,'persistent'),(KUZ,'persistent'),(AES,'persistent'),(ASCON,'persistent'),(KUZ,'one-shot')]:
        if current()!=profile:transitions.append(switch(lab,session,url,token,'alpha',profile))
        if backend=='one-shot':
            override=lab.root/'one-shot.compose.json';override.write_text(json.dumps(dict(services={s:dict(environment=dict(LCM_KUZ_BACKEND='one-shot')) for s in ['receiver','device-alpha']})));override.chmod(0o600)
            lab.base+=['-f',str(override)];lab.run('up','-d','--no-deps','--wait','receiver','device-alpha')
            # Published port may stay unchanged; admin requests resume after window with original base.
        time.sleep(3);before=lab.probe('snapshot');start=time.time_ns();deadline=time.monotonic()+20;time.sleep(9);resource_snapshot=resources(lab);time.sleep(max(0,deadline-time.monotonic()));end=time.time_ns()
        journals={d:read_journal(d,start,end) for d in lab.devices};formed=[r for rows in journals.values() for r in rows if r['kind']=='formed'];assert formed
        end_wait=time.monotonic()+20
        while True:
            r=lab.run('run','--rm','-T','--no-deps','-v',str(Path('scripts/stage12_probe.py').resolve())+':/app/scripts/stage12_probe.py:ro','--entrypoint','python','tests','-m','scripts.stage12_probe',input_data=json.dumps(formed))
            reconciled=json.loads(r.stdout)
            if reconciled['pg_unique']==len(formed)==reconciled['mongo_stored']:break
            if time.monotonic()>end_wait:raise AssertionError('Source cohort not reconciled')
            time.sleep(.25)
        target=[v for v in reconciled['rows'] if v['device']=='alpha'];assert target and all(v['profile']==PROFILES[profile]['algorithm'] for v in target)
        assert all(v['profile']=='Ascon-AEAD128' for v in reconciled['rows'] if v['device']!='alpha')
        published=[v for rs in journals.values() for v in rs if v['kind']=='publish'];mids={(v['boot'],v['mid']) for v in published}
        ack=[v for rs in journals.values() for v in rs if v['kind']=='puback' and (v['boot'],v['mid']) in mids and v['success']]
        windows.append(dict(before=before,after=lab.probe('snapshot'),profile=profile,backend=backend,device_count=3,target='alpha',background_profiles='beta/gamma Ascon',configured_hz=1,start_ns=start,end_ns=end,scheduled=sum(v.get('count',0) for rs in journals.values() for v in rs if v['kind']=='scheduled'),formed=len(formed),publish_calls=len(published),queued=sum(v['queued'] for v in published),broker_puback=len(ack),reconciliation=reconciled,resources=resource_snapshot))
        a.output.with_suffix('.progress.json').write_text(json.dumps(dict(windows=windows,transitions=transitions),indent=2))
    if current()!=ASCON:transitions.append(switch(lab,session,url,token,'alpha',ASCON))
    # Restore optimized configuration explicitly; no cryptographic profile fallback.
    lab.base=[v for v in lab.base if v!=str(lab.root/'one-shot.compose.json')]
    if lab.base[-1]=='-f':lab.base.pop()
    lab.run('up','-d','--no-deps','--wait','receiver','device-alpha')
    report=dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),windows=windows,transitions=transitions,commands=lab.commands,policy='DRY_RUN',trusted_detector=False,exit_code=0)
    a.output.write_text(json.dumps(report,indent=2));print('Real Stage12 network matrix, source reconciliation and HTTP switching: exit0')

if __name__=='__main__':main()
