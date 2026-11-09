from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
from src.brocker.mqtt_brocker import on_message
from src.telemetry import InvalidTelemetry


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
