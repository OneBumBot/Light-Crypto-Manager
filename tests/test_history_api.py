from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from src.web.models import User
from web_helpers import csrf_token

pytestmark=pytest.mark.postgres


def login(web,role='viewer'):
    user=User(username='history-'+role,email=role+'@history.test',role=role)
    user.set_password('public-test-password')
    web.db.session.add(user); web.db.session.commit()
    client=web.app.test_client()
    assert client.post('/login',data=dict(username=user.username,password='public-test-password',csrf_token=csrf_token(client))).status_code==302
    return client


def test_history_auth_roles_empty_and_outage(postgres_db):
    web=postgres_db
    client=web.app.test_client()
    assert client.get('/api/telemetry/history').status_code==401
    repo=Mock(); repo.history.return_value=[]
    web.app.extensions['telemetry_repository']=repo
    try:
        viewer=login(web)
        assert viewer.get('/api/telemetry/history').json['items']==[]
        assert viewer.get('/api/telemetry/metrics').status_code==403
        repo.history.side_effect=ConnectionError('password should not escape')
        response=viewer.get('/api/telemetry/history')
        assert response.status_code==503 and b'password' not in response.data
        web.db.session.get(User,1).role='invalid'
        web.db.session.commit()
        from flask import g
        g.pop('_login_user',None)
        assert viewer.get('/api/telemetry/history').status_code==401
    finally: web.app.extensions.pop('telemetry_repository',None)


@pytest.mark.parametrize('query',['limit=0','limit=501','offset=-1','offset=10001','limit=x',
    'device_id=$where','start=bad','start=2026-01-01','unknown=x','limit=1&limit=2',
    'start=2026-02-01T00:00:00Z&end=2026-01-01T00:00:00Z'])
def test_history_validates_query(postgres_db,query):
    client=login(postgres_db)
    assert client.get('/api/telemetry/history?'+query).status_code==400


def test_real_history_api_reads_mongo(postgres_db,monkeypatch):
    import os, uuid
    if os.environ.get('TEST_MONGO_ENABLED')!='1': pytest.skip('authenticated MongoDB required')
    from src.mongo_repository import MongoRepository
    from test_mongo_storage import payload
    relay=MongoRepository()
    data=payload()
    relay.store(data); relay.close()
    monkeypatch.setenv('MONGO_PASSWORD_FILE','/run/storage/history.password')
    web=postgres_db
    web.app.extensions.pop('telemetry_repository',None)
    try:
        client=login(web)
        response=client.get('/api/telemetry/history',query_string=dict(device_id=data['device_id'],limit=1,start='2020-01-01T00:00:00Z'))
        assert response.status_code==200
        assert response.json['items'][0]['device_id']==data['device_id']
        assert response.json['items'][0]['temperature']==24.5
        assert client.get('/api/telemetry/history',query_string=dict(device_id=data['device_id'],offset=1)).json['items']==[]
    finally:
        repo=web.app.extensions.pop('telemetry_repository',None)
        if repo: repo.close()
