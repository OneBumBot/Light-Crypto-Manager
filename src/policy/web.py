"""Authorized policy views and CSRF-protected administrative version activation."""
from datetime import datetime,timezone
from flask import Blueprint,request,jsonify,abort,render_template
from flask_login import login_required,current_user
from sqlalchemy import select,func,exists,and_
from sqlalchemy.exc import SQLAlchemyError
from src.web.models import db
from src.telemetry import DEVICE
from src.security_events import journal,queue
from .models import versions,states,signals,decisions,transitions,intents,worker_status
from .profiles import registry
from .state import install

blueprint=Blueprint('policy',__name__)


def read_access():
    if not current_user.has_table_access('sensor_data'):abort(403)


def params():
    if set(request.args)-{'device_id','limit','offset'} or any(len(request.args.getlist(k))!=1 for k in request.args):abort(400)
    try:
        limit=int(request.args.get('limit','50'));offset=int(request.args.get('offset','0'));device=request.args.get('device_id')
        if not 1<=limit<=200 or not 0<=offset<=10000 or (device is not None and not DEVICE.fullmatch(device)):raise ValueError()
    except (ValueError,TypeError):abort(400)
    return limit,offset,device


def serialize(row):
    return {k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in row.items()}


@blueprint.get('/policy')
@login_required
def page():
    read_access();return render_template('policy.html')


@blueprint.get('/api/policy')
@login_required
def overview():
    read_access();limit,offset,device=params()
    try:
        with db.engine.connect() as c:
            active=c.execute(select(versions).where(versions.c.active.is_(True))).mappings().first()
            query=select(states).order_by(states.c.updated_at.desc(),states.c.device_id).limit(limit).offset(offset)
            if active:query=query.where(states.c.version==active['version'])
            if device:query=query.where(states.c.device_id==device)
            rows=c.execute(query).mappings().all()
            workers=c.execute(select(worker_status).order_by(worker_status.c.heartbeat_at.desc()).limit(50)).mappings().all()
            ver=c.execute(select(versions).order_by(versions.c.created_at.desc()).limit(50)).mappings().all()
        now=datetime.now(timezone.utc)
        return jsonify(items=[serialize(r) for r in rows],versions=[serialize(r) for r in ver],active_version=active['version'] if active else None,
            workers=[dict(serialize(w),stale=(now-w['heartbeat_at']).total_seconds()>30) for w in workers],profiles=registry(),
            mode='DRY_RUN',live_control_enabled=False,interpretation='Configured profile is not an authenticated device acknowledgement',limit=limit,offset=offset)
    except SQLAlchemyError:return jsonify(error='Политика временно недоступна'),503


@blueprint.get('/api/policy/<kind>')
@login_required
def history(kind):
    read_access();limit,offset,device=params()
    tables={'decisions':decisions,'signals':signals,'transitions':transitions,'intents':intents}
    if kind not in tables:abort(404)
    table=tables[kind];order=table.c.at if kind=='transitions' else table.c.created_at
    query=select(table).order_by(order.desc()).limit(limit).offset(offset)
    if device:query=query.where(table.c.device_id==device)
    try:
        with db.engine.connect() as c:rows=c.execute(query).mappings().all()
        return jsonify(items=[serialize(r) for r in rows],limit=limit,offset=offset)
    except SQLAlchemyError:return jsonify(error='История политики временно недоступна'),503


@blueprint.post('/api/policy/versions')
@login_required
def policy_version():
    if current_user.role!='admin':abort(403)
    body=request.get_json(silent=True)
    if type(body) is not dict or set(body)!={'version','rules','activate'} or type(body['activate']) is not bool:abort(400)
    try:
        with db.engine.begin() as c:install(c,body['version'],body['rules'],c.scalar(select(func.clock_timestamp())),
            actor='admin:'+str(current_user.id),activate=body['activate'])
        return jsonify(status='activated' if body['activate'] else 'created',mode='DRY_RUN')
    except (ValueError,TypeError):return jsonify(error='Некорректная или несовместимая версия политики'),400
    except SQLAlchemyError:return jsonify(error='Изменение политики временно недоступно'),503


@blueprint.get('/api/policy/metrics')
@login_required
def metrics():
    if current_user.role!='admin':abort(403)
    try:
        with db.engine.connect() as c:
            active=c.scalar(select(versions.c.version).where(versions.c.active.is_(True)))
            filter_=decisions.c.version==active
            timing=c.execute(select(func.avg(decisions.c.compute_ms),func.percentile_cont(0.95).within_group(decisions.c.compute_ms),
                func.avg(decisions.c.source_lag_seconds)).where(filter_)).one()
            consumed=exists(select(1).where(signals.c.version==active,signals.c.event_id=='security:'+journal.c.id))
            backlog=c.scalar(select(func.count()).select_from(journal).where(~consumed))
            state=c.execute(select(queue)).mappings().first()
            result=dict(processed=dict(c.execute(select(signals.c.status,func.count()).where(signals.c.version==active).group_by(signals.c.status)).all()),
                decisions=c.scalar(select(func.count()).select_from(decisions).where(filter_)),
                transitions=c.scalar(select(func.count()).select_from(transitions).where(transitions.c.version==active)),
                suppressed=c.scalar(select(func.count()).select_from(decisions).where(filter_,decisions.c.result['suppressed'].as_boolean().is_(True))),
                unsupported=c.scalar(select(func.count()).select_from(decisions).where(filter_,decisions.c.result['recommended_protection']['status'].astext=='unsupported_profile')),
                intentions=dict(c.execute(select(intents.c.status,func.count()).group_by(intents.c.status)).all()),
                risk_counts=dict(c.execute(select(states.c.observed_risk,func.count()).where(states.c.version==active).group_by(states.c.observed_risk)).all()),
                mean_compute_ms=timing[0],p95_compute_ms=timing[1],mean_source_lag_seconds=timing[2],
                security_queue_pending=backlog,security_queue=dict(state) if state else None,
                mode='DRY_RUN',switching_latency=None)
        return jsonify(result)
    except SQLAlchemyError:return jsonify(error='Метрики политики временно недоступны'),503
