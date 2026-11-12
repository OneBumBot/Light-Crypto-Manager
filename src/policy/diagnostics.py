"""Read-only current PG evidence; readiness is deliberately separate from freshness."""
from datetime import timedelta
from sqlalchemy import select,func
from src.security_events import queue
from .models import pending,signals,states,versions,worker_status
from .rules import Rules
from .signals import utc


def snapshot(c,now,active=None):
    active=active or c.execute(select(versions).where(versions.c.active.is_(True))).mappings().first()
    version=active['version'] if active else None
    ttl=Rules.parse(active['config']).telemetry_fresh_seconds if active else None
    backlog={r.kind:dict(count=r.count,oldest_at=r.oldest) for r in c.execute(select(pending.c.kind,func.count().label('count'),func.min(pending.c.sort_at).label('oldest')).group_by(pending.c.kind))}
    count=sum(v['count'] for v in backlog.values());oldest=min((v['oldest_at'] for v in backlog.values()),default=None)
    last=c.execute(select(signals.c.created_at,signals.c.payload).where(signals.c.version==version,signals.c.event_id.like('security:%')).order_by(signals.c.created_at.desc(),signals.c.event_id).limit(1)).mappings().first() if version else None
    evidence=utc(last['payload']['occurred_at']) if last and last['payload'].get('occurred_at') else None
    rows=c.execute(select(worker_status).order_by(worker_status.c.heartbeat_at.desc()).limit(50)).mappings().all()
    workers=[r for r in rows if 0<=(now-r['heartbeat_at']).total_seconds()<=30]
    ready=any(r['status']=='ready' for r in workers)
    oldest_age=max(0,(now-oldest).total_seconds()) if oldest else None
    evidence_age=(now-evidence).total_seconds() if evidence else None
    processing_lag=max(0,(last['created_at']-evidence).total_seconds()) if last and evidence else None
    rates=c.execute(select(func.count().filter(signals.c.event_id.like('security:%')),
        func.count().filter(signals.c.source=='ml'),func.count().filter(signals.c.status=='rate_limited'),
        func.count().filter(signals.c.status=='rejected')).where(signals.c.version==version,signals.c.created_at>=now-timedelta(seconds=60))).one()
    cap=c.execute(select(queue)).mappings().first()
    return dict(active_version=version,worker_status='ready' if ready else 'unavailable' if rows else 'unknown',worker_count=len(workers),
        worker_count_source='recent heartbeat records, not a physical process census',serialization='one bounded policy transaction at a time',
        heartbeat_age_seconds=(now-rows[0]['heartbeat_at']).total_seconds() if rows else None,
        queue_pending=count,security_queue_pending=backlog.get('security',{}).get('count',0),ml_queue_pending=backlog.get('ml',{}).get('count',0),
        oldest_pending_age_seconds=oldest_age,source_lag_seconds=processing_lag,processed_evidence_age_seconds=evidence_age,last_processed_evidence_at=evidence.isoformat() if evidence else None,
        last_successful_processing_at=last['created_at'].isoformat() if last else None,
        evidence_status='unknown' if evidence_age is None else 'fresh' if ttl is not None and 0<=evidence_age<=ttl else 'stale',
        backlog_status='lagging' if oldest_age is not None and ttl is not None and oldest_age>ttl else 'pending' if count else 'idle',
        capacity=dict(cap) if cap else None,capacity_utilization=cap['retained']/cap['capacity'] if cap else None,overflow=cap['overflow'] if cap else None,
        current_worker_metrics=dict(workers[0]['metrics']) if workers and workers[0]['status']=='ready' else None,
        rates_window_seconds=60,security_events_per_second=rates[0]/60,ml_events_per_second=rates[1]/60,rate_limited_per_second=rates[2]/60,rejected_per_second=rates[3]/60,
        sql_time='lab_instrumentation_only',mode='DRY_RUN',live_control_enabled=False,checked_at=now.isoformat())
