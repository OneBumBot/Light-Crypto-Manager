"""Bounded read-only integration. Authority stays in ingestion/control/policy tables."""
import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.exc import SQLAlchemyError
from pymongo.errors import PyMongoError
from src.web.models import db
from src.devices import devices
from src.outbox import outbox
from src.security_events import journal
from src.device_control import models as control
from src.policy import models as policy
from src.ml_storage import models as ml_models, events as ml_events
from src.system_status import heartbeats
from src.crypto_profiles import PROFILES, BY_ALGORITHM
from src.telemetry import DEVICE
from src.policy.rules import Rules
from src.policy.signals import utc

blueprint = Blueprint('monitoring', __name__)
TELEMETRY_TTL = 15


def age(now, timestamp):
    return max(0, (now-timestamp).total_seconds()) if timestamp else None


def telemetry_state(enabled, timestamp, now):
    if not enabled: return 'disabled'
    if timestamp is None: return 'unknown'
    return 'recent' if 0 <= (now-timestamp).total_seconds() <= TELEMETRY_TTL else 'stale'


def worker(row, now, timestamp, ttl, source):
    checked = row[timestamp] if row else None
    fresh = checked is not None and 0 <= (now-checked).total_seconds() <= ttl
    ready = row is not None and row.get('ready', row.get('status') == 'ready')
    return dict(status=('ready' if ready else 'unavailable') if fresh else ('stale' if row else 'unknown'),
        checked_at=checked, age_seconds=age(now, checked), ttl_seconds=ttl, source=source)


def access():
    if not current_user.has_table_access('sensor_data'): abort(403)


def clean(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {k:clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    return value


def latest(table, ids, order, columns=None):
    return select(*(columns or list(table.c))).where(table.c.device_id.in_(ids)).distinct(table.c.device_id).order_by(table.c.device_id, order.desc())


def snapshot(connection, device=None, limit=50, offset=0):
    c = connection
    now = c.scalar(select(func.clock_timestamp()))
    latest_telemetry = select(outbox.c.device_id, outbox.c.id, outbox.c.created_at,
        outbox.c.payload, outbox.c.key_epoch, outbox.c.sequence_number).join(devices,
        (devices.c.device_id==outbox.c.device_id) & (devices.c.key_epoch==outbox.c.key_epoch))\
        .distinct(outbox.c.device_id).order_by(outbox.c.device_id, outbox.c.created_at.desc()).subquery()
    summary_row = c.execute(select(func.count().label('provisioned'),
        func.count().filter(devices.c.enabled.is_(True), latest_telemetry.c.created_at >= now-timedelta(seconds=TELEMETRY_TTL), latest_telemetry.c.created_at<=now).label('recent'),
        func.count().filter(devices.c.enabled.is_(False)).label('disabled'))
        .select_from(devices.outerjoin(latest_telemetry, devices.c.device_id==latest_telemetry.c.device_id))).mappings().one()
    summary = dict(summary_row)
    summary['without_recent'] = summary['provisioned']-summary['recent']-summary['disabled']
    summary['active_transitions'] = c.scalar(select(func.count()).select_from(control.transitions).where(control.transitions.c.phase.in_(['PREPARED_SERVER','PREPARE_SENT','ACTIVATION_SENT','DEVICE_APPLIED']),control.transitions.c.deadline>now))
    summary['uncertain_transitions'] = c.scalar(select(func.count()).select_from(control.transitions).where(or_(control.transitions.c.phase.in_(['UNKNOWN_OUTCOME','RECOVERY_REQUIRED']),and_(control.transitions.c.phase.in_(['PREPARED_SERVER','PREPARE_SENT','ACTIVATION_SENT','DEVICE_APPLIED']),control.transitions.c.deadline<=now))))
    q = select(devices).order_by(devices.c.device_id).limit(limit).offset(offset)
    if device: q=q.where(devices.c.device_id==device)
    inventory = [dict(r) for r in c.execute(q).mappings()]
    if device and not inventory: abort(404)
    ids = [r['device_id'] for r in inventory]
    def rows(q): return [dict(r) for r in c.execute(q).mappings()]
    def indexed(q): return {r['device_id']:r for r in rows(q)}
    managed = indexed(select(control.devices).where(control.devices.c.device_id.in_(ids)))
    telemetry = indexed(select(latest_telemetry).where(latest_telemetry.c.device_id.in_(ids)))
    security = indexed(latest(journal, ids, journal.c.occurred_at).where(journal.c.category!='accepted'))
    active = c.execute(select(policy.versions).where(policy.versions.c.active.is_(True))).mappings().first()
    active_rules=Rules.parse(active['config']) if active else None
    states = indexed(select(policy.states).where(policy.states.c.device_id.in_(ids), policy.states.c.version==active['version'])) if active else {}
    rec = c.execute(select(heartbeats).where(heartbeats.c.component=='receiver').order_by(heartbeats.c.checked_at.desc()).limit(1)).mappings().first()
    cw = c.execute(select(control.workers).order_by(control.workers.c.heartbeat.desc()).limit(1)).mappings().first()
    pw = c.execute(select(policy.worker_status).order_by(policy.worker_status.c.heartbeat_at.desc()).limit(1)).mappings().first()
    components = dict(postgres=dict(status='available',checked_at=now,source='PG snapshot'),
        receiver=worker(rec,now,'checked_at',10,'receiver SUBACK/connection diagnostic heartbeat'),
        control=worker(cw,now,'heartbeat',10,'live_control_workers'),
        policy=worker(pw,now,'heartbeat_at',30,'policy_worker_status'))
    models = rows(select(ml_models.c.model_id,ml_models.c.model_version,ml_models.c.mode,ml_models.c.score_semantics,ml_models.c.status,ml_models.c.heartbeat_at).order_by(ml_models.c.heartbeat_at.desc()).limit(20))
    for model in models:
        model['trusted_detector']=False
        model['stale']=age(now,model['heartbeat_at'])>30
    components['ml']=dict(status='disabled' if os.environ.get('ML_MONITOR_MODE')=='DISABLED' else ('unknown' if not models else ('research' if any(m['status']=='available' and not m['stale'] for m in models) else 'unavailable')), models=models,
        trusted_detector=False,source='ml_models; отсутствие модели не означает норму')
    pending_ids = [r['pending_transition'] for r in managed.values() if r['pending_transition']]
    pending = {r['id']:r for r in rows(select(control.transitions).where(control.transitions.c.id.in_(pending_ids)))}
    receipt_ids = [r['effective_event'] for r in managed.values() if r['effective_event']]
    receipts = {r['event_id']:r for r in rows(select(control.evidence).where(control.evidence.c.event_id.in_(receipt_ids)))}
    result=[]
    for item in inventory:
        identity=item['device_id']; state=managed.get(identity,{}); event=telemetry.get(identity)
        receipt=receipts.get(state.get('effective_event'))
        verified=bool(receipt and receipt['device_id']==identity and receipt['key_epoch']==item['key_epoch'] and receipt['profile']==state.get('effective_profile'))
        p=states.get(identity)
        if p:
            p={k:p[k] for k in ['version','observed_risk','recommended','state','updated_at']}
            p['evidence_at']=p['state'].get('last_event_at')
            evidence=utc(p['evidence_at']) if p['evidence_at'] else None
            p['evidence_age_seconds']=age(now,evidence)
            p['evidence_ttl_seconds']=active_rules.telemetry_fresh_seconds
            p['evidence_stale']=evidence is None or not 0<=(now-evidence).total_seconds()<=p['evidence_ttl_seconds']
            p['stale']=age(now,p['updated_at'])>30 or components['policy']['status']!='ready' or p['evidence_stale']
            p['mode']='DRY_RUN';p['applied']=False
        transition=pending.get(state.get('pending_transition'))
        if transition:
            transition=dict(transition,expired=transition['deadline']<=now)
        result.append(dict(device_id=identity,enabled=item['enabled'],key_epoch=item['key_epoch'],
            status=telemetry_state(item['enabled'],event['created_at'] if event else None,now),
            telemetry_age_seconds=age(now,event['created_at']) if event else None,
            telemetry=(dict(event['payload'],event_id=event['id'],received_at=event['created_at'],sequence_number=event['sequence_number']) if event else None),
            capabilities=state.get('capabilities',[]),effective_profile=state.get('effective_profile') if verified else None,
            effective_evidence=({k:receipt[k] for k in ['event_id','profile','key_epoch','sequence_number','accepted_at']} if verified else None),
            reported_profile=state.get('reported_profile'),pending=transition,policy=p,last_security=security.get(identity)))
    backlog = dict(c.execute(select(outbox.c.status,func.count()).group_by(outbox.c.status)).all())
    anonymous = rows(select(journal.c.id,journal.c.category,journal.c.occurred_at).where(journal.c.category=='rejected',journal.c.device_id.is_(None)).order_by(journal.c.occurred_at.desc()).limit(10))
    output=dict(checked_at=now,telemetry_ttl_seconds=TELEMETRY_TTL,summary=summary,components=components,
        items=result,limit=limit,offset=offset,outbox=backlog,anonymous_rejections=anonymous,
        profiles=PROFILES,control_mode=os.environ.get('CONTROL_MODE','DISABLED'),policy_mode='DRY_RUN',trusted_detector=False)
    if device:
        # Detail bounded per device; sensitive body/wire/MAC/fingerprints are never selected.
        output['security']=rows(select(journal).where(journal.c.device_id==device,journal.c.category!='accepted').order_by(journal.c.occurred_at.desc()).limit(30))
        output['transitions']=rows(select(control.transitions).where(control.transitions.c.device_id==device).order_by(control.transitions.c.created_at.desc()).limit(20))
        output['commands']=rows(select(*[control.commands.c[k] for k in ['id','transition_id','device_id','sequence','phase','status','attempts','expires_at']]).where(control.commands.c.device_id==device).order_by(control.commands.c.sequence.desc()).limit(40))
        ack_rows=rows(select(control.acks).where(control.acks.c.device_id==device).order_by(control.acks.c.received_at.desc()).limit(40))
        output['acks']=[dict(id=r['id'],command_id=r['command_id'],device_id=r['device_id'],received_at=r['received_at'],
            phase=r['body']['data']['phase'],result=r['body']['data']['result']) for r in ack_rows]
        output['audit']=rows(select(control.audit.c.id,control.audit.c.device_id,control.audit.c.transition_id,control.audit.c.action,control.audit.c.at).where(control.audit.c.device_id==device).order_by(control.audit.c.at.desc()).limit(60))
        output['decisions']=rows(select(policy.decisions).where(policy.decisions.c.device_id==device,policy.decisions.c.version==active['version']).order_by(policy.decisions.c.created_at.desc()).limit(10)) if active else []
        output['signals']=rows(select(policy.signals).where(policy.signals.c.device_id==device,policy.signals.c.version==active['version']).order_by(policy.signals.c.created_at.desc()).limit(10)) if active else []
        output['ml_events']=rows(select(*[ml_events.c[k] for k in ['device_id','model_id','model_version','evaluated_at','score','threshold','status']]).where(ml_events.c.device_id==device).order_by(ml_events.c.evaluated_at.desc().nullslast()).limit(10))
    return clean(output)


@blueprint.get('/monitoring')
@blueprint.get('/devices/<device>')
@login_required
def page(device=None):
    access()
    if device and not DEVICE.fullmatch(device): abort(404)
    return render_template('monitoring.html',device=device)


@blueprint.get('/api/monitoring')
@blueprint.get('/api/monitoring/<device>')
@login_required
def api(device=None):
    access()
    if device and not DEVICE.fullmatch(device): abort(404)
    if set(request.args)-{'limit','offset'} or any(len(request.args.getlist(k))!=1 for k in request.args): abort(400)
    try:
        limit=int(request.args.get('limit',50));offset=int(request.args.get('offset',0))
        if not 1<=limit<=100 or not 0<=offset<=10000: abort(400)
    except ValueError: abort(400)
    try:
        with db.engine.connect() as c:
            with c.begin():
                c.execute(text('SET LOCAL statement_timeout = 2000'))
                c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
                output=snapshot(c,device,limit,offset)
    except SQLAlchemyError:
        return jsonify(error='PostgreSQL недоступна. Актуальное состояние неизвестно.',components={'postgres':{'status':'unavailable'}}),503
    # Independent storage probe. It cannot invalidate PG admission/receiver facts.
    try:
        from src.web.app import history_repository
        history_repository().collection.find_one({}, {'_id':1}, max_time_ms=1500)
        output['components']['mongo']=dict(status='available',checked_at=datetime.now(timezone.utc).isoformat(),source='Mongo bounded authenticated read')
    except (PyMongoError, OSError, ValueError, KeyError):
        output['components']['mongo']=dict(status='unavailable',checked_at=datetime.now(timezone.utc).isoformat(),source='Mongo bounded authenticated read')
    return jsonify(output)
