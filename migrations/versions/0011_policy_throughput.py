"""Atomic source discovery, no timestamp cursor and no crypto authority changes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0011_policy_throughput'
down_revision='0010_mgm_key_usage'
branch_labels=depends_on=None


def upgrade():
    op.create_table('policy_pending',sa.Column('event_id',sa.String(160),primary_key=True),
        sa.Column('kind',sa.String(16),nullable=False),sa.Column('source_id',sa.String(36),nullable=False),
        sa.Column('sort_at',sa.DateTime(timezone=True),nullable=False),sa.Column('payload',JSONB,nullable=False),
        sa.CheckConstraint("kind IN ('security','ml')",name='ck_policy_pending_kind'))
    op.create_index('ix_policy_pending_order','policy_pending',['kind','sort_at','event_id'])
    op.create_table('policy_schedule',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('next_ml',sa.Boolean(),nullable=False,server_default='false'),sa.CheckConstraint('id=1',name='ck_policy_schedule'))
    op.execute('INSERT INTO policy_schedule(id,next_ml) VALUES(1,false)')
    op.create_index('ix_policy_signal_processed','policy_signals',['version','created_at'])
    op.add_column('policy_worker_status',sa.Column('metrics',JSONB,nullable=False,server_default='{}'))
    # Source capture never takes the policy/activation lock or reads active version.
    # Thus concurrent activation and a late source COMMIT cannot lose discovery.
    op.execute("""CREATE FUNCTION policy_enqueue_source() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='security_observations' THEN
        INSERT INTO policy_pending(event_id,kind,source_id,sort_at,payload)
          VALUES('security:'||NEW.id,'security',NEW.id,NEW.occurred_at,to_jsonb(NEW)) ON CONFLICT DO NOTHING;
      ELSIF NEW.status!='processing' THEN
        IF TG_OP='UPDATE' THEN
          IF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
        END IF;
        INSERT INTO policy_pending(event_id,kind,source_id,sort_at,payload)
          VALUES('ml:'||NEW.id||':'||NEW.status,'ml',NEW.id,NEW.available_at,to_jsonb(NEW)) ON CONFLICT DO NOTHING;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER policy_security_enqueue AFTER INSERT ON security_observations FOR EACH ROW EXECUTE FUNCTION policy_enqueue_source()')
    op.execute('CREATE TRIGGER policy_ml_enqueue AFTER INSERT OR UPDATE ON ml_anomaly_events FOR EACH ROW EXECUTE FUNCTION policy_enqueue_source()')
    op.execute("""CREATE FUNCTION policy_protect_pending() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM policy_signals s JOIN policy_versions v ON s.version=v.version AND v.active
                        WHERE s.event_id='security:'||OLD.id) THEN
        RAISE EXCEPTION 'Unread policy source retention forbidden';
      END IF;
      DELETE FROM policy_pending WHERE event_id='security:'||OLD.id;
      RETURN OLD;
    END $$""")
    op.execute('CREATE TRIGGER policy_security_retention BEFORE DELETE ON security_observations FOR EACH ROW EXECUTE FUNCTION policy_protect_pending()')
    op.execute("""INSERT INTO policy_pending(event_id,kind,source_id,sort_at,payload)
      SELECT 'security:'||j.id,'security',j.id,j.occurred_at,to_jsonb(j) FROM security_observations j
      WHERE NOT EXISTS(SELECT 1 FROM policy_signals s JOIN policy_versions v ON s.version=v.version AND v.active WHERE s.event_id='security:'||j.id)
      ON CONFLICT DO NOTHING""")
    op.execute("""INSERT INTO policy_pending(event_id,kind,source_id,sort_at,payload)
      SELECT 'ml:'||m.id||':'||m.status,'ml',m.id,m.available_at,to_jsonb(m) FROM ml_anomaly_events m WHERE m.status!='processing'
      AND NOT EXISTS(SELECT 1 FROM policy_signals s JOIN policy_versions v ON s.version=v.version AND v.active WHERE s.event_id='ml:'||m.id||':'||m.status)
      ON CONFLICT DO NOTHING""")


def downgrade():
    raise RuntimeError('Reviewed policy pending/audit preservation required')
