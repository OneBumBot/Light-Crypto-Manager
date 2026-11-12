"""Device durable profile and command replay ledger. No nonce leases on disk."""
import sqlite3,os,fcntl,hashlib
from pathlib import Path
from contextlib import contextmanager
from src.telemetry import canonical,strict_json
from src.crypto_profiles import ASCON,PROFILES
from .protocol import message


class DeviceState:
    def __init__(self,path,device,epoch,*,initialize=False,strict_authority=False):
        self.path=Path(path);self.device=device;self.epoch=epoch;self.strict_authority=strict_authority
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.lock=open(str(self.path)+'.lock','a+b');os.chmod(str(self.path)+'.lock',0o600)
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not self.path.exists():
            if not initialize:raise ValueError('Device state missing: recovery/new provisioning required')
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            with self.transaction() as c:
                c.execute('CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), device TEXT, epoch INTEGER, profile TEXT, seq INTEGER, prepared TEXT)')
                c.execute('CREATE TABLE commands (sequence INTEGER PRIMARY KEY, digest TEXT, command_id TEXT UNIQUE, ack BLOB)')
                c.execute('INSERT INTO state VALUES (1,?,?,?,0,NULL)',(device,epoch,ASCON))
        if self.path.stat().st_mode&0o077:raise ValueError('Device state must be private')
        with self.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS nonce_reservation (id INTEGER PRIMARY KEY CHECK(id=1), high INTEGER NOT NULL)')
            c.execute('INSERT OR IGNORE INTO nonce_reservation VALUES (1,0)')
            c.execute('CREATE TABLE IF NOT EXISTS authority_failure (id INTEGER PRIMARY KEY CHECK(id=1), reason TEXT NOT NULL)')
            if c.execute('SELECT 1 FROM authority_failure').fetchone():raise ValueError('Nonce authority blocked; reviewed rekey required')
        s=self.read()
        if s['device']!=device or s['epoch']!=epoch:raise ValueError('Device state provisioning mismatch')

    @contextmanager
    def transaction(self):
        c=sqlite3.connect(self.path,timeout=3);c.row_factory=sqlite3.Row
        try:
            c.execute('PRAGMA synchronous=FULL');c.execute('BEGIN IMMEDIATE')
            yield c;c.commit()
        except BaseException:c.rollback();raise
        finally:c.close()

    def read(self):
        with self.transaction() as c:return dict(c.execute('SELECT * FROM state WHERE id=1').fetchone())

    def accept_lease(self,first,last):
        with self.transaction() as c:
            if c.execute('SELECT 1 FROM authority_failure').fetchone():raise ValueError('Nonce authority blocked; reviewed rekey required')
            high=c.execute('SELECT high FROM nonce_reservation WHERE id=1').fetchone()[0]
            rollback=first<=high
            if rollback and self.strict_authority:
                c.execute("INSERT OR REPLACE INTO authority_failure VALUES (1,'Server range rollback')")
            elif not rollback:c.execute('UPDATE nonce_reservation SET high=? WHERE id=1',(last,))
        if rollback:raise ValueError('Server nonce authority rollback; new epoch required')

    def execute(self,body,config,*,now=None):
        from .protocol import validate
        validate(body,now)
        d=body['data'];seq=d['command_sequence'];digest=hashlib.sha256(canonical(body)).hexdigest()
        with self.transaction() as c:
            s=dict(c.execute('SELECT * FROM state WHERE id=1').fetchone())
            prior=c.execute('SELECT * FROM commands WHERE sequence=?',(seq,)).fetchone()
            if prior:
                if prior['digest']!=digest or prior['command_id']!=body['message_id']:raise ValueError('Command identity conflict')
                return bytes(prior['ack']) # same exact authenticated response, no second execution
            if d['command_epoch']!=self.epoch or seq<=s['seq']:raise ValueError('Control replay rejected')
            if body['device_id']!=self.device:raise ValueError('Device command binding')
            target=d['requested_profile'];result='UNSUPPORTED';prepared=s['prepared'];profile=s['profile']
            has_key=target==ASCON or config['registry'].get('telemetry_keys',{}).get(PROFILES[target]['algorithm'])
            if target=='kuznyechik-mgm-v1' and has_key:
                from src.kuz_provider import self_test
                if not self_test():raise ValueError('Provider readiness failed')
                high=c.execute('SELECT high FROM nonce_reservation WHERE id=1').fetchone()[0]
                if high<=0:raise ValueError('MGM nonce authority unavailable')
            if target in config['capabilities'] and has_key:
                if d['phase']=='PREPARE':
                    if prepared and strict_json(prepared)['transition_id']!=d['transition_id']:raise ValueError('Conflicting prepared transition')
                    prepared=canonical(d).decode();result='READY'
                else:
                    old=strict_json(prepared) if prepared else None
                    if old is None or any(old[k]!=d[k] for k in ['transition_id','correlation_id','requested_profile','key_reference','command_epoch']):raise ValueError('ACTIVATE without matching PREPARE')
                    profile=target;prepared=None;result='DEVICE_APPLIED'
            ack_data={k:d[k] for k in ['command_id','transition_id','correlation_id','command_epoch','command_sequence','requested_profile','phase']}
            ack_data.update(result=result,command_sha256=digest)
            from .protocol import seal
            ack=seal(message(self.device,'ack',ack_data,now=now),bytes.fromhex(config['status_key']),'device',now=now)
            c.execute('INSERT INTO commands VALUES (?,?,?,?)',(seq,digest,body['message_id'],ack))
            c.execute('UPDATE state SET profile=?,seq=?,prepared=? WHERE id=1',(profile,seq,prepared))
            return ack

    def close(self):
        fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()
