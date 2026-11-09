"""Future control contract. No transport, signing keys or live ACK acceptance."""
from dataclasses import dataclass, asdict
import re
import uuid
from .signals import utc
from src.telemetry import DEVICE

SECURITY_REQUIREMENTS={
    'authentication':'Separate command AEAD/signature, canonical authenticated metadata',
    'authorization':'Dedicated controller identity and per-device MQTT ACL; no telemetry publisher rights',
    'key_separation':'Separate control keys or reviewed cryptographic domain separation',
    'replay':'Persisted independent device/command_epoch/command_sequence, never telemetry replay-state',
    'ack':'Authenticated device ACK bound to command_id/correlation_id/profile/epoch/sequence',
    'recovery':'Persist before send; retry same identity, expiry and timeout; reconcile authenticated applied state'}

@dataclass(frozen=True)
class Command:
    command_id: str
    device_id: str
    command_type: str
    requested_profile: str
    policy_version: str
    created_at: str
    expires_at: str
    command_sequence: int
    command_epoch: int
    acknowledgement_id: str
    correlation_id: str
    status: str = 'proposed'
    schema_version: int = 1

    def validate(self):
        for name in ['command_id','acknowledgement_id','correlation_id']:
            if str(uuid.UUID(getattr(self,name)))!=getattr(self,name):raise ValueError('Canonical UUID required')
        if not DEVICE.fullmatch(self.device_id) or self.command_type!='set_profile' or self.schema_version!=1 or type(self.schema_version) is not int:
            raise ValueError('Unsupported command')
        for name in ['requested_profile','policy_version']:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',getattr(self,name)):raise ValueError('Invalid command reference')
        if self.status not in {'proposed','unsupported','expired','failed','simulated'}:raise ValueError('Live command status forbidden')
        for v in [self.command_sequence,self.command_epoch]:
            if type(v) is not int or not 1<=v<=2**63-1:raise ValueError('Invalid command replay identity')
        ttl=(utc(self.expires_at)-utc(self.created_at)).total_seconds()
        if not 0<ttl<=300:raise ValueError('Command TTL must be 1..300 seconds')
        return self

    def payload(self):return asdict(self.validate())


class AckSimulator:
    """Deterministic fixture; must never update production Applied Configuration."""
    def __init__(self):self.last={};self.used=set();self.applied={}
    def acknowledge(self,command,now,*,subject='simulation-controller',authentic=False):
        command.validate();now=utc(now)
        if subject!='simulation-controller' or authentic is not True:raise ValueError('Simulator authentication/authorization required')
        if not utc(command.created_at)<=now<utc(command.expires_at):raise ValueError('Expired or premature command')
        if command.command_id in self.used:raise ValueError('Duplicate command')
        key=(command.device_id,command.command_epoch)
        if command.command_sequence<=self.last.get(key,0):raise ValueError('Command replay')
        if command.requested_profile not in {'ascon-aead128-v1','simulated-profile'}:raise ValueError('Unsupported simulated profile')
        self.last[key]=command.command_sequence;self.used.add(command.command_id)
        self.applied[command.device_id]=command.requested_profile
        return dict(acknowledgement_id=command.acknowledgement_id,command_id=command.command_id,
                    correlation_id=command.correlation_id,status='simulated',mode='SIMULATION',
                    applied_configuration=None,simulated_configuration=command.requested_profile)
