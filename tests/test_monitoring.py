"""Integration read-model truth semantics: real PG/AEAD, no invented effective state."""
from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy import select,func,update
from pymongo.errors import ServerSelectionTimeoutError
from src.web.monitoring import telemetry_state,worker,snapshot
from src.device_control import models as m,server
from src.crypto_profiles import ASCON,AES
from src.outbox import outbox
from src.device_control.state import DeviceState
from src.device_control.protocol import open_message,topic
from test_control_storage import setup,baseline,packet,pending_command
from src.ingestion import process_packet


@pytest.mark.parametrize('enabled,seconds,expected',[(True,None,'unknown'),(True,1,'recent'),(True,16,'stale'),(True,-30,'stale'),(False,1,'disabled'),(False,None,'disabled')])
def test_freshness_is_admission_age_not_presence(enabled,seconds,expected):
    now=datetime.now(timezone.utc);stamp=now-timedelta(seconds=seconds) if seconds is not None else None
    assert telemetry_state(enabled,stamp,now)==expected


def test_worker_ready_requires_fresh_evidence():
    now=datetime.now(timezone.utc)
    assert worker(None,now,'heartbeat',10,'PG')['status']=='unknown'
    assert worker(dict(heartbeat=now-timedelta(seconds=11),status='ready'),now,'heartbeat',10,'PG')['status']=='stale'
    assert worker(dict(heartbeat=now,status='failed'),now,'heartbeat',10,'PG')['status']=='unavailable'
    assert worker(dict(heartbeat=now,status='ready'),now,'heartbeat',10,'PG')['status']=='ready'


@pytest.mark.postgres
def test_snapshot_ack_is_not_effective_and_identity_is_bound(postgres_db,registry,tmp_path):
    web=postgres_db;cfg=setup(web,registry);seq=baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    state=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True)
    try:
        for _ in range(2):
            _,body=pending_command(engine,cfg)
            ack=open_message(state.execute(body,cfg),bytes.fromhex(cfg['status_key']),'device','raspb1',topic('raspb1','device'))
            with engine.begin() as c:server.handle_ack(c,ack)
        with engine.connect() as c:result=snapshot(c,'raspb1')
        d=result['items'][0]
        assert d['device_id']=='raspb1' and d['effective_profile']==ASCON and d['reported_profile']==AES
        assert d['pending']['phase']=='DEVICE_APPLIED'
        assert d['effective_evidence']['event_id']!=None
        assert result['acks'][0]['result']=='DEVICE_APPLIED'
        assert all('body' not in a and 'wire' not in a for a in result['acks']+result['commands'])
        process_packet(packet(registry,seq,AES),registry,engine,'iot/sensors/raspb1')
        with engine.connect() as c:result=snapshot(c,'raspb1')
        d=result['items'][0]
        assert d['effective_profile']==AES and d['pending'] is None
        assert d['effective_evidence']['event_id']==d['telemetry']['event_id']
        assert d['telemetry']['crypto_profile']=='AES-128-GCM'
        assert result['transitions'][0]['phase']=='EFFECTIVE_CONFIRMED'
    finally:state.close()


@pytest.mark.postgres
def test_monitoring_stale_and_disabled_not_online(postgres_db,registry):
    web=postgres_db;setup(web,registry);baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:c.execute(update(outbox).values(created_at=datetime.now(timezone.utc)-timedelta(seconds=20)))
    with engine.connect() as c:
        result=snapshot(c,'raspb1');assert result['items'][0]['status']=='stale' and result['summary']['recent']==0
    from src.devices import devices
    with engine.begin() as c:c.execute(update(devices).where(devices.c.device_id=='raspb1').values(enabled=False))
    with engine.connect() as c:assert snapshot(c,'raspb1')['items'][0]['status']=='disabled'


@pytest.mark.postgres
def test_monitoring_api_mongo_failure_independent_rbac_limits(postgres_db,registry,monkeypatch):
    from test_history_api import login
    from src.web import app as module
    from src.web.models import ROLE_PERMISSIONS,UserRole
    from types import SimpleNamespace
    web=postgres_db;setup(web,registry);baseline(web,registry)
    class Collection:
        def find_one(self,*args,**kwargs):raise ServerSelectionTimeoutError('test outage')
    monkeypatch.setattr(module,'history_repository',lambda:SimpleNamespace(collection=Collection()))
    anon=web.app.test_client();assert anon.get('/api/monitoring').status_code==401
    viewer=login(web)
    response=viewer.get('/api/monitoring/raspb1');assert response.status_code==200
    data=response.json
    assert len(data['items'])==1 and data['items'][0]['device_id']=='raspb1'
    assert data['components']['ml']['trusted_detector'] is False
    assert data['components']['postgres']['status']=='available'
    assert data['components']['mongo']['status']=='unavailable'
    assert data['items'][0]['telemetry'] is not None
    assert data['trusted_detector'] is False and data['policy_mode']=='DRY_RUN'
    for query in ['limit=101','limit=no','offset=-1','device_id=raspb1','limit=1&limit=2']:
        assert viewer.get('/api/monitoring?'+query).status_code==400
    assert viewer.get('/api/monitoring/missing').status_code==404
    assert viewer.get('/api/monitoring/raspb1').headers['Cache-Control']=='no-store'
    text=response.text
    for secret in ['key_hex','command_key','status_key','key_fingerprint','sequence_reserved','wire','"body"']:
        assert secret not in text
    monkeypatch.setitem(ROLE_PERMISSIONS[UserRole.VIEWER],'tables',[])
    assert viewer.get('/api/monitoring').status_code==403
    assert viewer.get('/monitoring').status_code==403


@pytest.mark.postgres
def test_receiver_heartbeat_is_diagnostic_only(postgres_db):
    from src.system_status import receiver_heartbeat,heartbeats
    from src.replay import replay_state
    engine=postgres_db.db.engine
    receiver_heartbeat(engine,True);receiver_heartbeat(engine,False)
    with engine.connect() as c:
        row=c.execute(select(heartbeats)).mappings().one()
        assert row['component']=='receiver' and row['ready'] is False
        assert c.scalar(select(func.count()).select_from(replay_state))==0
        assert c.scalar(select(func.count()).select_from(outbox))==0
        assert c.scalar(select(func.count()).select_from(m.commands))==0


@pytest.mark.postgres
def test_expired_transition_snapshot_is_uncertain_not_active(postgres_db,registry):
    web=postgres_db;setup(web,registry);baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:
        tid=server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
        c.execute(update(m.transitions).where(m.transitions.c.id==tid).values(deadline=datetime.now(timezone.utc)-timedelta(seconds=1)))
    with engine.connect() as c:
        result=snapshot(c,'raspb1')
        assert result['summary']['active_transitions']==0 and result['summary']['uncertain_transitions']==1
        assert result['items'][0]['pending']['expired'] is True
        assert result['items'][0]['effective_profile']==ASCON
        assert c.scalar(select(m.transitions.c.phase))=='PREPARED_SERVER' # read adapter never writes FSM
