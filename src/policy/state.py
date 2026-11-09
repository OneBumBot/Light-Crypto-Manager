"""Short serialized per-device decisions, atomic audit and immutable policy versions."""
from datetime import timedelta
import hashlib
import json
import re
import time
import uuid
from sqlalchemy import select,update,func,text,delete
from sqlalchemy.dialects.postgresql import insert
from .models import versions,states,signals,decisions,transitions,intents,audit,command_counters
from .engine import State,evaluate,LEVEL
from .rules import Rules
from .profiles import ASCON,IMPLEMENTED
from .control_contract import Command
from .signals import utc


def install(connection,version,config,now,actor='bootstrap',activate=False):
    if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',version):raise ValueError('Invalid policy version')
    rules=Rules.parse(config)
    # Runtime policies cannot lower the minimum or select simulation-only profiles.
    if rules.minimum_profile!=ASCON:raise ValueError('Unsupported minimum protection')
    payload=rules.payload();digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    connection.execute(text('SELECT pg_advisory_xact_lock(734819207)'))
    old=connection.execute(select(versions).where(versions.c.version==version)).mappings().first()
    if old and old['sha256']!=digest:raise ValueError('Policy version is immutable')
    if not old:connection.execute(versions.insert().values(version=version,config=payload,sha256=digest,active=False,created_at=now))
    if activate:
        connection.execute(update(versions).where(versions.c.active.is_(True)).values(active=False))
        connection.execute(update(versions).where(versions.c.version==version).values(active=True))
        connection.execute(audit.insert().values(id=str(uuid.uuid4()),actor=actor,action='activate',version=version,at=now))
    return rules


def process(connection,signal,version,now,*,before_commit=None):
    signal.validate();now=utc(now);start=time.perf_counter()
    if signal.binding=='simulation' or signal.trust=='simulation':raise ValueError('Simulation signals forbidden in runtime persistence')
    row=connection.execute(select(versions).where(versions.c.version==version)).mappings().one()
    rules=Rules.parse(row['config'])
    # Never derive trusted identity from raw MQTT data here. Only internal adapters.
    if signal.device_id:
        previous=connection.execute(select(states).where(states.c.device_id==signal.device_id)
            .order_by(states.c.updated_at.desc()).limit(1)).mappings().first()
        initial=State(**previous['state']) if previous else State()
        initial.stable_since=None;initial.healthy_count=0;initial.healthy_evidence=[]
        connection.execute(insert(states).values(device_id=signal.device_id,version=version,state=initial.payload(),
            observed_risk=initial.risk,updated_at=now).on_conflict_do_nothing())
        state_row=connection.execute(select(states).where(states.c.device_id==signal.device_id,states.c.version==version)
            .with_for_update()).mappings().one()
    else:state_row=None
    inserted=connection.execute(insert(signals).values(event_id=signal.event_id,version=version,device_id=signal.device_id,
        source=signal.source,payload=signal.payload(),status='processing',created_at=now).on_conflict_do_nothing()
        .returning(signals.c.event_id)).first()
    if inserted is None:return None
    if state_row is None:
        connection.execute(update(signals).where(signals.c.event_id==signal.event_id,signals.c.version==version).values(status='unattributed'))
        return None
    state=State(**state_row['state']) if state_row else State()
    if state_row and previous and previous['version']!=version and previous['updated_at']>state_row['updated_at']:
        other=State(**previous['state'])
        if LEVEL[other.guard]>LEVEL[state.guard]:
            state=other;state.stable_since=None;state.healthy_count=0;state.healthy_evidence=[]
    start=time.perf_counter()
    new,result=evaluate(state,signal,rules,now)
    compute_ms=(time.perf_counter()-start)*1000
    result['policy_version']=version
    decision_id=str(uuid.uuid4())
    if not result['emit_decision']:
        connection.execute(update(signals).where(signals.c.event_id==signal.event_id,signals.c.version==version).values(status='rate_limited'))
        if state_row:
            connection.execute(update(states).where(states.c.device_id==signal.device_id,states.c.version==version)
                .values(state=new.payload(),updated_at=now,revision=states.c.revision+1))
        return dict(id=None,**result)
    connection.execute(decisions.insert().values(id=decision_id,event_id=signal.event_id,version=version,device_id=signal.device_id,
        result=result,created_at=now,compute_ms=compute_ms,
        source_lag_seconds=max(0,(now-utc(signal.occurred_at)).total_seconds())))
    connection.execute(update(signals).where(signals.c.event_id==signal.event_id,signals.c.version==version).values(status=result['diagnostic']))
    if state_row:
        request=state_row['requested']
        # Intents are proposals only, rate limited by a new transition and a changed recommendation.
        if result['transitioned'] and result['recommended_protection']['profile_id']!=state_row['configured_profile']:
            profile=result['recommended_protection']['profile_id']
            if request is None or request.get('requested_profile')!=profile:
                connection.execute(insert(command_counters).values(device_id=signal.device_id).on_conflict_do_nothing())
                counter=connection.execute(update(command_counters).where(command_counters.c.device_id==signal.device_id)
                    .values(last_sequence=command_counters.c.last_sequence+1).returning(command_counters)).mappings().one()
                intent_id=str(uuid.uuid4());command=Command(intent_id,signal.device_id,'set_profile',profile,version,
                    now.isoformat(),(now+timedelta(seconds=60)).isoformat(),counter['last_sequence'],counter['command_epoch'],
                    str(uuid.uuid4()),decision_id,status='unsupported' if profile not in IMPLEMENTED else 'proposed').payload()
                connection.execute(intents.insert().values(id=intent_id,decision_id=decision_id,device_id=signal.device_id,
                    command=command,status=command['status'],created_at=now));request=command
        connection.execute(update(states).where(states.c.device_id==signal.device_id,states.c.version==version)
            .values(state=new.payload(),observed_risk=new.risk,recommended=result['recommended_protection'],requested=request,
                    updated_at=now,revision=states.c.revision+1))
        if result['transitioned']:
            connection.execute(transitions.insert().values(id=str(uuid.uuid4()),decision_id=decision_id,device_id=signal.device_id,
                version=version,from_state=result['current_state'],to_state=new.risk,at=now))
    if before_commit:before_commit()
    return dict(id=decision_id,**result)


def prune(connection,days,now):
    """Explicit bounded audit retention. Never touches replay/ML/Mongo."""
    if type(days) is not int or days<1:raise ValueError('Explicit positive retention required')
    cutoff=utc(now)-timedelta(days=days)
    rows=connection.execute(select(decisions.c.id,decisions.c.event_id,decisions.c.version)
        .where(decisions.c.created_at<cutoff).order_by(decisions.c.created_at).limit(1000).with_for_update(skip_locked=True)).all()
    ids=[r.id for r in rows]
    if not ids:return 0
    connection.execute(delete(intents).where(intents.c.decision_id.in_(ids),intents.c.status.in_(['expired','failed','simulated','unsupported'])))
    # Proposals are not deleted silently, even when old.
    retained=set(connection.scalars(select(intents.c.decision_id).where(intents.c.decision_id.in_(ids))))
    ids=[i for i in ids if i not in retained]
    connection.execute(delete(transitions).where(transitions.c.decision_id.in_(ids)))
    connection.execute(delete(decisions).where(decisions.c.id.in_(ids)))
    # Keep signal identity tombstones to prevent replay after retention.
    for row in rows:
        if row.id in ids:
            connection.execute(update(signals).where(signals.c.event_id==row.event_id,signals.c.version==row.version)
                .values(payload={'retained_identity':True}))
    return len(ids)
