"""Packet TCP features visible under TLS; availability does not prove IDS quality."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator,TransformerMixin

VERSION='tcp-packet-passive-v1'
FEATURES=['frame.len','tcp.len','tcp.flags','tcp.window_size_value','tcp.time_delta']
LIMITS={'frame.len':4*1024*1024,'tcp.len':65535,'tcp.flags':511,'tcp.window_size_value':2**30,'tcp.time_delta':86400}
META=['source_id','capture_id','session_id','packet_id','epoch_seconds','attack_type','label']


def packet_frame(frame,version=VERSION):
    if version!=VERSION:raise ValueError('Unsupported packet feature version')
    if not isinstance(frame,pd.DataFrame) or frame.columns.duplicated().any() or not set(FEATURES)<=set(frame):
        raise ValueError('Required packet features missing or duplicated; no zero-fill fallback')
    result=frame[FEATURES].copy()
    for name in FEATURES:
        values=result[name]
        if values.map(lambda v:isinstance(v,(bool,np.bool_))).any():raise ValueError('Boolean in numeric feature')
        if name=='tcp.flags':
            values=values.map(lambda v:int(v,16) if isinstance(v,str) and v.lower().startswith('0x') else v)
        try:numeric=pd.to_numeric(values.replace('',np.nan),errors='raise').astype(float)
        except (ValueError,TypeError):raise ValueError('Invalid packet numeric feature: '+name) from None
        present=numeric.dropna()
        if not np.isfinite(present).all() or (present<0).any() or (present>LIMITS[name]).any():
            raise ValueError('Invalid packet range: '+name)
        if name!='tcp.time_delta' and (present%1!=0).any():raise ValueError('Integral packet field required: '+name)
        result[name]=numeric
    return result


class PacketSchema(BaseEstimator,TransformerMixin):
    def __init__(self,version=VERSION):self.version=version
    def fit(self,X,y=None):packet_frame(X,self.version);return self
    def transform(self,X):return packet_frame(X,self.version)
