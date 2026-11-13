"""Actual Stage13 HTTP/MQTT/TLS/Chromium regressions after the Policy-only fault phase."""
import argparse,json,subprocess,sys,time
from pathlib import Path
from scripts.policy13_crypto_lab import Lab
from scripts.performance_run import login
from scripts.performance_reliability import switch
from src.crypto_profiles import ASCON,KUZ


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--reports',type=Path,required=True);a=p.parse_args();lab=Lab(a.directory);records=[]
    def harness(module,name,binding='Lab'):
        output=a.reports/(name+'.json')
        if output.exists():raise ValueError('Immutable report exists')
        code='from scripts.policy13_crypto_lab import Lab;from scripts import '+module+' as m;m.'+binding+'=Lab;m.main()'
        started=time.monotonic();r=subprocess.run([sys.executable,'-c',code,'--directory',str(lab.root),'--output',str(output)],capture_output=True,text=True,timeout=600)
        (a.reports/(name+'.txt')).write_text(r.stdout+r.stderr);records.append(dict(module=module,exit_code=r.returncode,seconds=time.monotonic()-started))
        if r.returncode:raise RuntimeError(module+' failed; see bounded report')
    try:
        harness('check_stage9_browser','crypto-browser','ResearchLab')
        harness('check_kuz_control_browser','control-browser')
        harness('check_kuz_lostack','lost-ack')
        harness('check_kuz_reliability','crypto-service-recovery')
        s,url,token=login(lab);switch(lab,s,url,token,'alpha',KUZ)
        output=a.reports/'poison.json'
        r=subprocess.run([sys.executable,'-m','scripts.check_malformed_mqtt_recovery','--env-file',str(lab.root/'compose.env'),'--profile',KUZ,'--output',str(output)],capture_output=True,text=True,timeout=180)
        (a.reports/'poison.txt').write_text(r.stdout+r.stderr);records.append(dict(module='check_malformed_mqtt_recovery',exit_code=r.returncode));assert r.returncode==0
        s,url,token=login(lab);switch(lab,s,url,token,'alpha',ASCON)
        r=lab.run('run','--rm','-T','--no-deps','--entrypoint','python','tests','-m','scripts.control_security_probe',timeout=150,check=False)
        (a.reports/'control-negatives.txt').write_text(r.stdout+r.stderr);assert r.returncode==0
        lab.run('stop',*lab.agents());end=time.monotonic()+90
        while time.monotonic()<end:
            snapshot=lab.probe('snapshot')
            pending=lab.run('run','--rm','-T','--no-deps','-v',str(Path('scripts/policy13_probe.py').resolve())+':/app/scripts/policy13_probe.py:ro','--entrypoint','python','tests','-m','scripts.policy13_probe','snapshot')
            policy=json.loads(pending.stdout)
            if not policy['security']['pending'] and not sum(v for k,v in snapshot['outbox'].items() if k!='delivered'):break
            time.sleep(1)
        else:raise AssertionError('Final durable queues did not drain')
        data=dict(project=lab.project,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cryptographic=snapshot,policy=policy,harnesses=records,commands=lab.commands,exit_code=0)
        assert snapshot['counters'].get('accepted')==snapshot['mongo_managed'] and snapshot['policy_applied']==0 and not snapshot['unknown']
        (a.reports/'crypto-final.json').write_text(json.dumps(data,indent=2))
    finally:
        lab.run('stop')
    print('Real crypto/browser/control/poison/service recovery complete; lab stopped, state retained')
if __name__=='__main__':main()
