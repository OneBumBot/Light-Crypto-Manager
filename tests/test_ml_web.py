import pytest
from src.web.models import ROLE_PERMISSIONS,UserRole,User
from test_history_api import login

pytestmark=pytest.mark.postgres


def test_ml_routes_auth_permissions_and_separate_sources(postgres_db,monkeypatch):
    web=postgres_db;client=web.app.test_client()
    assert client.get('/api/ml/events').status_code==401
    assert client.get('/api/ml/status').status_code==401
    viewer=login(web)
    assert viewer.get('/ml').status_code==200
    assert viewer.get('/api/ml/events').json['items']==[]
    status=viewer.get('/api/ml/status')
    assert status.status_code==200 and status.json['protocol_rejections'] is None and status.json['rule_anomalies'] is None
    assert viewer.get('/api/ml/events?limit=201').status_code==400
    assert viewer.get('/api/ml/events?device_id=$where').status_code==400
    monkeypatch.setitem(ROLE_PERMISSIONS[UserRole.VIEWER],'tables',[])
    assert viewer.get('/api/ml/events').status_code==403
    assert viewer.get('/api/ml/status').status_code==403
    assert viewer.get('/ml').status_code==403
