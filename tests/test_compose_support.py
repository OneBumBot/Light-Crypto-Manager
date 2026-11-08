import hashlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.brocker import mqtt_brocker as receiver
from src.web.models import Algorithm, TagJournal, db
from scripts.seed_demo import seed_demo


@pytest.mark.parametrize('rejected', [False, True])
def test_receiver_readiness_requires_successful_suback(tmp_path, monkeypatch, rejected):
    path = tmp_path / 'ready'
    monkeypatch.setenv('MQTT_READY_FILE', str(path))
    client = Mock()
    receiver.on_connect(client, None, None, 0, None)
    assert not path.exists()
    client.subscribe.assert_called_once_with(os.environ.get('MQTT_TOPIC', 'iot/sensors/#'), qos=1)
    receiver.on_subscribe(client, None, 1, [SimpleNamespace(is_failure=rejected)], None)
    assert path.exists() is not rejected
    receiver.on_disconnect(client, None, None, 0, None)
    assert not path.exists()


def test_compose_config_never_overwrites_secrets(tmp_path):
    path = tmp_path / 'compose.env'
    script = Path(__file__).resolve().parents[1] / 'scripts/prepare_compose.py'
    command = [sys.executable, str(script), '--env-file', str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert path.stat().st_mode & 0o777 == 0o600
    digest = hashlib.sha256(path.read_bytes()).digest()
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert hashlib.sha256(path.read_bytes()).digest() == digest


@pytest.mark.postgres
def test_demo_seed_is_idempotent(postgres_db):
    seed_demo()
    seed_demo()
    assert db.session.query(Algorithm).count() == 1
    assert db.session.query(TagJournal).count() == 1


@pytest.mark.postgres
def test_demo_seed_conflict_rolls_back_without_overwrite(postgres_db):
    db.session.add(TagJournal(Tag_ID=1, Tag_Name='existing-real-device'))
    db.session.commit()
    with pytest.raises(ValueError, match='conflict'):
        seed_demo()
    assert db.session.get(TagJournal, 1).Tag_Name == 'existing-real-device'
    assert db.session.query(Algorithm).count() == 0
