"""Prove stop/start resumes authority and never reuses a boot nonce range."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
from scripts.stage9_common import Demo


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Immutable output exists')
    d=Demo(a.directory)
    def private_hashes():
        paths=[d.root/'control.json',d.root/'compose.env',d.root/'mqtt/registry.json',*list((d.root/'accounts').glob('*.password'))]
        return {str(p):hashlib.sha256(p.read_bytes()).digest() for p in paths}
    before=d.probe('ready');keys=private_hashes()
    assert before['unknown']==0 and before['transitions']==before['completed']
    commands=[]
    for action in ['stop','start']:
        command=[sys.executable,'-m','scripts.run_stage9_demo','--directory',str(d.root),action]
        r=subprocess.run(command,capture_output=True,text=True,timeout=250)
        commands.append(dict(command=command,exit_code=r.returncode))
        if r.returncode:raise RuntimeError('Resume '+action+' failed: '+r.stderr[-1000:])
    after=d.probe('ready')
    assert private_hashes()==keys
    old={x['device_id']:x for x in before['devices']}
    for row in after['devices']:
        prior=old[row['device_id']]
        assert row['sequence_reserved']>prior['sequence_reserved']
        assert row['command_sequence']==prior['command_sequence']
        assert row['effective_profile']==prior['effective_profile'] and row['effective_event']==prior['effective_event']
    assert before['transitions']==after['transitions'] and before['authenticated_ack']==after['authenticated_ack']
    assert sum(x['accepted'] for x in after['telemetry'].values())>=sum(x['accepted'] for x in before['telemetry'].values())
    report=dict(project=d.project,source_commit=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
        before=before,after=after,private_material_unchanged=True,commands=commands+d.commands,all_new_boot_ranges=True,exit_code=0)
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(all_new_boot_ranges=True,private_material_unchanged=True,exit_code=0)))

if __name__=='__main__':main()
