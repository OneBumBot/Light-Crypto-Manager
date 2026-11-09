"""Causal, per-device windows; no future measurements or cross-device baselines."""
from collections import deque
from datetime import datetime, timezone
import math
from numbers import Integral
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from src.telemetry import DEVICE, positive, validate_sensor
from .schema import TELEMETRY_VERSION

RAW_FIELDS=['device_id','key_epoch','sequence_number','measured_at','received_at','temperature','humidity']
FEATURES=['temperature','humidity','delta_temperature','delta_humidity','rolling_temperature',
          'rolling_humidity','std_temperature','std_humidity','interval_seconds',
          'missing_intervals','ingestion_delay_seconds']


def raw_record(value):
    if not set(RAW_FIELDS)<=set(value): raise ValueError('Missing telemetry columns')
    result={key:value[key] for key in RAW_FIELDS}
    if type(result['device_id']) is not str or not DEVICE.fullmatch(result['device_id']):
        raise ValueError('Invalid device identity')
    for key in ['key_epoch','sequence_number']:
        if not isinstance(result[key],Integral) or isinstance(result[key],bool): raise ValueError('Integer identity required')
        result[key]=int(result[key])
    positive(result['key_epoch'],2**31-1); positive(result['sequence_number'])
    for key in ['measured_at','received_at']:
        date=result[key]
        if isinstance(date,str):
            try:date=datetime.fromisoformat(date)
            except ValueError:raise ValueError('Invalid UTC telemetry datetime') from None
        if not isinstance(date,datetime) or date.utcoffset()!=timezone.utc.utcoffset(None):
            raise ValueError('UTC telemetry dates required')
        result[key]=date.astimezone(timezone.utc)
    validate_sensor(dict(temperature=result['temperature'],humidity=result['humidity'],timestamp=result['measured_at'].isoformat()))
    delay=(result['received_at']-result['measured_at']).total_seconds()
    if not -86400<=delay<=86400: raise ValueError('Unsupported clock/delivery offset')
    return result


def one_window(target,history,window=8,expected_interval=10):
    if not 3<=window<=256 or not math.isfinite(expected_interval) or expected_interval<=0:
        raise ValueError('Invalid window configuration')
    target=raw_record(target)
    prior=[raw_record(row) for row in history]
    if len(prior)>window: raise ValueError('History exceeds configured bound')
    previous_sequence=0
    previous_time=None
    previous_received=None
    for row in prior:
        if row['device_id']!=target['device_id'] or row['key_epoch']!=target['key_epoch']:
            raise ValueError('Mixed device/epoch history')
        if row['sequence_number']<=previous_sequence or row['sequence_number']>=target['sequence_number']:
            raise ValueError('Non-causal sequence history')
        if row['received_at']>target['received_at'] or (previous_received and row['received_at']<previous_received):
            return None,'out_of_order'
        if row['measured_at']>=target['measured_at'] or (previous_time and row['measured_at']<=previous_time):
            return None,'out_of_order'
        previous_sequence=row['sequence_number'];previous_time=row['measured_at'];previous_received=row['received_at']
    if len(prior)<window: return None,'warmup'
    interval=(target['measured_at']-prior[-1]['measured_at']).total_seconds()
    if interval>86400: return None,'out_of_order'
    result={key:target[key] for key in ['device_id','key_epoch','sequence_number','measured_at','received_at','temperature','humidity']}
    for sensor in ['temperature','humidity']:
        values=np.asarray([row[sensor] for row in prior],dtype=float)
        result['delta_'+sensor]=float(target[sensor]-values[-1])
        result['rolling_'+sensor]=float(values.mean())
        result['std_'+sensor]=float(values.std(ddof=0))
    result.update(interval_seconds=interval,missing_intervals=min(1000,max(0,int(interval/expected_interval)-1)),
        ingestion_delay_seconds=(target['received_at']-target['measured_at']).total_seconds())
    return result,'ready'


def causal_frame(records,window=8,expected_interval=10):
    records=[raw_record(row) for row in records]
    # Accepted sequence is authoritative; timestamps are checked, never used to
    # pull future measurements into an earlier window.
    records.sort(key=lambda r:(r['device_id'],r['key_epoch'],r['sequence_number']))
    histories={};seen=set();rows=[];statuses=[]
    for target in records:
        identity=(target['device_id'],target['key_epoch'],target['sequence_number'])
        if identity in seen: raise ValueError('Duplicate source telemetry identity')
        seen.add(identity)
        key=identity[:2]; history=histories.setdefault(key,[])
        if history and target['sequence_number']<=history[-1]['sequence_number']:
            status='out_of_order';row=None
        else: row,status=one_window(target,list(history),window,expected_interval)
        statuses.append({'device_id':target['device_id'],'sequence_number':target['sequence_number'],'status':status})
        if row is not None: rows.append(row)
        # Keep the highest sequence context visible by this received_at cutoff.
        # Nonmonotone measurement windows are skipped until the bad record ages out.
        histories[key]=sorted(history+[target],key=lambda row:row['sequence_number'])[-window:]
    rows.sort(key=lambda r:(r['received_at'],r['device_id'],r['key_epoch'],r['sequence_number']))
    return pd.DataFrame(rows),statuses


class UnknownDevice(ValueError):
    pass


class DeviceFeatures(BaseEstimator,TransformerMixin):
    def __init__(self,version=TELEMETRY_VERSION): self.version=version
    def _check(self,X):
        if self.version!=TELEMETRY_VERSION: raise ValueError('Unsupported telemetry feature schema')
        if not isinstance(X,pd.DataFrame) or not set(['device_id']+FEATURES)<=set(X):
            raise ValueError('Missing causal telemetry features')
        values=X[FEATURES].to_numpy(dtype=float)
        if not np.isfinite(values).all(): raise ValueError('Nonfinite telemetry features')
        return values
    def fit(self,X,y=None):
        self._check(X)
        self.baselines_={}
        for device,group in X.groupby('device_id',sort=True):
            centers={};scales={}
            if len(group)<3: raise ValueError('Insufficient per-device training history')
            for sensor in ['temperature','humidity']:
                values=group[sensor].to_numpy(dtype=float)
                center=float(np.median(values)); scale=max(1.0,float(np.median(np.abs(values-center)))*1.4826)
                centers[sensor]=center;scales[sensor]=scale
            self.baselines_[device]=(centers,scales)
        return self
    def transform(self,X):
        values=self._check(X).copy()
        for i,device in enumerate(X['device_id']):
            if device not in self.baselines_: raise UnknownDevice('No trained device baseline')
            center,scale=self.baselines_[device]
            for sensor in ['temperature','humidity']:
                for field in [sensor,'rolling_'+sensor]:
                    index=FEATURES.index(field);values[i,index]=(values[i,index]-center[sensor])/scale[sensor]
                for field in ['delta_'+sensor,'std_'+sensor]:
                    index=FEATURES.index(field);values[i,index]/=scale[sensor]
        # Time dimensions are explicit, not probabilities.
        values[:,FEATURES.index('interval_seconds')]/=10
        values[:,FEATURES.index('ingestion_delay_seconds')]/=10
        return values


class StatisticalDetector(BaseEstimator):
    def fit(self,X,y=None):
        if len(X)<3: raise ValueError('Insufficient baseline rows')
        self.fitted_=True
        return self
    def score_samples(self,X):
        selected=np.asarray(X)[:,[0,1,2,3,4,5,9]]
        return -np.max(np.abs(selected),axis=1)


def build_telemetry(algorithm='statistical',seed=42,trees=100):
    if algorithm=='statistical':
        return Pipeline([('features',DeviceFeatures()),('model',StatisticalDetector())])
    if algorithm=='isolation_forest':
        return Pipeline([('features',DeviceFeatures()),('impute',SimpleImputer(keep_empty_features=True)),
            ('scale',StandardScaler()),('model',IsolationForest(n_estimators=trees,random_state=seed,n_jobs=1,contamination='auto'))])
    raise ValueError('Unsupported telemetry algorithm')
