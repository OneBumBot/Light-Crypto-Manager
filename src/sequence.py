"""Persist allocation before publish; gaps are allowed, reuse is not."""
import os
from pathlib import Path
import sqlite3

from src.telemetry import MAX_SEQUENCE, positive


def next_sequence(path,device,epoch):
    positive(epoch,2**31-1)
    path=Path(path)
    if not path.parent.is_dir(): raise ValueError('Sequence directory must exist')
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        fd=None
    if fd is not None: os.close(fd)
    with sqlite3.connect(path,timeout=15) as connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('CREATE TABLE IF NOT EXISTS counters (device TEXT, epoch INTEGER, value INTEGER, PRIMARY KEY(device,epoch))')
        row=connection.execute('SELECT value FROM counters WHERE device=? AND epoch=?',(device,epoch)).fetchone()
        value=(row[0] if row else 0)+1
        if value>MAX_SEQUENCE: raise ValueError('Sequence exhausted; provision a new key epoch')
        connection.execute('INSERT INTO counters VALUES (?,?,?) ON CONFLICT(device,epoch) DO UPDATE SET value=excluded.value',(device,epoch,value))
    return value
