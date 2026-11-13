"""Read actual PG/Mongo identities and HMAC receipts. No generated telemetry/ACK."""
import hashlib
import json
from sqlalchemy import create_engine, select, func
from scripts.stage9_probe import status
from src.runtime import database_url
from src.outbox import outbox
from src.replay import replay_state
from src.device_control import models as m
from src.device_control.config import load
from src.device_control.protocol import seal, utc
from src.telemetry import canonical
from src.policy import models as policy
from src.mongo_repository import MongoRepository


def snapshot(engine):
    result = status(engine)
    config = load()
    with engine.connect() as c:
        rows = [dict(r) for r in c.execute(select(outbox).order_by(outbox.c.device_id, outbox.c.sequence_number).limit(10001)).mappings()]
        if len(rows) > 10000:
            raise ValueError('Demo evidence bound 10000 records reached; use another NEW project, never reset old state')
        identities = [dict(event_id=r['id'], device_id=r['device_id'], key_epoch=r['key_epoch'], sequence_number=r['sequence_number'],
                           crypto_profile=r['payload']['crypto_profile'], status=r['status']) for r in rows]
        result['identities'] = identities
        result['duplicate_identities'] = len(identities)-len({(r['device_id'],r['key_epoch'],r['sequence_number']) for r in identities})
        result['replay_state'] = [dict(r) for r in c.execute(select(replay_state)).mappings()]
        commands = {r['id']:dict(r) for r in c.execute(select(m.commands)).mappings()}
        transitions = [dict(r) for r in c.execute(select(m.transitions).order_by(m.transitions.c.created_at)).mappings()]
        receipts = {r['event_id']:dict(r) for r in c.execute(select(m.evidence)).mappings()}
        acks = []
        for row in c.execute(select(m.acks)).mappings():
            body = row['body'];cmd = commands[row['command_id']]
            wire = seal(body, bytes.fromhex(config[row['device_id']]['status_key']), 'device', now=utc(body['created_at']))
            verified = hashlib.sha256(wire).hexdigest() == row['sha256']
            binding = body['data']['command_sha256'] == hashlib.sha256(canonical(cmd['body'])).hexdigest()
            assert verified and binding
            acks.append(dict(id=row['id'],command_id=row['command_id'],transition_id=cmd['transition_id'],device_id=row['device_id'],phase=cmd['phase'],result=body['data']['result'],hmac_digest_matches=verified,command_digest_matches=binding))
        by_id = {r['id']:r for r in rows}
        verified_transitions=[]
        for row in transitions:
            evidence = receipts.get(row['telemetry_event'])
            packet = by_id.get(row['telemetry_event'])
            good = bool(evidence and packet and evidence['device_id']==row['device_id'] and evidence['profile']==row['target_profile']
                        and row['activated_at'] and evidence['accepted_at']>=row['activated_at'])
            if row['phase']=='EFFECTIVE_CONFIRMED':
                assert good and row['confirmed_at'] and row['confirmed_at']>=evidence['accepted_at']
            verified_transitions.append(dict(id=row['id'],device_id=row['device_id'],old_profile=row['old_profile'],target_profile=row['target_profile'],phase=row['phase'],actor=row['actor'],telemetry_event=row['telemetry_event'],activated_at=row['activated_at'],confirmed_at=row['confirmed_at'],receipt_matches_committed_admission=good,
                                             receipt=dict(event_id=evidence['event_id'],key_epoch=evidence['key_epoch'],sequence_number=evidence['sequence_number'],profile=evidence['profile'],accepted_at=evidence['accepted_at'],key_reference=evidence['key_reference']) if evidence else None))
        result['transition_evidence']=verified_transitions
        result['verified_acks']=acks
        result['command_phases']=[dict(id=r['id'],transition_id=r['transition_id'],device_id=r['device_id'],phase=r['phase'],status=r['status']) for r in commands.values()]
        result['nonce_ranges']=[dict(device_id=r['device_id'],boot_id=r['boot_id'],first=r['body']['data']['first_sequence'],last=r['body']['data']['last_sequence']) for r in c.execute(select(m.leases)).mappings()]
        for device in config:
            ranges=sorted((r['first'],r['last']) for r in result['nonce_ranges'] if r['device_id']==device)
            assert all(ranges[n][1]<ranges[n+1][0] for n in range(len(ranges)-1)), 'Nonce range reuse'
        result['policy']=dict(pending=c.scalar(select(func.count()).select_from(policy.pending)),signals=c.scalar(select(func.count()).select_from(policy.signals)),decisions=c.scalar(select(func.count()).select_from(policy.decisions)),active_versions=list(c.scalars(select(policy.versions.c.version).where(policy.versions.c.active.is_(True)))),workers=[dict(r) for r in c.execute(select(policy.worker_status.c.worker_id,policy.worker_status.c.status,policy.worker_status.c.mode,policy.worker_status.c.heartbeat_at)).mappings()])
    repo=MongoRepository('relay')
    try:
        docs=list(repo.collection.find({'device_id':{'$in':['alpha','beta','gamma']}},{'_id':1,'device_id':1,'key_epoch':1,'sequence_number':1,'crypto_profile':1}).limit(10001))
        result['mongo_identities']=docs
        expected={f"{r['device_id']}:{r['key_epoch']}:{r['sequence_number']}":r for r in identities}
        result['pg_identities_missing_in_mongo']=[key for key in expected if key not in {d['_id'] for d in docs}]
        for doc in docs:
            if doc['_id'] in expected:assert doc['crypto_profile']==expected[doc['_id']]['crypto_profile']
    finally:
        repo.close()
    result['mode']='MANUAL_AUTHORIZED_CONTROL'
    result['shadow']='OPTIONAL_RESEARCH_DEMO_UNAVAILABLE'
    result['exit_code']=0
    return result


def main():
    engine=create_engine(database_url(),connect_args={'connect_timeout':2})
    try:print(json.dumps(snapshot(engine),indent=2,default=lambda v:v.isoformat()))
    finally:engine.dispose()

if __name__=='__main__':main()
