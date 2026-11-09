"""Real HTTP/Socket.IO checks against the running web container, with disposable user."""
import os
import re
import secrets
import threading
import uuid

import requests
import socketio
from src.web.app import app
from src.web.models import db, User


def main():
    base=os.environ.get('WEB_TEST_URL','http://web:5000')
    username='web-check-'+uuid.uuid4().hex[:12]
    password=secrets.token_urlsafe(24)
    user_id=None
    active=socketio.Client(reconnection=False,request_timeout=5)
    anonymous=socketio.Client(reconnection=False,request_timeout=5)
    try:
        with app.app_context():
            user=User(username=username,email=username+'@example.test',role='viewer')
            user.set_password(password)
            db.session.add(user);db.session.commit();user_id=user.id
        try: anonymous.connect(base,transports=['polling'],wait_timeout=5)
        except socketio.exceptions.ConnectionError: pass
        else: raise AssertionError('Anonymous Socket.IO accepted')
        print('PASS: real anonymous Socket.IO connection rejected')
        session=requests.Session()
        assert session.post(base+'/login',data={'username':username,'password':password},timeout=5).status_code==400
        def token(path='/login'):
            response=session.get(base+path,timeout=5)
            match=re.search(r'name="csrf-token" content="([^"]+)"',response.text)
            if not match: raise AssertionError('Missing CSRF token')
            return match.group(1)
        response=session.post(base+'/login',params={'next':'https://evil.test'},data={
            'username':username,'password':password,'csrf_token':token()},allow_redirects=False,timeout=5)
        assert response.status_code==302 and response.headers['Location']=='/'
        csrf=token('/')
        assert session.put(base+'/api/algorithms/1',json={'Algorithm_Name':'blocked'},timeout=5).status_code==400
        assert session.put(base+'/api/algorithms/1',json={'Algorithm_Name':'blocked'},headers={'X-CSRFToken':csrf},timeout=5).status_code==403
        assert session.get(base+'/socket.io/?EIO=4&transport=polling',headers={'Origin':'https://evil.test'},timeout=5).status_code==400
        print('PASS: live CSRF, role restriction, safe redirect and cross-origin rejection')
        active=socketio.Client(http_session=session,reconnection=False,request_timeout=5)
        received=threading.Event();disconnected=threading.Event()
        active.on('sensor_update',lambda data: received.set())
        active.on('disconnect',lambda *a: disconnected.set())
        active.connect(base,auth={'csrf_token':csrf},transports=['polling'],wait_timeout=5)
        assert active.connected
        assert received.wait(20)
        print('PASS: logged-in Socket.IO receives live MQTT telemetry')
        assert requests.get(base+'/api/ml/events',timeout=5).status_code==401
        ml=session.get(base+'/api/ml/events',params={'limit':10},timeout=5)
        status=session.get(base+'/api/ml/status',timeout=5)
        assert ml.status_code==200 and status.status_code==200
        assert status.json()['protocol_rejections'] is None and status.json()['rule_anomalies'] is None
        assert session.get(base+'/ml',timeout=5).status_code==200
        if os.environ.get('WEB_EXPECT_ML')=='1':
            assert ml.json()['items'] and any(m['status']=='available' for m in status.json()['models'])
        print('PASS: ML routes require login, separate protocol/rule/ML sources and preserve role visibility')
        history=session.get(base+'/api/telemetry/history',params={'limit':2},timeout=5)
        assert history.status_code==200 and 0<len(history.json()['items'])<=2
        assert session.get(base+'/telemetry',timeout=5).status_code==200
        assert session.get(base+'/api/telemetry/metrics',timeout=5).status_code==403
        with app.app_context():
            user=db.session.get(User,user_id); user.role='admin'; db.session.commit()
        metrics=session.get(base+'/api/telemetry/metrics',timeout=5)
        assert metrics.status_code==200
        assert metrics.json()['mongo_documents']>0 and metrics.json()['counters']['incoming']>0
        print('PASS: authorized live MongoDB history, history page and admin-only pipeline metrics')
        response=session.post(base+'/logout' ,headers={'X-CSRFToken':csrf},allow_redirects=False,timeout=5)
        assert response.status_code==302 and disconnected.wait(5)
        assert session.get(base+'/api/latest-data',timeout=5).status_code==401
        print('PASS: logout disconnects live Socket.IO and removes HTTP access')
    finally:
        for client in [active,anonymous]:
            if client.connected: client.disconnect()
        if user_id is not None:
            with app.app_context():
                user=db.session.get(User,user_id)
                if user: db.session.delete(user);db.session.commit()


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(f'Live web check failed ({type(error).__name__})')
        raise SystemExit(1) from None
