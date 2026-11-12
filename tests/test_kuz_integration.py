"""Real PG effects of MGM failures and conservative key reservation."""
import base64,uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select,update,func
from src.crypto_profiles import ASCON,AES,KUZ
from src.telemetry import encode_packet,decode_packet,InvalidTelemetry,canonical,strict_json
from src.kuz_usage import nonce,usage,reservations,initialize_fresh,reserve,MAX_INVOCATIONS
from src.device_control import server,models as m
from src.device_control.protocol import message,CONTROLLER
from src.ingestion import process_packet
from src.outbox import outbox
from src.replay import replay_state


def test_icn_fixed_width_injective_and_bounds():
    coordinates=[(e,s) for e in [1,2,2**31-1] for s in [1,2,2**32-1,2**63-1]]
    values=[nonce(e,s) for e,s in coordinates]
    assert len(set(values))==len(values)
    assert all(len(v)==16 and not v[0]&128 for v in values)
    for bad in [None,True,False,0,-1,1.5,[],{},2**63]:
        with pytest.raises(ValueError):nonce(1,bad)
    with pytest.raises(ValueError):nonce(2**31,1)


def config(registry):
    registry['raspb1']['telemetry_keys']={'AES-128-GCM':bytes(range(90,106)).hex(),'Kuznyechik-MGM':bytes(range(110,142)).hex()}
    return dict(registry=registry['raspb1'],command_key=bytes(range(150,182)).hex(),status_key=bytes(range(190,222)).hex(),command_epoch=1,capabilities=[ASCON,AES,KUZ])


@pytest.mark.postgres
def test_reservation_is_atomic_idempotent_crash_burned_and_bounded(postgres_db,registry):
    conf=config(registry);engine=postgres_db.db.engine
    with engine.begin() as c:server.provision(c,{'raspb1':conf})
    req=message('raspb1','lease_request',dict(boot_id=str(uuid.uuid4()),key_epoch=1,local_profile=ASCON))
    with engine.begin() as c:first=server.grant(c,req)
    with engine.begin() as c:assert server.grant(c,req)==first
    def issue(_):
        q=message('raspb1','lease_request',dict(boot_id=str(uuid.uuid4()),key_epoch=1,local_profile=ASCON))
        with engine.begin() as c:return server.grant(c,q)['data']
    with ThreadPoolExecutor(max_workers=2) as pool:ranges=list(pool.map(issue,range(2)))
    assert len({r['first_sequence'] for r in ranges})==2
    with engine.connect() as c:
        u=c.execute(select(usage)).mappings().one()
        assert u['reserved_invocations']==30000 and u['reserved_blocks']==30000*320
        assert c.scalar(select(func.count()).select_from(reservations))==3
    with pytest.raises(RuntimeError):
        with engine.begin() as c:
            reserve(c,'raspb1',1,str(uuid.uuid4()),30001,40000)
            raise RuntimeError('simulated crash before durable commit')
    with engine.begin() as c:
        with pytest.raises(ValueError,match='reuse'):reserve(c,'raspb1',1,str(uuid.uuid4()),1,10000)
        c.execute(update(usage).values(max_invocations=30000,max_blocks=30000*320))
    with pytest.raises(ValueError,match='exhausted'):issue(0)
    with engine.connect() as c:assert c.scalar(select(m.devices.c.sequence_reserved))==30000


@pytest.mark.postgres
def test_bad_tag_cannot_change_admission_outbox_evidence_or_replay(postgres_db,registry):
    from test_postgres import seed_device
    from test_control_storage import packet,baseline
    web=postgres_db;seed_device(web);conf=config(registry)
    with web.db.engine.begin() as c:server.provision(c,{'raspb1':conf})
    sequence=baseline(web,registry)
    # Explicit test authorization of target, real AEAD remains mandatory.
    with web.db.engine.begin() as c:
        c.execute(update(m.devices).values(effective_profile=KUZ))
    p=packet(registry,sequence,KUZ)
    ct=base64.b64decode(p['ciphertext']);p['ciphertext']=base64.b64encode(ct[:-1]+bytes([ct[-1]^1])).decode()
    def snapshot():
        with web.db.engine.connect() as c:
            return (c.scalar(select(func.count()).select_from(outbox)),c.scalar(select(replay_state.c.last_sequence)),
                c.scalar(select(func.count()).select_from(m.evidence)),c.scalar(select(m.devices.c.effective_profile)))
    before=snapshot()
    with pytest.raises(InvalidTelemetry):process_packet(p,registry,web.db.engine,'iot/sensors/raspb1')
    assert snapshot()==before
    with web.db.engine.connect() as c:assert c.scalar(select(usage.c.verify_attempts))==1
    good=packet(registry,sequence+1,KUZ)
    assert process_packet(good,registry,web.db.engine,'iot/sensors/raspb1')
    assert process_packet(good,registry,web.db.engine,'iot/sensors/raspb1') is None
    assert snapshot()[0]==before[0]+1
    with web.db.engine.begin() as c:c.execute(update(usage).values(max_verify_attempts=3))
    with pytest.raises(InvalidTelemetry,match='budget'):process_packet(packet(registry,sequence+2,KUZ),registry,web.db.engine,'iot/sensors/raspb1')


@pytest.mark.parametrize('field',['profile','key_epoch','sequence_number','device_id','topic'])
@pytest.mark.parametrize('bad',[None,True,False,0,1.5,[],{}])
def test_mgm_malformed_aad_is_controlled(registry,field,bad):
    from datetime import datetime,timezone
    config(registry)
    p=encode_packet(dict(temperature=23,humidity=45,timestamp=datetime.now(timezone.utc).isoformat()),registry,'raspb1',1,profile=KUZ)
    aad=strict_json(base64.b64decode(p['associated_data']));aad[field]=bad;p['associated_data']=base64.b64encode(canonical(aad)).decode()
    with pytest.raises(InvalidTelemetry):decode_packet(p,'iot/sensors/raspb1',registry)


def test_nonce_authority_rollback_latches_across_restart(tmp_path):
    from src.device_control.state import DeviceState
    path=tmp_path/'device.db'
    state=DeviceState(path,'alpha',1,initialize=True,strict_authority=True)
    state.accept_lease(1,10000)
    with pytest.raises(ValueError,match='rollback'):state.accept_lease(1,10000)
    state.close()
    with pytest.raises(ValueError,match='blocked'):DeviceState(path,'alpha',1)


@pytest.mark.parametrize('length',[0,16,31,33,64])
def test_registry_keeps_profile_specific_key_lengths(registry,length):
    from src.telemetry import validate_registry
    config(registry);registry['raspb1']['telemetry_keys']['Kuznyechik-MGM']=('ab'*length)
    with pytest.raises(InvalidTelemetry):validate_registry(registry)


def test_mgm_missing_capability_and_key_cannot_prepare(tmp_path,registry):
    from src.device_control.state import DeviceState
    from src.device_control.protocol import message,CONTROLLER
    conf=config(registry);conf['capabilities']=[ASCON]
    state=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True)
    state.accept_lease(1,10000)
    cid=str(uuid.uuid4())
    body=message('raspb1','command',dict(command_id=cid,transition_id=str(uuid.uuid4()),correlation_id=str(uuid.uuid4()),command_type='set_profile',phase='PREPARE',requested_profile=KUZ,source_version='admin-v1',controller_identity=CONTROLLER,profile_config_version=1,key_reference=KUZ+':1',command_epoch=1,command_sequence=1),message_id=cid)
    # Full signed envelope verification is covered by protocol tests; execute receives verified body.
    from src.device_control.protocol import open_message,topic
    response=open_message(state.execute(body,conf),bytes.fromhex(conf['status_key']),'device','raspb1',topic('raspb1','device'))
    assert response['data']['result']=='UNSUPPORTED' and state.read()['profile']==ASCON and state.read()['prepared'] is None
    state.close()


@pytest.mark.parametrize('bad',[None,True,False,0,1,1.5,[],{},['Kuznyechik-MGM'],{'algorithm':'Kuznyechik-MGM'},'unknown'])
def test_mgm_outer_profile_type_guard(registry,bad):
    from test_control_storage import packet
    config(registry);p=packet(registry,1,KUZ);p['profile']=bad
    with pytest.raises(InvalidTelemetry):decode_packet(p,'iot/sensors/raspb1',registry)


@pytest.mark.parametrize('source,target',[(AES,KUZ),(KUZ,ASCON)])
def test_ciphertext_cannot_be_relabelled(registry,source,target):
    from test_control_storage import packet
    from src.crypto_profiles import PROFILES
    config(registry);p=packet(registry,1,source)
    ad=strict_json(base64.b64decode(p['associated_data']));ad['profile']=PROFILES[target]['algorithm'];p['profile']=ad['profile'];p['associated_data']=base64.b64encode(canonical(ad)).decode()
    if target==KUZ:p['nonce']=base64.b64encode(nonce(1,1)).decode()
    with pytest.raises(InvalidTelemetry):decode_packet(p,'iot/sensors/raspb1',registry)
