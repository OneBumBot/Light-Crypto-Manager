"""Strict normalized signals. Trust is assigned by local adapters, never MQTT AAD."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import math
import re
from src.telemetry import DEVICE, MAX_SEQUENCE
from src.ml_signals import signal as ml_signal

SOURCES = {'protocol': {'accepted', 'replay', 'rejected', 'security_violation'},
           'rule': {'physical_anomaly', 'delivery_delay'},
           'ml': {'anomaly', 'normal', 'unavailable'},
           'system': {'unavailable', 'healthy', 'stale'}}


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Signal:
    event_id: str
    source: str
    category: str
    occurred_at: str
    received_at: str
    device_id: str | None = None
    key_epoch: int | None = None
    sequence_number: int | None = None
    binding: str = 'unattributed'
    trust: str = 'monitor'
    source_version: int = 1
    schema_version: int = 1
    original: dict | None = None

    def validate(self):
        if self.schema_version != 1 or type(self.schema_version) is not int or self.source_version != 1 or type(self.source_version) is not int:
            raise ValueError('Unsupported signal schema')
        if self.source not in SOURCES or self.category not in SOURCES[self.source]:
            raise ValueError('Unsupported signal source/category')
        if not isinstance(self.event_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', self.event_id):
            raise ValueError('Invalid event identity')
        utc(self.occurred_at); utc(self.received_at)
        if self.binding not in {'authenticated', 'unattributed', 'simulation'} or self.trust not in {'verified', 'monitor', 'simulation'}:
            raise ValueError('Invalid provenance')
        if self.device_id is not None and (not isinstance(self.device_id,str) or not DEVICE.fullmatch(self.device_id)):
            raise ValueError('Invalid device')
        if self.binding == 'unattributed' and any(v is not None for v in [self.device_id,self.key_epoch,self.sequence_number]):
            raise ValueError('Unverified identity cannot target a device')
        if self.binding != 'unattributed' and self.device_id is None:
            raise ValueError('Bound identity required')
        for value, maximum in [(self.key_epoch,2**31-1),(self.sequence_number,MAX_SEQUENCE)]:
            if value is not None and (type(value) is not int or not 1 <= value <= maximum):
                raise ValueError('Invalid source identity')
        if self.trust == 'verified' and (self.binding != 'authenticated' or self.source == 'ml'):
            raise ValueError('Unverified source cannot assert verified trust')
        if self.source == 'ml':
            validate_ml(self.original)
            if any(getattr(self,k)!=self.original[k] for k in ['device_id','key_epoch','sequence_number']):
                raise ValueError('Inner/outer ML identity mismatch')
            expected='unavailable' if self.original['status']!='ok' else ('anomaly' if self.original['is_anomaly'] else 'normal')
            if self.category!=expected:raise ValueError('ML category mismatch')
            if self.trust != 'monitor': raise ValueError('Research ML cannot gain trust')
        if self.original is not None and type(self.original) is not dict:
            raise ValueError('Original semantics must be an object')
        if len(json.dumps(asdict(self),allow_nan=False).encode()) > 16384:
            raise ValueError('Signal too large')
        return self

    def payload(self):
        self.validate()
        return asdict(self)


def validate_ml(value):
    if type(value) is not dict: raise ValueError('ML semantics required')
    required={'signal_version','device_id','key_epoch','sequence_number','detector','model_id','model_version',
              'feature_version','score','threshold','is_anomaly','evaluated_at','score_direction',
              'score_range','score_semantics','mode','trusted_detector','interpretation','status'}
    if set(value) != required or value['signal_version'] != 1 or type(value['signal_version']) is not int:
        raise ValueError('Unsupported ML contract')
    if value['detector'] not in {'telemetry_anomaly','network_intrusion'} or value['mode'] not in {'DEMO','RESEARCH'} or value['trusted_detector'] is not False:
        raise ValueError('Unsupported ML provenance')
    if value['feature_version'] not in {'telemetry-causal-v1','network-core-v1'}:
        raise ValueError('Unsupported feature schema')
    if (value['detector']=='telemetry_anomaly') != (value['feature_version']=='telemetry-causal-v1'):
        raise ValueError('Detector/feature mismatch')
    for name in ['model_id','model_version']:
        if not isinstance(value[name],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,47}',value[name]):
            raise ValueError('Invalid model identity')
    if not isinstance(value['device_id'],str) or not DEVICE.fullmatch(value['device_id']):raise ValueError('Invalid ML device')
    for name,maximum in [('key_epoch',2**31-1),('sequence_number',MAX_SEQUENCE)]:
        if type(value[name]) is not int or not 1<=value[name]<=maximum:raise ValueError('Invalid ML measurement identity')
    utc(value['evaluated_at'])
    if value['score_direction']!='higher_is_more_anomalous':raise ValueError('Unsupported score direction')
    bounds=value['score_range']
    if type(bounds) is not list or len(bounds)!=2 or type(bounds[0]) not in (float,int) or bounds[0]!=0:
        raise ValueError('Invalid score range')
    upper=bounds[1]
    if upper is not None and (type(upper) not in (float,int) or not math.isfinite(upper) or upper<=0):raise ValueError('Invalid score bound')
    statuses={'ok','processing','warmup','unknown_device','dead','retry','invalid_history','out_of_order','feed_expired','unavailable','disabled','version_conflict'}
    if value['status'] not in statuses: raise ValueError('Unknown ML status')
    if value['status']=='ok':
        for name in ['score','threshold']:
            v=value[name]
            if type(v) not in (float,int) or not math.isfinite(v) or v<0 or (name=='score' and upper is not None and v>upper):
                raise ValueError('Invalid model-specific scale')
        if type(value['is_anomaly']) is not bool or value['is_anomaly'] != (value['score']>=value['threshold']):
            raise ValueError('Inconsistent ML flag')
    elif any(value[k] is not None for k in ['score','threshold','is_anomaly']):
        raise ValueError('Unscored is not normal')
    if not isinstance(value['score_semantics'],str) or not 1<=len(value['score_semantics'])<=256:
        raise ValueError('Score semantics required')


def from_ml(event, model, received_at):
    if event['feature_version']!=model.get('feature_version') or event['detector']!=model['detector']:
        raise ValueError('ML model identity mismatch')
    if (event['model_id'],event['model_version'])!=(model['model_id'],model['model_version']):raise ValueError('ML identity mismatch')
    if event['status']=='ok':
        raw=ml_signal(event,model)
    else:
        raw=dict(signal_version=1,device_id=event['device_id'],key_epoch=event['key_epoch'],sequence_number=event['sequence_number'],
            detector=event['detector'],model_id=event['model_id'],model_version=event['model_version'],feature_version=event['feature_version'],
            score=None,threshold=None,is_anomaly=None,evaluated_at=utc(event['evaluated_at'] or event['available_at']).isoformat(),
            score_direction='higher_is_more_anomalous',score_range=[0,model.get('score_upper_bound')],
            score_semantics=model.get('score_semantics'),mode=model['mode'],trusted_detector=False,
            interpretation='Unscored observation; not normal')
    raw['status']=event['status']
    category='unavailable' if raw['status']!='ok' else ('anomaly' if raw['is_anomaly'] else 'normal')
    return Signal('ml:'+event['id']+':'+raw['status'],'ml',category,raw['evaluated_at'],utc(received_at).isoformat(),
                  event['device_id'],event['key_epoch'],event['sequence_number'],'authenticated','monitor',original=raw).validate()
