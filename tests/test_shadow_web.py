import json,time
import pytest
from src.web.models import User
from src.shadow_ids.journal import Journal
from web_helpers import login
pytestmark=pytest.mark.postgres
@pytest.fixture
def shadow_web(postgres_db,tmp_path,monkeypatch):
 web=postgres_db
 for role in ['admin','operator','viewer']:
  u=User(username='shadow-'+role,email=role+'-shadow@test.local',role=role);u.set_password('public-test-password');web.db.session.add(u)
 web.db.session.commit();path=tmp_path/'shadow.db';journal=Journal(path);now=time.time();journal.status('capture',dict(heartbeat=now,last_packet=now,status='CAPTURING',queue_overflow=2));journal.status('worker',dict(heartbeat=now,last_inference=now,status='READY'));journal.close();monkeypatch.setenv('SHADOW_JOURNAL',str(path));return web,path
@pytest.mark.parametrize('role',['admin','operator','viewer'])
def test_shadow_read_only_authorized_roles(shadow_web,role):
 web,path=shadow_web
 with web.app.test_client() as c:
  login(c,'shadow-'+role);r=c.get('/api/research/shadow-ids');assert r.status_code==200 and r.json['mode']=='SHADOW_ONLY' and r.json['trusted_detector'] is False and r.json['capture']['queue_overflow']==2;assert r.headers['Cache-Control']=='no-store';assert c.get('/research/shadow-ids').status_code==200;assert c.post('/api/research/shadow-ids',json={}).status_code in [400,405]
@pytest.mark.parametrize('query',['?limit=101','?limit=0','?offset=-1','?offset=50001','?limit=true','?limit=[]'])
def test_shadow_pagination_bounds(shadow_web,query):
 web,_=shadow_web
 with web.app.test_client() as c:
  login(c,'shadow-viewer');assert c.get('/api/research/shadow-ids'+query).status_code==400

def test_shadow_requires_login_and_same_origin(shadow_web):
 web,_=shadow_web
 with web.app.test_client() as c:
  assert c.get('/api/research/shadow-ids').status_code in [302,401];login(c,'shadow-viewer');assert c.get('/api/research/shadow-ids',headers={'Origin':'https://outside.invalid'}).status_code==403

def test_shadow_unavailable_clears_current_rows(shadow_web,monkeypatch):
 web,path=shadow_web;monkeypatch.setenv('SHADOW_JOURNAL',str(path.parent/'missing.db'))
 with web.app.test_client() as c:
  login(c,'shadow-viewer');r=c.get('/api/research/shadow-ids');assert r.status_code==503 and r.json['results']==[] and r.json['available'] is False
