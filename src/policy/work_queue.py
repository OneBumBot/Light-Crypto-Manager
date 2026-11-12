"""Durable global discovery; completion remains policy_signals(event_id,version)."""
from sqlalchemy import text


def seed(c,version):
    # Only on activation/installation, never the per-event processing path.
    c.execute(text("""INSERT INTO policy_pending(event_id,kind,source_id,sort_at,payload)
      SELECT 'security:'||j.id,'security',j.id,j.occurred_at,to_jsonb(j) FROM security_observations j
      WHERE NOT EXISTS(SELECT 1 FROM policy_signals s WHERE s.version=:version AND s.event_id='security:'||j.id)
      ON CONFLICT DO NOTHING"""),dict(version=version))
    c.execute(text("""INSERT INTO policy_pending(event_id,kind,source_id,sort_at,payload)
      SELECT 'ml:'||m.id||':'||m.status,'ml',m.id,m.available_at,to_jsonb(m) FROM ml_anomaly_events m WHERE m.status!='processing'
      AND NOT EXISTS(SELECT 1 FROM policy_signals s WHERE s.version=:version AND s.event_id='ml:'||m.id||':'||m.status)
      ON CONFLICT DO NOTHING"""),dict(version=version))
