"""Authorized status and manual requests. Web never mounts MQTT control keys."""
import os
from datetime import datetime,timezone
from flask import Blueprint,request,jsonify,abort,render_template
from flask_login import login_required,current_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from src.web.models import db
from src.telemetry import strict_json,DEVICE
from src.devices import devices as registered_devices
from src.crypto_profiles import PROFILES
from . import models as m,server
blueprint=Blueprint('control',__name__)


def serialized(row):return {k:v.isoformat() if isinstance(v,datetime) else v for k,v in row.items()}
def access():
    if not current_user.has_table_access('sensor_data'):abort(403)


@blueprint.get('/control')
@login_required
def page():
    access();return render_template('control.html')


@blueprint.get('/api/control')
@login_required
def status():
    access()
    if set(request.args)-{'device_id','limit'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
    device=request.args.get('device_id')
    try:limit=int(request.args.get('limit','50'))
    except ValueError:abort(400)
    if not 1<=limit<=200 or device is not None and not DEVICE.fullmatch(device):abort(400)
    try:
        with db.engine.connect() as c:
            q=select(m.devices).order_by(m.devices.c.device_id).limit(limit)
            if device:q=q.where(m.devices.c.device_id==device)
            rows=c.execute(q).mappings().all();ids=[r['device_id'] for r in rows]
            history=c.execute(select(m.transitions).where(m.transitions.c.device_id.in_(ids)).order_by(m.transitions.c.created_at.desc()).limit(limit)).mappings().all()
            acks=c.execute(select(m.acks).where(m.acks.c.device_id.in_(ids)).order_by(m.acks.c.received_at.desc()).limit(limit)).mappings().all()
            audit=c.execute(select(m.audit).where(m.audit.c.device_id.in_(ids)).order_by(m.audit.c.at.desc()).limit(limit)).mappings().all()
            workers=c.execute(select(m.workers).order_by(m.workers.c.heartbeat.desc()).limit(20)).mappings().all()
        # Key fingerprints are internal provisioning consistency metadata, excluded from HTTP.
        items=[{k:v for k,v in serialized(r).items() if k not in ['key_fingerprint','sequence_reserved']} for r in rows]
        return jsonify(items=items,transitions=[serialized(r) for r in history],acks=[serialized(r) for r in acks],audit=[serialized(r) for r in audit],
            workers=[dict(serialized(r),stale=(datetime.now(timezone.utc)-r['heartbeat']).total_seconds()>10) for r in workers],profiles=PROFILES,
            mode=os.environ.get('CONTROL_MODE','DISABLED'),policy_mode='DRY_RUN')
    except SQLAlchemyError:return jsonify(error='Управление временно недоступно'),503


@blueprint.post('/api/control/<device>/switch')
@login_required
def switch(device):
    if current_user.role!='admin':abort(403)
    if os.environ.get('CONTROL_MODE')!=server.MODE:return jsonify(error='Управление отключено'),409
    if not DEVICE.fullmatch(device) or request.content_length is None or request.content_length>2048:abort(400)
    try:
        body=strict_json(request.get_data())
        if type(body) is not dict or set(body)!={'profile','ttl'}:raise ValueError('Fields')
        with db.engine.begin() as c:
            if not c.scalar(select(registered_devices.c.device_id).where(registered_devices.c.device_id==device,registered_devices.c.enabled.is_(True))):abort(404)
            tid=server.request_switch(c,device,body['profile'],'admin:'+str(current_user.id),ttl=body['ttl'],mode=server.MODE)
        return jsonify(transition_id=tid,status='PREPARE_SENT',effective_changed=False),202
    except (TypeError,ValueError):return jsonify(error='Недопустимый или конфликтующий запрос переключения'),409
    except SQLAlchemyError:return jsonify(error='Запрос временно недоступен'),503
