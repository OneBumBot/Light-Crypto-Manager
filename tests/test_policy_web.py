import pytest
from sqlalchemy import select,func
from src.policy.models import versions,audit
from src.web.models import ROLE_PERMISSIONS,UserRole
from test_history_api import login
from web_helpers import csrf_token

pytestmark=pytest.mark.postgres


def test_policy_auth_roles_csrf_activation_validation(postgres_db,monkeypatch):
    web=postgres_db
    from flask.testing import FlaskClient
    class FreshContextClient(FlaskClient):
        def open(self,*args,**kwargs):
            # The DB fixture holds an outer app context. Real HTTP requests get fresh g.
            with self.application.app_context():return super().open(*args,**kwargs)
    monkeypatch.setattr(web.app,'test_client_class',FreshContextClient)
    anon=web.app.test_client()
    assert anon.get('/api/policy').status_code==401
    viewer=login(web);operator=login(web,'operator');admin=login(web,'admin')
    assert viewer.get('/policy').status_code==200
    assert viewer.get('/api/policy').json['mode']=='DRY_RUN'
    for client in [viewer,operator]:
        assert client.post('/api/policy/versions',json={'version':'no','rules':{},'activate':True},
                           headers={'X-CSRFToken':csrf_token(client,'/')}).status_code==403
        assert client.get('/api/policy/metrics').status_code==403
    body={'version':'web-v1','rules':{},'activate':True}
    assert admin.post('/api/policy/versions',json=body).status_code==400
    assert admin.post('/api/policy/versions',json=body,headers={'X-CSRFToken':csrf_token(viewer,'/')}).status_code==400
    response=admin.post('/api/policy/versions',json=body,headers={'X-CSRFToken':csrf_token(admin,'/')})
    assert response.status_code==200 and response.json['status']=='activated'
    with web.db.engine.connect() as c:
        assert c.scalar(select(versions.c.version).where(versions.c.active.is_(True)))=='web-v1'
        assert c.scalar(select(func.count()).select_from(audit))==1
    for rules in [{'expression':'__import__("os")'},{'minimum_profile':'none'},{'watch_observations':False}]:
        assert admin.post('/api/policy/versions',json=dict(body,version='bad',rules=rules),
            headers={'X-CSRFToken':csrf_token(admin,'/')}).status_code==400
    assert admin.get('/api/policy/metrics').status_code==200
    for path in ['/api/policy','/api/policy/signals','/api/policy/decisions','/api/policy/transitions','/api/policy/intents']:
        assert viewer.get(path+'?limit=201').status_code==400
        assert viewer.get(path+'?device_id=$where').status_code==400
        assert viewer.get(path).status_code==200
    monkeypatch.setitem(ROLE_PERMISSIONS[UserRole.VIEWER],'tables',[])
    assert viewer.get('/api/policy').status_code==403
    assert viewer.get('/policy').status_code==403
