from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from src.telemetry import encode_packet
from src.web.models import Algorithm, TagJournal, User
from web_helpers import csrf_token, headers, login

pytestmark=pytest.mark.postgres


@pytest.fixture
def web(postgres_db):
    web=postgres_db
    assert web.app.config['WTF_CSRF_ENABLED'] is True
    for role in ['admin','operator','viewer']:
        user=User(username='security-'+role,email=role+'@example.test',role=role)
        user.set_password('public-test-password')
        web.db.session.add(user)
    web.db.session.add(Algorithm(Algorithm_ID=1,Algorithm_Name='original'))
    web.db.session.add(TagJournal(Tag_ID=1,Tag_Name='original-tag'))
    web.db.session.commit()
    yield web
    with web.socket_lock:
        peers=list(web.socket_connections)
    for sid in peers: web.socketio.server.disconnect(sid,namespace='/')


@pytest.mark.parametrize('role', ['viewer','operator'])
def test_role_cannot_modify_protected_table(web,role):
    with web.app.test_client() as client:
        assert login(client,'security-'+role).status_code==302
        assert client.put('/api/algorithms/1',json={'Algorithm_Name':'forbidden'},headers=headers(client)).status_code==403
        assert client.delete('/api/algorithms/1',headers=headers(client)).status_code==403
    assert web.db.session.get(Algorithm,1).Algorithm_Name=='original'


def test_operator_allowed_update_but_not_delete(web):
    with web.app.test_client() as client:
        login(client,'security-operator')
        assert client.put('/api/tag_journal/1',json={'Tag_Name':'allowed'},headers=headers(client)).status_code==200
        assert client.delete('/api/tag_journal/1',headers=headers(client)).status_code==403


@pytest.mark.parametrize('data', [[],{}, {'Algorithm_ID':2},{'metadata':'bad'}, {'__dict__':{}},
                                {'Algorithm_Name':'changed','password_hash':'bad'},
                                {'Algorithm_Name':'x'*41},{'Algorithm_Type_ID':True}])
def test_mass_assignment_and_bad_types(web,data):
    with web.app.test_client() as client:
        login(client)
        response=client.put('/api/algorithms/1',json=data,headers=headers(client))
        assert response.status_code==400
    assert web.db.session.get(Algorithm,1).Algorithm_Name=='original'


def test_csrf_cannot_be_skipped(web):
    with web.app.test_client() as other:
        foreign=csrf_token(other)
    with web.app.test_client() as client:
        assert client.post('/login',data={'username':'security-admin','password':'public-test-password'}).status_code==400
        login(client)
        assert client.put('/api/algorithms/1',json={'Algorithm_Name':'bad'}).status_code==400
        assert client.put('/api/algorithms/1',json={'Algorithm_Name':'bad'},headers={'X-CSRFToken':'wrong'}).status_code==400
        assert client.put('/api/algorithms/1',json={'Algorithm_Name':'bad'},headers={'X-CSRFToken':foreign}).status_code==400
        assert client.put('/api/algorithms/1',json={'Algorithm_Name':'valid'},headers=headers(client)).status_code==200
        assert client.get('/logout').status_code==405
        assert client.post('/logout').status_code==400
        assert client.post('/logout',headers=headers(client)).status_code==302


@pytest.mark.parametrize('target', ['https://evil.test','//evil.test','/\\evil.test',
    'javascript:alert(1)','http://[invalid','/%2f%2fevil.test','/\r\nLocation: https://evil.test'])
def test_open_redirect_rejected(web,target):
    with web.app.test_client() as client:
        response=login(client,next_value=target)
        assert response.status_code==302
        assert response.headers['Location']=='/'


def test_safe_local_redirect_preserved(web):
    with web.app.test_client() as client:
        assert login(client,next_value='/tables').headers['Location']=='/tables'


def test_socket_requires_login_csrf_and_same_origin(web):
    anonymous=web.socketio.test_client(web.app)
    assert not anonymous.is_connected()
    with web.app.test_client() as client:
        login(client,'security-viewer')
        assert not web.socketio.test_client(web.app,flask_test_client=client).is_connected()
        peer=web.socketio.test_client(web.app,flask_test_client=client,auth={'csrf_token':csrf_token(client,'/')})
        assert peer.is_connected()
        response=client.get('/socket.io/?EIO=4&transport=polling',headers={'Origin':'https://evil.test'})
        assert response.status_code==400
        web.update_dashboard({'temperature':22,'humidity':50,'timestamp':datetime.now(timezone.utc).isoformat()})
        assert [event['name'] for event in peer.get_received()]==['sensor_update']
        client.post('/logout',headers=headers(client))
        assert not peer.is_connected()


def test_socket_access_revoked_when_user_deactivated(web):
    with web.app.test_client() as client:
        login(client,'security-viewer')
        peer=web.socketio.test_client(web.app,flask_test_client=client,auth={'csrf_token':csrf_token(client,'/')})
        user=User.query.filter_by(username='security-viewer').one()
        user.is_active=False
        web.db.session.commit()
        web.update_dashboard({'temperature':22,'humidity':50,'timestamp':datetime.now(timezone.utc).isoformat()})
        assert not peer.is_connected()


def test_web_consumer_does_not_emit_replay(web,registry):
    with web.app.test_client() as client:
        login(client,'security-viewer')
        peer=web.socketio.test_client(web.app,flask_test_client=client,auth={'csrf_token':csrf_token(client,'/')})
        packet=encode_packet({'temperature':22,'humidity':50,'timestamp':datetime.now(timezone.utc).isoformat()},registry,'raspb1',1)
        message=SimpleNamespace(payload=json.dumps(packet).encode(),topic='iot/sensors/raspb1')
        web.on_message(None,None,message)
        assert len(peer.get_received())==1
        web.on_message(None,None,message)
        assert peer.get_received()==[]
        peer.disconnect()


def test_database_exception_not_exposed(web):
    with web.db.engine.begin() as connection:
        connection.execute(text('ALTER TABLE "Algorithms" ADD CONSTRAINT reject_name CHECK ("Algorithm_Name" <> \'blocked\')'))
    with web.app.test_client() as client:
        login(client)
        response=client.put('/api/algorithms/1',json={'Algorithm_Name':'blocked'},headers=headers(client))
        assert response.status_code==400
        assert 'reject_name' not in response.get_data(as_text=True)
        assert 'SELECT' not in response.get_data(as_text=True)
        assert 'psycopg' not in response.get_data(as_text=True)
        assert client.put('/api/algorithms/1',json={'Algorithm_Name':'good'},headers=headers(client)).status_code==200


def test_unknown_role_fails_closed(web):
    user=User(username='invalid-role',email='invalid@example.test',role='unrecognized')
    user.set_password('public-test-password')
    web.db.session.add(user);web.db.session.commit()
    with web.app.test_client() as client:
        login(client,'invalid-role')
        assert client.get('/api/latest-data').status_code==401
        assert not web.socketio.test_client(web.app,flask_test_client=client).is_connected()


def test_table_renders_untrusted_values_as_text(web):
    payload='<img src=x onerror=alert(1)>'
    web.db.session.get(Algorithm,1).Algorithm_Name=payload
    web.db.session.commit()
    with web.app.test_client() as client:
        login(client)
        response=client.get('/table/algorithms')
        assert response.status_code==200
        body=response.get_data(as_text=True)
        assert payload not in body
        assert '&lt;img' in body
        assert 'const primaryKeys' in body
