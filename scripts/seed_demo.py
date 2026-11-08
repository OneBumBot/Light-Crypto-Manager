"""Explicit opt-in fixture for the demo profile; never overwrite existing rows."""

from datetime import datetime

from src.web.app import app
from src.web.models import Algorithm, AnomalyCause, DeviceConfiguration, TagJournal, db


def seed_demo():
    objects = [
        (Algorithm, 1, {'Algorithm_ID': 1, 'Algorithm_Name': 'Ascon-AEAD128'}),
        (AnomalyCause, 0, {'Anomaly_Cause_ID': 0, 'Anomaly_Cause': 'Sensor threshold'}),
        (AnomalyCause, 1, {'Anomaly_Cause_ID': 1, 'Anomaly_Cause': 'Telemetry delay'}),
        (TagJournal, 1, {'Tag_ID': 1, 'Tag_Name': 'raspb1-demo',
                         'Creation_Date': datetime(2026, 1, 1)}),
        (DeviceConfiguration, (1, datetime(2026, 1, 1)), {
            'Device_ID': 1, 'Configuration_Update_Date': datetime(2026, 1, 1),
            'Algorithm_ID': 1, 'Tag_ID': 1,
        }),
    ]
    try:
        for model, identity, fields in objects:
            existing = db.session.get(model, identity)
            if existing:
                if any(getattr(existing, name) != value for name, value in fields.items()):
                    raise ValueError('Demo IDs conflict with existing data; no changes committed')
            else:
                db.session.add(model(**fields))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


if __name__ == '__main__':
    with app.app_context():
        seed_demo()
    print('Demo device ready (idempotent; existing data preserved)')
