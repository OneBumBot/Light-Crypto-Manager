"""Read-only bounded corroboration in the isolated lab; never output secrets."""

import json, os, time
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from src.runtime import database_url
from src.mongo_repository import MongoRepository


def snapshot(since):
    engine = create_engine(database_url())
    repo = MongoRepository()
    try:
        with engine.connect() as c:
            c.execute(text("SET TRANSACTION READ ONLY"))
            counts = dict(
                c.execute(
                    text("SELECT category,count(*) FROM security_observations GROUP BY category")
                ).all()
            )
            rows = c.execute(
                text(
                    "SELECT device_id,key_epoch,sequence_number FROM security_observations WHERE category='replay' AND occurred_at>=:since ORDER BY occurred_at DESC LIMIT 2000"
                ),
                {"since": datetime.fromtimestamp(since, timezone.utc)},
            ).all()
            accepted = (
                c.execute(
                    text(
                        "SELECT DISTINCT device_id FROM security_observations WHERE category='accepted' AND occurred_at>=:since"
                    ),
                    {"since": datetime.fromtimestamp(since, timezone.utc)},
                )
                .scalars()
                .all()
            )
            events = (
                c.execute(
                    text(
                        "SELECT id,category,device_id,key_epoch,sequence_number,occurred_at FROM security_observations WHERE occurred_at>=:since ORDER BY occurred_at,id LIMIT 10001"
                    ),
                    {"since": datetime.fromtimestamp(since, timezone.utc)},
                )
                .mappings()
                .all()
            )
            if len(events) > 10000:
                raise ValueError("Corroboration journal overflow")
            events = [{**dict(e), "occurred_at": e["occurred_at"].timestamp()} for e in events]
            pending = c.execute(
                text("SELECT count(*) FROM telemetry_outbox WHERE status!='delivered'")
            ).scalar_one()
        return dict(
            schema_version=2,
            security_events=events,
            at=time.time(),
            accepted_devices=accepted,
            categories=counts,
            replay_identities=[list(x) for x in rows],
            outbox_pending=pending,
            mongo_records=repo.collection.count_documents({}, maxTimeMS=2000),
            postgres="available",
            mongo="available",
            applied_configuration_check="policy stays opt-in DRY_RUN; separate integration check",
        )
    finally:
        repo.close()
        engine.dispose()


if __name__ == "__main__":
    print(json.dumps(snapshot(float(os.environ.get("RESEARCH_SINCE", "0")))))
