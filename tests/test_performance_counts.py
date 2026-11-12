"""Real PostgreSQL grouping of admitted Ascon/AES packets, not labels in reports."""
import pytest
from scripts.performance_probe import profile_counts
from test_control_storage import setup,baseline,packet,pending_command
from src.crypto_profiles import AES
from src.device_control import server
from src.device_control.protocol import open_message,topic
from src.device_control.state import DeviceState
from src.ingestion import process_packet


@pytest.mark.postgres
def test_counts_group_actual_profiles_with_shared_json_expression(postgres_db,registry,tmp_path):
    web=postgres_db;config=setup(web,registry);seq=baseline(web,registry);engine=web.db.engine
    process_packet(packet(registry,seq),registry,engine,'iot/sensors/raspb1')
    with engine.begin() as c:server.request_switch(c,'raspb1',AES,'admin:1',mode=server.MODE)
    state=DeviceState(tmp_path/'device.db','raspb1',1,initialize=True)
    try:
        for _ in range(2):
            _,command=pending_command(engine,config)
            response=state.execute(command,config)
            ack=open_message(response,bytes.fromhex(config['status_key']),'device','raspb1',topic('raspb1','device'))
            with engine.begin() as c:server.handle_ack(c,ack)
        process_packet(packet(registry,seq+1,AES),registry,engine,'iot/sensors/raspb1')
        assert profile_counts(engine)==[
            dict(device_id='raspb1',profile='AES-128-GCM',count=1),
            dict(device_id='raspb1',profile='Ascon-AEAD128',count=2)]
    finally:state.close()
