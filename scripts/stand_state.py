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
            pending = c.execute(
                text("SELECT count(*) FROM telemetry_outbox WHERE status!='delivered'")
            ).scalar_one()
        return dict(
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
