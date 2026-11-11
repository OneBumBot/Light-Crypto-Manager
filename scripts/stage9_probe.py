"""Real PG/Mongo stage9 setup/status. Contains no synthetic telemetry or device ACK."""
import argparse
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine,select,func,text
from src.runtime import database_url
from src.outbox import outbox,metrics
from src.device_control import models as m,server
from src.device_control.config import load
from src.policy.models import worker_status,states
from src.mongo_repository import MongoRepository


def status(engine):
    with engine.connect() as c:
        result=dict(devices=[dict(r) for r in c.execute(select(m.devices.c.device_id,m.devices.c.effective_profile,m.devices.c.effective_event,m.devices.c.sequence_reserved,m.devices.c.command_sequence)).mappings()],
            outbox=dict(c.execute(select(outbox.c.status,func.count()).group_by(outbox.c.status)).all()),
            telemetry={r.device_id:dict(accepted=r.n,max_sequence=r.seq) for r in c.execute(select(outbox.c.device_id,func.count().label('n'),func.max(outbox.c.sequence_number).label('seq')).group_by(outbox.c.device_id))},
            transitions=c.scalar(select(func.count()).select_from(m.transitions)),
            completed=c.scalar(select(func.count()).select_from(m.transitions).where(m.transitions.c.phase=='EFFECTIVE_CONFIRMED')),
            unknown=c.scalar(select(func.count()).select_from(m.transitions).where(m.transitions.c.phase.in_(['UNKNOWN_OUTCOME','RECOVERY_REQUIRED']))),
            authenticated_ack=c.scalar(select(func.count()).select_from(m.acks)),
            effective_receipts=c.scalar(select(func.count()).select_from(m.evidence)),
            policy_modes=list(c.scalars(select(worker_status.c.mode).distinct())),
            policy_applied=c.scalar(select(func.count()).select_from(states).where(states.c.applied.is_not(None))),
            counters={k:int(v) for k,v in c.execute(select(metrics.c.kind,func.sum(metrics.c.count)).group_by(metrics.c.kind))},
            migration=c.scalar(text('SELECT version_num FROM alembic_version')),trusted_detector=False,active_publishers='not_measured')
    repo=MongoRepository('relay')
    try:result['mongo_managed']=repo.collection.count_documents({'device_id':{'$in':['alpha','beta','gamma']}})
    finally:repo.close()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['setup','status','ready']);a=p.parse_args()
    engine=create_engine(database_url(),connect_args={'connect_timeout':2})
    try:
        if a.action=='setup':
            credentials=json.load(sys.stdin)
            if set(credentials)!={'admin','operator','viewer'} or any(type(v) is not str or len(v)<24 for v in credentials.values()):raise ValueError('Explicit independent private account credentials required')
            from src.web.app import app
            from src.web.models import db,Algorithm,AnomalyCause,User
            with app.app_context():
                for cls,identity,fields in [(Algorithm,1,dict(Algorithm_ID=1,Algorithm_Name='Ascon-AEAD128')),
                    (AnomalyCause,0,dict(Anomaly_Cause_ID=0,Anomaly_Cause='Sensor threshold')),
                    (AnomalyCause,1,dict(Anomaly_Cause_ID=1,Anomaly_Cause='Telemetry delay'))]:
                    old=db.session.get(cls,identity)
                    if old and any(getattr(old,k)!=v for k,v in fields.items()):raise ValueError('Setup conflict')
                    if not old:db.session.add(cls(**fields))
                for role in ['admin','operator','viewer']:
                    password=credentials[role]
                    old=User.query.filter_by(username='demo-'+role).first()
                    if old:
                        if old.role!=role or not old.check_password(password):raise ValueError('Existing account mismatch; no reset')
                    else:
                        u=User(username='demo-'+role,email=role+'@demo.invalid',role=role);u.set_password(password);db.session.add(u)
                db.session.commit()
            from scripts.provision_registry import main as provision
            provision()
            with engine.begin() as c:server.provision(c,load())
            print(json.dumps(dict(setup='committed',devices=list(load()),passwords_printed=False)));return
        if a.action=='ready':
            end=time.monotonic()+50
            while time.monotonic()<end:
                result=status(engine)
                if len(result['devices'])==3 and all(r['effective_event'] for r in result['devices']) and len(result['telemetry'])==3 and result['mongo_managed']>=3:break
                time.sleep(.3)
            else:raise AssertionError('Real telemetry readiness not observed')
        else:result=status(engine)
        assert result['policy_modes']==['DRY_RUN'] and result['policy_applied']==0
        print(json.dumps(result,indent=2))
    finally:engine.dispose()

if __name__=='__main__':main()
