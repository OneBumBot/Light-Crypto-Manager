"""Real PostgreSQL transactions, real AEAD/device ledger; no network mocks."""
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import uuid,json,hashlib
import pytest
from sqlalchemy import select,update,func,text
from src.crypto_profiles import ASCON,AES
from src.device_control import models as m,server
from src.device_control.protocol import message,open_message,topic
from src.device_control.state import DeviceState
from src.telemetry import encode_packet,canonical,InvalidTelemetry
from src.ingestion import process_packet
from src.outbox import outbox
from src.replay import replay_state
from web_helpers import csrf_token,headers

pytestmark=pytest.mark.postgres


def setup(web,registry):
    from test_postgres import seed_device
    seed_device(web)
    registry['raspb1']['telemetry_keys']={'AES-128-GCM':bytes(range(100,116)).hex()}
    conf=dict(registry=registry['raspb1'],command_key=bytes(range(100,132)).hex(),status_key=bytes(range(132,164)).hex(),command_epoch=1,capabilities=[ASCON,AES])
    with web.db.engine.begin() as c:server.provision(c,{'raspb1':conf})
    return conf


def lease(engine,profile=ASCON):
    req=message('raspb1','lease_request',dict(boot_id=str(uuid.uuid4()),key_epoch=1,local_profile=profile))
    with engine.begin() as c:return server.grant(c,req)


def packet(registry,seq,profile=ASCON):
    return encode_packet(dict(temperature=25,humidity=48,timestamp=datetime.now(timezone.utc).isoformat()),registry,'raspb1',seq,profile=profile)


def baseline(web,registry):
    grant=lease(web.db.engine);seq=grant['data']['first_sequence']
    process_packet(packet(registry,seq),registry,web.db.engine,'iot/sensors/raspb1')
    return seq+1


def pending_command(engine,conf):
    with engine.begin() as c:
        cmd=server.claim(c,{'raspb1':conf})
    assert cmd is not None
    return cmd,open_message(cmd['wire'].encode(),bytes.fromhex(conf['command_key']),'controller','raspb1',topic('raspb1','controller'))


def test_effective_requires_real_telemetry_and_ack_loss_does_not_downgrade(postgres_db,registry,tmp_path):
    web=postgres_db;conf=setup(web,registry);seq=baseline(web,registry)
    with web.db.engine.begin() as c:tid=server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    state=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True)
    cmd,body=pending_command(web.db.engine,conf)
    ready=state.execute(body,conf)
    ack=open_message(ready,bytes.fromhex(conf['status_key']),'device','raspb1',topic('raspb1','device'))
    with web.db.engine.begin() as c:assert server.handle_ack(c,ack)
    with web.db.engine.begin() as c:assert not server.handle_ack(c,ack)
    cmd,body=pending_command(web.db.engine,conf);state.execute(body,conf) # deliberately lose authenticated ACTIVATE ACK
    assert state.read()['profile']==AES
    with web.db.engine.connect() as c:assert c.scalar(select(m.devices.c.effective_profile))==ASCON
    process_packet(packet(registry,seq,AES),registry,web.db.engine,'iot/sensors/raspb1')
    with web.db.engine.connect() as c:
        d=c.execute(select(m.devices)).mappings().one();t=c.execute(select(m.transitions)).mappings().one()
        assert d['effective_profile']==AES and t['phase']=='EFFECTIVE_CONFIRMED'
        evidence=c.execute(select(outbox).where(outbox.c.id==d['effective_event'])).mappings().one()
        assert evidence['payload']['crypto_profile']=='AES-128-GCM' and evidence['sequence_number']==seq
    with pytest.raises(InvalidTelemetry):process_packet(packet(registry,seq+1),registry,web.db.engine,'iot/sensors/raspb1')
    state.close()


def test_nonce_grants_survive_restart_and_local_restore(postgres_db,registry):
    conf=setup(postgres_db,registry);engine=postgres_db.db.engine
    first=lease(engine);second=lease(engine) # restored local state still requests a fresh challenge-bound lease
    assert second['data']['first_sequence']>first['data']['last_sequence']
    p1=packet(registry,first['data']['first_sequence'],AES);p2=packet(registry,second['data']['first_sequence'],AES)
    assert p1['nonce']!=p2['nonce']
    with pytest.raises(RuntimeError):
        with engine.begin() as c:
            server.grant(c,message('raspb1','lease_request',dict(boot_id=str(uuid.uuid4()),key_epoch=1,local_profile=ASCON)))
            raise RuntimeError('rollback')
    third=lease(engine)
    assert third['data']['first_sequence']==second['data']['last_sequence']+1


def test_atomic_admission_rollback_keeps_effective_and_replay(postgres_db,registry):
    web=postgres_db;setup(web,registry);seq=baseline(web,registry)
    # Deliberately fail outbox INSERT via a real database constraint; admission/evidence must rollback.
    with web.db.engine.begin() as c:
        c.execute(text('ALTER TABLE telemetry_outbox ADD CONSTRAINT injected_fail CHECK (sequence_number < 2)'))
    with pytest.raises(Exception):process_packet(packet(registry,seq),registry,web.db.engine,'iot/sensors/raspb1')
    with web.db.engine.connect() as c:
        assert c.scalar(select(replay_state.c.last_sequence).where(replay_state.c.consumer=='receiver'))==seq-1
        assert c.scalar(select(func.count()).select_from(outbox))==1


def test_conflicting_admin_requests_are_serialized(postgres_db,registry):
    web=postgres_db;setup(web,registry);baseline(web,registry)
    engine=web.db.engine
    def run(_):
        try:
            with engine.begin() as c:return server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sum(x is not None for x in results)==1
    with web.db.engine.connect() as c:assert c.scalar(select(func.count()).select_from(m.commands))==1


def test_research_and_simulated_sources_cannot_authorize(postgres_db,registry):
    web=postgres_db;setup(web,registry);baseline(web,registry)
    for mode,actor in [('DRY_RUN','admin:1'),(server.MODE,'ml:research'),('SIMULATION','admin:1')]:
        with pytest.raises(ValueError):
            with web.db.engine.begin() as c:server.request_switch(c,'raspb1',AES,actor,mode=mode)


@pytest.mark.parametrize('role',['operator','viewer','admin'])
def test_control_web_roles_csrf_and_fields(postgres_db,registry,monkeypatch,role):
    web=postgres_db;setup(web,registry);baseline(web,registry)
    from src.web.models import User
    monkeypatch.setenv('CONTROL_MODE',server.MODE)
    web.app.config.update(TESTING=True)
    for created_role in ['admin','operator','viewer']:
        u=User(username='ctrl-'+created_role,email=created_role+'@example.test',role=created_role);u.set_password('public-unit-test-password');web.db.session.add(u)
    web.db.session.commit()
    with web.app.test_client() as client:
        assert client.post('/login',data={'username':'ctrl-'+role,'password':'public-unit-test-password','csrf_token':csrf_token(client)}).status_code==302
        assert client.get('/api/control').status_code==200
        assert 'key_fingerprint' not in client.get('/api/control').text
        body={'profile':AES,'ttl':120}
        assert client.post('/api/control/raspb1/switch',json=body).status_code==400
        resp=client.post('/api/control/raspb1/switch',json=body,headers=headers(client))
        assert resp.status_code==(202 if role=='admin' else 403)
