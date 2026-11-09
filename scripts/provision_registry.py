"""Explicit idempotent PG provisioning from a private registry, without key copies."""
from datetime import datetime
from sqlalchemy import create_engine, text
from src.runtime import database_url
from src.telemetry import load_registry


def main():
    registry=load_registry()
    engine=create_engine(database_url())
    try:
        with engine.begin() as c:
            for name,entry in registry.items():
                existing=c.execute(text('SELECT "Tag_Name" FROM "Tag_Journal" WHERE "Tag_ID"=:id'),{'id':entry['database_device_id']}).first()
                if existing and existing[0]!=name[:25]+'-main': raise RuntimeError('Provisioning identity conflict')
                if not existing:
                    c.execute(text('INSERT INTO "Tag_Journal" ("Tag_ID","Tag_Name","Creation_Date") VALUES (:id,:name,:date)'),dict(id=entry['database_device_id'],name=name[:25]+'-main',date=datetime(2026,1,1)))
                    c.execute(text('INSERT INTO "Device_Configuration" ("Device_ID","Tag_ID","Algorithm_ID","Configuration_Update_Date") VALUES (:id,:id,1,:date)'),dict(id=entry['database_device_id'],date=datetime(2026,1,1)))
        print('Device configurations provisioned; keys remain outside PostgreSQL')
    finally: engine.dispose()

if __name__=='__main__': main()
