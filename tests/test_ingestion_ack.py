from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
from src.brocker.mqtt_brocker import on_message
from src.telemetry import InvalidTelemetry
import pytest


def test_manual_ack_after_commit_or_replay_only():
    for result in [dict(temperature=20),None]:
        client=Mock(); engine=MagicMock()
        with patch('src.brocker.mqtt_brocker.process_packet',return_value=result),patch('src.outbox.record'):
            on_message(client,{'engine':engine,'registry':{}},SimpleNamespace(payload=b'{}',topic='t',qos=1,mid=17))
        client.ack.assert_called_once_with(17,1)
        client.disconnect.assert_not_called()


def test_pg_failure_disconnects_without_ack():
    client=Mock(); engine=MagicMock()
    with patch('src.brocker.mqtt_brocker.process_packet',side_effect=RuntimeError()),patch('src.outbox.record'):
        on_message(client,{'engine':engine,'registry':{}},SimpleNamespace(payload=b'{}',topic='t',qos=1,mid=17))
    client.ack.assert_not_called(); client.disconnect.assert_called_once()


def test_poison_packet_acknowledged_and_handler_continues():
    client=Mock(); engine=MagicMock()
    with patch('src.brocker.mqtt_brocker.process_packet',side_effect=InvalidTelemetry()),patch('src.outbox.record'),patch('src.security_events.capture') as capture:
        on_message(client,{'engine':engine,'registry':{}},SimpleNamespace(payload=b'{}',topic='t',qos=1,mid=17))
    client.ack.assert_called_once_with(17,1)
    client.disconnect.assert_not_called()

    capture.assert_called_once()
    assert capture.call_args.args[1:]==('rejected',)


@pytest.mark.parametrize('profile', [[], {}, None, True, 1, 1.5])
def test_real_parser_poison_manual_ack(profile):
    from src.telemetry import canonical
    client=Mock();engine=MagicMock()
    raw=canonical(dict(schema_version=2,profile=profile,nonce='',associated_data='',ciphertext=''))
    with patch('src.outbox.record') as record,patch('src.security_events.capture') as capture:
        on_message(client,dict(engine=engine,registry={}),SimpleNamespace(payload=raw,topic='iot/sensors/alpha',qos=1,mid=17))
    client.ack.assert_called_once_with(17,1)
    client.disconnect.assert_not_called()
    assert [c.args[1] for c in record.call_args_list]==['incoming','rejected']
    capture.assert_called_once()
    assert capture.call_args.args[1:]==('rejected',)


def test_reject_audit_commit_failure_is_not_acknowledged():
    client=Mock();engine=MagicMock()
    with patch('src.brocker.mqtt_brocker.process_packet',side_effect=InvalidTelemetry()),patch('src.outbox.record'),patch('src.security_events.capture',side_effect=RuntimeError('durable audit failed')):
        on_message(client,dict(engine=engine,registry={}),SimpleNamespace(payload=b'{}',topic='t',qos=1,mid=17))
    client.ack.assert_not_called();client.disconnect.assert_called_once()
