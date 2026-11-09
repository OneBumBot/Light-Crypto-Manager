"""Explicit feature schemas. No inference from arbitrary CSV columns."""
import math
import re
import pandas as pd
import numpy as np

NETWORK_VERSION = 'network-core-v1'
TELEMETRY_VERSION = 'telemetry-causal-v1'
NETWORK_NUMERIC = [
    'arp.opcode','arp.hw.size','icmp.checksum','icmp.seq_le','http.content_length',
    'http.response','tcp.ack','tcp.ack_raw','tcp.checksum','tcp.connection.fin',
    'tcp.connection.rst','tcp.connection.syn','tcp.connection.synack','tcp.flags',
    'tcp.flags.ack','tcp.len','tcp.seq','udp.stream','udp.time_delta',
    'mqtt.conflag.cleansess','mqtt.conflags','mqtt.hdrflags','mqtt.len','mqtt.msgtype',
    'mqtt.proto_len','mqtt.topic_len','mqtt.ver',
]
NETWORK_CATEGORICAL = ['http.request.method','http.referer','http.request.version']
NETWORK_FEATURES = NETWORK_NUMERIC + NETWORK_CATEGORICAL
# Four reported provenance proxies deliberately excluded from the core schema.
NETWORK_EXCLUDED_PROXIES = ['dns.qry.name.len','mqtt.conack.flags','mqtt.protoname','mqtt.topic']
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,47}\Z')


def safe_name(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError('Invalid model identity')
    return value


def network_frame(frame, version=NETWORK_VERSION):
    if version != NETWORK_VERSION:
        raise ValueError('Unsupported network feature schema')
    if not isinstance(frame,pd.DataFrame) or frame.columns.duplicated().any():
        raise ValueError('Unique named network columns required')
    missing = set(NETWORK_FEATURES)-set(frame.columns)
    if missing:
        raise ValueError('Missing network columns: '+','.join(sorted(missing)))
    result=frame[NETWORK_FEATURES].copy()
    boolean_fields={'http.response','tcp.connection.fin','tcp.connection.rst',
        'tcp.connection.syn','tcp.connection.synack','tcp.flags.ack','mqtt.conflag.cleansess'}
    for name in NETWORK_NUMERIC:
        values=result[name]
        if values.map(lambda x:isinstance(x,(bool,np.bool_))).any():
            raise ValueError('Boolean token in numeric feature: '+name)
        numeric=pd.to_numeric(values,errors='raise').astype(float)
        present=numeric.dropna()
        limits={'arp.opcode':65535,'arp.hw.size':255,'icmp.checksum':65535,'icmp.seq_le':65535,
            'http.content_length':2**31-1,'tcp.ack':2**32-1,'tcp.ack_raw':2**32-1,'tcp.checksum':65535,
            'tcp.flags':511,'tcp.len':65535,'tcp.seq':2**32-1,'udp.stream':2**31-1,'udp.time_delta':86400,
            'mqtt.conflags':255,'mqtt.hdrflags':255,'mqtt.len':268435455,'mqtt.msgtype':15,
            'mqtt.proto_len':65535,'mqtt.topic_len':65535,'mqtt.ver':5}
        maximum=1 if name in boolean_fields else limits[name]
        if not np.isfinite(present).all() or (present<0).any() or (present>maximum).any():
            raise ValueError('Network feature outside supported range: '+name)
        result[name]=numeric
    for name in NETWORK_CATEGORICAL:
        def category(value):
            if value is None or (isinstance(value,float) and math.isnan(value)):
                return np.nan
            if isinstance(value,(int,float,np.number)) and value==0: return '__ABSENT__'
            if type(value) is str and value.strip() in ('0','0.0'): return '__ABSENT__'
            if type(value) is not str or len(value)>4096 or any(ord(c)<32 for c in value):
                raise ValueError('Invalid network category: '+name)
            return value.strip()
        result[name]=result[name].map(category)
    return result
