"""Real additive validator upgrade, restricted to an isolated stage8 collection.
Stops only its relay, never deletes collections, rows, indexes or volumes.
"""
import argparse,json,subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--env-file',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    env=dict(l.split('=',1) for l in a.env_file.read_text().splitlines() if '=' in l and not l.startswith('#'))
    if not env.get('COMPOSE_PROJECT_NAME','').startswith('lcm-stage8-'):p.error('Dedicated stage8 project required')
    if a.output.exists():p.error('Immutable output path already exists')
    base=['docker','compose','--env-file',str(a.env_file),'-f','compose.yaml','-f','compose.control.yaml']
    def run(*args):return subprocess.run(base+list(args),check=True,capture_output=True,text=True,timeout=60).stdout
    auth="const fs=require('fs');if(!db.getSiblingDB('admin').auth('root',fs.readFileSync('/run/mongo/root.password','utf8').trim()))throw Error('Authentication');const t=db.getSiblingDB('telemetry');"
    read="print(JSON.stringify({count:t.measurements.countDocuments({}),indexes:t.measurements.getIndexes(),validator:t.getCollectionInfos({name:'measurements'})[0].options.validator}));"
    def query(code):return run('exec','-T','mongo','mongosh','--quiet','--eval',auth+code)
    run('stop','outbox-relay');before=None
    try:
        before=json.loads(query(read));assert before['count']>0
        assert before['validator']['$jsonSchema']['properties']['crypto_profile']['enum']==['Ascon-AEAD128','AES-128-GCM']
        query("const v=t.getCollectionInfos({name:'measurements'})[0].options.validator;v.$jsonSchema.properties.crypto_profile.enum=['Ascon-AEAD128'];if(!t.runCommand({collMod:'measurements',validator:v}).ok)throw Error('Legacy validator');")
        assert json.loads(query(read))['validator']['$jsonSchema']['properties']['crypto_profile']['enum']==['Ascon-AEAD128']
        for _ in range(2):run('exec','-T','mongo','mongosh','--quiet','--file','/upgrade_profiles.js')
        after=json.loads(query(read));assert after==before
        result=dict(project=env['COMPOSE_PROJECT_NAME'],existing_documents=before['count'],documents_after=after['count'],indexes_unchanged=True,validator_restored=True,upgrade_repeated=2,rows_deleted=0,volumes_deleted=0)
        a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    finally:
        if before:
            query('if(!t.runCommand({collMod:"measurements",validator:'+json.dumps(before['validator'])+'}).ok)throw Error("Restore validator");')
        run('up','-d','--no-deps','--wait','outbox-relay')

if __name__=='__main__':main()
