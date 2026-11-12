"""Transactional live control authority. No network calls in SQL transactions."""
from datetime import timedelta
import hashlib,uuid
from sqlalchemy import select,update,func,or_,and_
from sqlalchemy.dialects.postgresql import insert
from src.crypto_profiles import ASCON,KUZ,PROFILES,BY_ALGORITHM
from src.telemetry import canonical,InvalidTelemetry
from src.replay import replay_state
from . import models as m
from .protocol import message,CONTROLLER

MODE='MANUAL_AUTHORIZED_CONTROL'


def now(c):return c.scalar(select(func.clock_timestamp()))
def identity():return str(uuid.uuid4())
def log(c,device,action,tid=None,**detail):
    c.execute(m.audit.insert().values(id=identity(),device_id=device,transition_id=tid,action=action,detail=detail,at=now(c)))


def provision(c,config):
    for device,e in config.items():
        fingerprint=hashlib.sha256(canonical(e)).hexdigest()
        added=c.execute(insert(m.devices).values(device_id=device,key_epoch=e['command_epoch'],capabilities=e['capabilities'],key_fingerprint=fingerprint).on_conflict_do_nothing().returning(m.devices.c.device_id)).scalar()
        if added and 'Kuznyechik-MGM' in e['registry'].get('telemetry_keys',{}):
            from src.kuz_usage import initialize_fresh
            initialize_fresh(c,device,e['command_epoch'])
        row=c.execute(select(m.devices).where(m.devices.c.device_id==device).with_for_update()).mappings().one()
        if row['key_fingerprint']!=fingerprint:raise ValueError('Live provisioning conflict; explicit reviewed epoch migration required')


def lock(c,device):
    row=c.execute(select(m.devices).where(m.devices.c.device_id==device).with_for_update()).mappings().first()
    if row is None:raise ValueError('Device is not provisioned for live control')
    return row


def add_command(c,device,t,phase):
    seq=device['command_sequence']+1
    c.execute(update(m.devices).where(m.devices.c.device_id==device['device_id']).values(command_sequence=seq))
    command_id=identity();n=now(c)
    body=message(device['device_id'],'command',dict(command_id=command_id,transition_id=t['id'],correlation_id=t['correlation_id'],
        command_type='set_profile',phase=phase,requested_profile=t['target_profile'],source_version='admin-v1',controller_identity=CONTROLLER,
        profile_config_version=1,key_reference=t['target_profile']+':'+str(device['key_epoch']),command_epoch=device['key_epoch'],command_sequence=seq),
        now=n,ttl=max(1,min(300,int((t['deadline']-n).total_seconds()))),message_id=command_id)
    c.execute(m.commands.insert().values(id=command_id,transition_id=t['id'],device_id=device['device_id'],command_epoch=device['key_epoch'],sequence=seq,
        phase=phase,body=body,available_at=n,expires_at=t['deadline']))
    return command_id


def request_switch(c,device,target,actor,*,ttl=120,mode=None):
    if mode!=MODE or type(actor) is not str or not actor.startswith('admin:'):raise ValueError('Explicit manual administrative authorization required')
    from src.policy.profiles import IMPLEMENTED
    implementation=IMPLEMENTED.get(target) if type(target) is str else None
    if target==KUZ:
        from src.kuz_release import allow_validation
        allow_validation()
    if implementation is None or not all([implementation.activation_allowed,implementation.server_implemented,implementation.device_implemented,implementation.known_vectors_passed,implementation.software_e2e_passed]):raise ValueError('Profile implementation not verified')
    if target not in PROFILES or type(ttl) is not int or not 15<=ttl<=300:raise ValueError('Unsupported control request')
    d=lock(c,device);n=now(c)
    from src.devices import devices as registry_devices
    if not c.scalar(select(registry_devices.c.device_id).where(registry_devices.c.device_id==device,registry_devices.c.enabled.is_(True),registry_devices.c.key_epoch==d['key_epoch'])):raise ValueError('Device disabled')
    if target not in d['capabilities']:raise ValueError('Unsupported device profile')
    if target==KUZ:
        from src.kuz_usage import locked
        u,_=locked(c,device,d['key_epoch'])
        if not u['reserved_invocations'] or u['verify_attempts']>=u['max_verify_attempts']:raise ValueError('MGM budget unavailable')
    if not d['effective_profile'] or not d['effective_event']:raise ValueError('Verified baseline telemetry required')
    if d['pending_transition']:raise ValueError('Conflicting transition; recovery required')
    if d['effective_profile']==target:raise ValueError('Profile already effective')
    if d['last_request_at'] and (n-d['last_request_at']).total_seconds()<2:raise ValueError('Administrative request rate limited')
    t=dict(id=identity(),device_id=device,old_profile=d['effective_profile'],target_profile=target,phase='PREPARED_SERVER',actor=actor,
        correlation_id=identity(),created_at=n,deadline=n+timedelta(seconds=ttl))
    c.execute(m.transitions.insert().values(**t))
    c.execute(update(m.devices).where(m.devices.c.device_id==device).values(pending_transition=t['id'],last_request_at=n))
    add_command(c,d,t,'PREPARE');log(c,device,'PREPARED_SERVER',t['id'],actor=actor,target=target)
    return t['id']


def grant(c,body):
    device=body['device_id'];d=lock(c,device);data=body['data'];n=now(c)
    if data['key_epoch']!=d['key_epoch']:raise ValueError('Lease epoch mismatch')
    old=c.execute(select(m.leases).where(m.leases.c.request_id==body['message_id'])).mappings().first()
    if old:
        if old['device_id']!=device or old['boot_id']!=data['boot_id']:raise ValueError('Conflicting boot request')
        return old['body']
    if c.scalar(select(func.count()).select_from(m.leases).where(m.leases.c.device_id==device))>=10000:raise ValueError('Lease retention limit; reviewed maintenance required')
    high=max(d['sequence_reserved'],c.scalar(select(func.coalesce(func.max(replay_state.c.last_sequence),0)).where(replay_state.c.device_id==device)) or 0)
    last=high+10000
    if last>2**32-1:raise ValueError('Key invocation budget exhausted; new keys required')
    pending=c.execute(select(m.transitions).where(m.transitions.c.id==d['pending_transition'])).mappings().first() if d['pending_transition'] else None
    permitted=pending['target_profile'] if pending and pending['phase'] in ['ACTIVATION_SENT','DEVICE_APPLIED'] and pending['deadline']>n else None
    if d['effective_profile'] and data['local_profile'] not in [d['effective_profile'],permitted]:raise ValueError('Device state rollback requires explicit recovery')
    from src.kuz_usage import usage,reserve
    if c.scalar(select(usage.c.device_id).where(usage.c.device_id==device,usage.c.key_epoch==d['key_epoch'])):
        reserve(c,device,d['key_epoch'],body['message_id'],high+1,last)
    elif KUZ in d['capabilities']:raise ValueError('MGM usage authority missing')
    reply=message(device,'lease_grant',dict(boot_id=data['boot_id'],request_id=body['message_id'],key_epoch=d['key_epoch'],first_sequence=high+1,last_sequence=last,
        effective_profile=d['effective_profile'],pending_profile=permitted,command_floor=d['command_acknowledged']),now=n)
    c.execute(m.leases.insert().values(request_id=body['message_id'],device_id=device,boot_id=data['boot_id'],body=reply,created_at=n))
    c.execute(update(m.devices).where(m.devices.c.device_id==device).values(sequence_reserved=last))
    log(c,device,'NONCE_RANGE_RESERVED',first=high+1,last=last)
    return reply


def handle_ack(c,body):
    device=body['device_id'];d=lock(c,device);data=body['data'];n=now(c)
    cmd=c.execute(select(m.commands).where(m.commands.c.id==data['command_id'])).mappings().first()
    if cmd is None or cmd['device_id']!=device:raise ValueError('Unmatched ACK')
    source=cmd['body']['data']
    for field in ['command_id','transition_id','correlation_id','command_epoch','command_sequence','requested_profile','phase']:
        if data[field]!=source[field]:raise ValueError('ACK command binding')
    if data['command_sha256']!=hashlib.sha256(canonical(cmd['body'])).hexdigest():raise ValueError('ACK source digest')
    digest=hashlib.sha256(canonical(body)).hexdigest()
    existing=c.execute(select(m.acks).where(m.acks.c.command_id==cmd['id'])).mappings().first()
    if existing:
        if existing['id']!=body['message_id'] or existing['sha256']!=digest:raise ValueError('Conflicting ACK replay')
        return False
    if data['command_epoch']!=d['key_epoch'] or data['command_sequence']<=d['command_acknowledged']:raise ValueError('Stale ACK')
    t=c.execute(select(m.transitions).where(m.transitions.c.id==cmd['transition_id'])).mappings().one()
    if t['phase']=='EFFECTIVE_CONFIRMED':
        # Late valid ACK is evidence only, never changes effective configuration.
        pass
    elif t['deadline']<=n or d['pending_transition']!=t['id']:raise ValueError('Expired or superseded ACK')
    c.execute(m.acks.insert().values(id=body['message_id'],command_id=cmd['id'],device_id=device,body=body,sha256=digest,received_at=n))
    c.execute(update(m.commands).where(m.commands.c.id==cmd['id']).values(status='acknowledged',claim=None,lease_until=None))
    c.execute(update(m.devices).where(m.devices.c.device_id==device).values(command_acknowledged=data['command_sequence']))
    if t['phase']=='EFFECTIVE_CONFIRMED':
        if cmd['phase']!='ACTIVATE' or data['result']!='DEVICE_APPLIED':raise ValueError('Contradictory late ACK')
        c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(acknowledged_at=func.coalesce(m.transitions.c.acknowledged_at,n)))
        if d['effective_event']==t['telemetry_event']:
            c.execute(update(m.devices).where(m.devices.c.device_id==device).values(reported_profile=t['target_profile']))
        log(c,device,'LATE_DEVICE_REPORTED_APPLIED',t['id'],ack=body['message_id'])
        return True
    if data['result']=='READY' and cmd['phase']=='PREPARE' and t['phase'] in ['PREPARED_SERVER','PREPARE_SENT']:
        log(c,device,'DEVICE_READY',t['id'],ack=body['message_id'])
        fresh=dict(d,command_sequence=d['command_sequence'])
        add_command(c,fresh,t,'ACTIVATE')
        c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(phase='ACTIVATION_SENT',activated_at=n))
    elif data['result']=='DEVICE_APPLIED' and cmd['phase']=='ACTIVATE' and t['phase']=='ACTIVATION_SENT':
        c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(phase='DEVICE_APPLIED',acknowledged_at=n))
        c.execute(update(m.devices).where(m.devices.c.device_id==device).values(reported_profile=t['target_profile']))
        log(c,device,'DEVICE_REPORTED_APPLIED',t['id'],ack=body['message_id'])
    elif data['result'] in ['UNSUPPORTED','FAILED']:
        c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(phase='RECOVERY_REQUIRED',error=data['result']))
        log(c,device,'RECOVERY_REQUIRED',t['id'],reason=data['result'])
    else:raise ValueError('Unexpected ACK phase')
    return True


def authorize(c,message):
    """Called AFTER AEAD, BEFORE replay admission, under device row lock."""
    row=c.execute(select(m.devices).where(m.devices.c.device_id==message.device_id).with_for_update()).mappings().first()
    profile=BY_ALGORITHM[message.profile]
    if row is None:
        if profile!=ASCON:raise InvalidTelemetry('No profile authorization')
        return
    if message.key_epoch!=row['key_epoch'] or message.sequence_number>row['sequence_reserved'] or profile not in row['capabilities']:raise InvalidTelemetry('Telemetry lease binding')
    permitted=[row['effective_profile'] or ASCON]
    if row['pending_transition']:
        t=c.execute(select(m.transitions).where(m.transitions.c.id==row['pending_transition'])).mappings().one()
        if t['deadline']<=now(c) or t['phase'] in ['UNKNOWN_OUTCOME','RECOVERY_REQUIRED']:raise InvalidTelemetry('Transition reconciliation required')
        if t['phase'] in ['ACTIVATION_SENT','DEVICE_APPLIED']:permitted.append(t['target_profile'])
    if profile not in permitted:raise InvalidTelemetry('Profile not authorized')


def observe(c,message,event_id):
    d=c.execute(select(m.devices).where(m.devices.c.device_id==message.device_id).with_for_update()).mappings().first()
    if d is None:return
    profile=BY_ALGORITHM[message.profile];n=now(c)
    confirming=False
    if d['pending_transition']:
        pending=c.execute(select(m.transitions).where(m.transitions.c.id==d['pending_transition'])).mappings().one()
        confirming=pending['phase'] in ['ACTIVATION_SENT','DEVICE_APPLIED'] and pending['target_profile']==profile
    if not d['effective_profile'] or confirming:
        if not message.packet_sha256:raise InvalidTelemetry('Missing authenticated packet receipt')
        c.execute(m.evidence.insert().values(event_id=event_id,device_id=message.device_id,key_epoch=message.key_epoch,sequence_number=message.sequence_number,profile=profile,packet_sha256=message.packet_sha256,key_reference=profile+':'+str(message.key_epoch),accepted_at=n))
    if not d['effective_profile']:
        c.execute(update(m.devices).where(m.devices.c.device_id==message.device_id).values(effective_profile=profile,effective_event=event_id,effective_at=n))
        log(c,message.device_id,'BASELINE_TELEMETRY_VERIFIED',event=event_id,profile=profile)
    if d['pending_transition']:
        t=c.execute(select(m.transitions).where(m.transitions.c.id==d['pending_transition'])).mappings().one()
        if t['phase'] in ['ACTIVATION_SENT','DEVICE_APPLIED'] and t['target_profile']==profile:
            c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(phase='EFFECTIVE_CONFIRMED',telemetry_event=event_id,confirmed_at=n))
            c.execute(update(m.devices).where(m.devices.c.device_id==message.device_id).values(effective_profile=profile,effective_event=event_id,effective_at=n,pending_transition=None))
            c.execute(update(m.commands).where(m.commands.c.transition_id==t['id'],m.commands.c.phase=='ACTIVATE').values(status='verified',claim=None,lease_until=None))
            log(c,message.device_id,'EFFECTIVE_CONFIRMED',t['id'],event=event_id,profile=profile,sequence_number=message.sequence_number)


def claim(c,config):
    n=now(c)
    # Device locks precede command locks everywhere, avoiding ACK/claim lock inversion.
    eligible=select(m.commands.c.device_id).where(m.commands.c.status.in_(['pending','claimed']),m.commands.c.available_at<=n,or_(m.commands.c.lease_until.is_(None),m.commands.c.lease_until<=n))
    expired=select(m.transitions.c.id).where(m.transitions.c.deadline<=n,m.transitions.c.phase.in_(['PREPARED_SERVER','PREPARE_SENT','ACTIVATION_SENT','DEVICE_APPLIED']))
    active=select(m.transitions.c.id).where(m.transitions.c.phase.in_(['PREPARED_SERVER','PREPARE_SENT','ACTIVATION_SENT']),m.transitions.c.device_id.in_(eligible))
    device=c.execute(select(m.devices).where(m.devices.c.pending_transition.is_not(None),or_(m.devices.c.pending_transition.in_(active),m.devices.c.pending_transition.in_(expired))).order_by(m.devices.c.device_id).limit(1).with_for_update(skip_locked=True)).mappings().first()
    if not device:return None
    t=c.execute(select(m.transitions).where(m.transitions.c.id==device['pending_transition'])).mappings().one()
    if t['deadline']<=n:
        if t['phase'] not in ['UNKNOWN_OUTCOME','RECOVERY_REQUIRED']:
            c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(phase='UNKNOWN_OUTCOME',error='DeadlineExpired'))
            log(c,device['device_id'],'UNKNOWN_OUTCOME',t['id'])
        return None
    if t['phase'] not in ['PREPARED_SERVER','PREPARE_SENT','ACTIVATION_SENT']:return None
    row=c.execute(select(m.commands).where(m.commands.c.transition_id==t['id'],m.commands.c.status.in_(['pending','claimed']),
        m.commands.c.available_at<=n,or_(m.commands.c.lease_until.is_(None),m.commands.c.lease_until<=n))
        .order_by(m.commands.c.sequence).limit(1).with_for_update(skip_locked=True)).mappings().first()
    if row is None:return None
    if row['attempts']>=12:
        c.execute(update(m.transitions).where(m.transitions.c.id==t['id']).values(phase='UNKNOWN_OUTCOME',error='DeliveryAttemptsExhausted'))
        return None
    from .protocol import seal
    raw=row['wire'] or seal(row['body'],bytes.fromhex(config[device['device_id']]['command_key']),'controller',now=n).decode()
    token=identity()
    c.execute(update(m.commands).where(m.commands.c.id==row['id']).values(wire=raw,claim=token,status='claimed',attempts=row['attempts']+1,lease_until=n+timedelta(seconds=5)))
    return dict(row,wire=raw,claim=token)


def delivery_finished(c,cmd):
    # Only a real broker PUBACK earns a sent audit record. Device ACK is separate.
    if cmd['phase']=='PREPARE':
        c.execute(update(m.transitions).where(m.transitions.c.id==cmd['transition_id'],m.transitions.c.phase=='PREPARED_SERVER').values(phase='PREPARE_SENT'))
    log(c,cmd['device_id'],'BROKER_PUBACK',cmd['transition_id'],command_id=cmd['id'],attempt=cmd['attempts']+1)
    c.execute(update(m.commands).where(m.commands.c.id==cmd['id'],m.commands.c.claim==cmd['claim'],m.commands.c.status=='claimed')
        .values(status='pending',claim=None,lease_until=None,available_at=now(c)+timedelta(seconds=min(10,2**min(cmd['attempts'],4)))))


def reopen_reconciliation(c,device,transition_id,actor,*,ttl=60,mode=None):
    """Explicit admin reopens only observation of an ALREADY authorized activation.
    No new command, no rollback and no applied/effective state is written here.
    """
    if mode!=MODE or not actor.startswith('admin:') or type(ttl) is not int or not 15<=ttl<=120:raise ValueError('Manual bounded reconciliation required')
    d=lock(c,device);n=now(c)
    from src.devices import devices as registered
    if not c.scalar(select(registered.c.device_id).where(registered.c.device_id==device,registered.c.enabled.is_(True))):raise ValueError('Device disabled')
    if d['pending_transition']!=transition_id:raise ValueError('No matching pending transition')
    t=c.execute(select(m.transitions).where(m.transitions.c.id==transition_id)).mappings().one()
    if t['phase'] not in ['UNKNOWN_OUTCOME','RECOVERY_REQUIRED'] or not t['activated_at']:raise ValueError('No prior authorized activation to reconcile')
    if not c.scalar(select(m.commands.c.id).where(m.commands.c.transition_id==transition_id,m.commands.c.phase=='ACTIVATE')):raise ValueError('No durable activation')
    c.execute(update(m.commands).where(m.commands.c.transition_id==transition_id,m.commands.c.status.in_(['pending','claimed'])).values(status='expired',claim=None,lease_until=None))
    c.execute(update(m.transitions).where(m.transitions.c.id==transition_id).values(phase='ACTIVATION_SENT',deadline=n+timedelta(seconds=ttl),error='ReconciliationWindow'))
    log(c,device,'RECONCILIATION_AUTHORIZED',transition_id,actor=actor,ttl=ttl)
