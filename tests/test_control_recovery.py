"""Critical failure states with real isolated PostgreSQL and durable SQLite."""
from datetime import timedelta
import copy,uuid
import pytest
from sqlalchemy import select,update,func
from src.device_control import server,models as m
from src.device_control.protocol import open_message,topic
from src.device_control.state import DeviceState
from src.crypto_profiles import ASCON,AES
from src.telemetry import InvalidTelemetry
from src.ingestion import process_packet
from test_control_storage import setup,baseline,packet,pending_command,lease

pytestmark=pytest.mark.postgres


def test_prepare_alone_and_expiry_cannot_claim_effective(postgres_db,registry,tmp_path):
    web=postgres_db;cfg=setup(web,registry);seq=baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:tid=server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    cmd,body=pending_command(engine,cfg);s=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True);s.execute(body,cfg)
    assert s.read()['profile']==ASCON
    with engine.begin() as c:c.execute(update(m.transitions).where(m.transitions.c.id==tid).values(deadline=server.now(c)-timedelta(seconds=1)))
    with engine.begin() as c:assert server.claim(c,{'raspb1':cfg}) is None
    with engine.connect() as c:
        assert c.scalar(select(m.transitions.c.phase))=='UNKNOWN_OUTCOME'
        assert c.scalar(select(m.devices.c.effective_profile))==ASCON
    with pytest.raises(InvalidTelemetry):process_packet(packet(registry,seq),registry,engine,'iot/sensors/raspb1')
    s.close()


def test_forged_and_mismatched_ack_do_not_activate(postgres_db,registry,tmp_path):
    web=postgres_db;cfg=setup(web,registry);baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    cmd,body=pending_command(engine,cfg);s=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True)
    raw=s.execute(body,cfg)
    bad=raw.replace(b'READY',b'FAILED')
    with pytest.raises(ValueError):open_message(bad,bytes.fromhex(cfg['status_key']),'device','raspb1',topic('raspb1','device'))
    ack=open_message(raw,bytes.fromhex(cfg['status_key']),'device','raspb1',topic('raspb1','device'))
    for field,value in [('correlation_id',str(uuid.uuid4())),('requested_profile',ASCON),('command_epoch',2),('command_sha256','00'*32)]:
        forged=copy.deepcopy(ack);forged['data'][field]=value
        with pytest.raises(ValueError):
            with engine.begin() as c:server.handle_ack(c,forged)
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(m.acks))==0
        assert c.scalar(select(m.transitions.c.phase))=='PREPARED_SERVER'
        assert c.scalar(select(m.devices.c.effective_profile))==ASCON
    s.close()


def test_ack_transaction_rollback_does_not_queue_activate(postgres_db,registry,tmp_path):
    web=postgres_db;cfg=setup(web,registry);baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    cmd,body=pending_command(engine,cfg);s=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True)
    ack=open_message(s.execute(body,cfg),bytes.fromhex(cfg['status_key']),'device','raspb1',topic('raspb1','device'))
    with pytest.raises(RuntimeError):
        with engine.begin() as c:server.handle_ack(c,ack);raise RuntimeError('simulated crash before commit, no network')
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(m.commands))==1
        assert c.scalar(select(func.count()).select_from(m.acks))==0
        assert c.scalar(select(m.devices.c.command_acknowledged))==0
    s.close()


def test_old_epoch_and_missing_telemetry_key_are_rejected(tmp_path):
    from test_control_protocol import command,conf
    s=DeviceState(tmp_path/'state.db','alpha',1,initialize=True);c=conf()
    old=command();old['data']['command_epoch']=2;old['data']['key_reference']=AES+':2'
    with pytest.raises(ValueError):s.execute(old,c)
    c['registry']['telemetry_keys']={}
    raw=s.execute(command(),c)
    assert open_message(raw,bytes.fromhex(c['status_key']),'device','alpha',topic('alpha','device'))['data']['result']=='UNSUPPORTED'
    assert s.read()['profile']==ASCON;s.close()


def test_server_range_rollback_is_detected_on_device(tmp_path):
    s=DeviceState(tmp_path/'state.db','alpha',1,initialize=True);s.accept_lease(1,10000);s.close()
    s=DeviceState(tmp_path/'state.db','alpha',1)
    with pytest.raises(ValueError):s.accept_lease(1,10000)
    with pytest.raises(ValueError):s.accept_lease(9999,19998)
    s.accept_lease(10001,20000);s.close()


def test_reconciliation_never_changes_effective_without_new_telemetry(postgres_db,registry,tmp_path):
    web=postgres_db;cfg=setup(web,registry);seq=baseline(web,registry);engine=web.db.engine
    with engine.begin() as c:tid=server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    s=DeviceState(tmp_path/'state.db','raspb1',1,initialize=True)
    cmd,body=pending_command(engine,cfg)
    ack=open_message(s.execute(body,cfg),bytes.fromhex(cfg['status_key']),'device','raspb1',topic('raspb1','device'))
    with engine.begin() as c:server.handle_ack(c,ack)
    cmd,body=pending_command(engine,cfg);s.execute(body,cfg)
    with engine.begin() as c:
        c.execute(update(m.transitions).where(m.transitions.c.id==tid).values(deadline=server.now(c)-timedelta(seconds=1)))
        server.claim(c,{'raspb1':cfg})
    with pytest.raises(InvalidTelemetry):process_packet(packet(registry,seq,AES),registry,engine,'iot/sensors/raspb1')
    with engine.begin() as c:server.reopen_reconciliation(c,'raspb1',tid,'admin:1',mode=server.MODE)
    with engine.connect() as c:assert c.scalar(select(m.devices.c.effective_profile))==ASCON
    process_packet(packet(registry,seq,AES),registry,engine,'iot/sensors/raspb1')
    with engine.connect() as c:assert c.scalar(select(m.devices.c.effective_profile))==AES
    s.close()
