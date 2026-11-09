"""Synthetic fixtures only; no claim of real network/physical anomaly quality."""
from datetime import datetime,timedelta,timezone
import numpy as np
import pandas as pd
from src.classifier.ml.schema import NETWORK_NUMERIC,NETWORK_CATEGORICAL


def telemetry_rows(devices=('raspb1','alpha','beta'),count=80):
    rows=[]
    origin=datetime(2026,1,1,tzinfo=timezone.utc)
    for index in range(count):
        for device_index,device in enumerate(devices):
            measured=origin+timedelta(seconds=index*10)
            rows.append(dict(device_id=device,key_epoch=1,sequence_number=index+1,
                measured_at=measured.isoformat(),received_at=(measured+timedelta(milliseconds=100)).isoformat(),
                temperature=20+device_index*15+float(np.sin(index/4)),humidity=35+device_index*10+float(np.cos(index/6))))
    return rows


def network_rows(count=240):
    booleans={'http.response','tcp.connection.fin','tcp.connection.rst','tcp.connection.syn',
        'tcp.connection.synack','tcp.flags.ack','dns.qry.qu','dns.retransmission','mqtt.conflag.cleansess'}
    rows=[]
    for i in range(count):
        label=i%3
        row={name:(i%2 if name in booleans else float(i+1)) for name in NETWORK_NUMERIC}
        row['mqtt.ver']=4;row['mqtt.msgtype']=i%15;row['arp.hw.size']=6
        row.update({name:('GET' if label==0 else 'POST') for name in NETWORK_CATEGORICAL})
        row.update(capture_id='capture-'+str(i//12),Attack_label=int(label!=0),
                   Attack_type=['Normal','DDoS_TCP','XSS'][label],device_id='synthetic-network')
        rows.append(row)
    return pd.DataFrame(rows)


def config(task='telemetry_anomaly',algorithm='statistical'):
    return dict(config_version=1,random_state=42,mode='DEMO',source='EXPLICIT_SYNTHETIC_TEST_FIXTURE',
        license_status='project-generated test fixture; not Edge-IIoTset',synthetic=True,max_rows=10000,
        model_id='test-model',model_version='1.0.0',task=task,algorithm=algorithm,
        feature_version='telemetry-causal-v1' if task=='telemetry_anomaly' else 'network-core-v1',
        split_strategy='time' if task=='telemetry_anomaly' else 'group',group_column=None if task=='telemetry_anomaly' else 'capture_id',
        time_column='received_at',fractions=[0.6,0.2,0.2],window=5,expected_interval=10,trees=12,
        validation_alert_quantile=0.95,validation_fpr_target=0.1,reject_feature_overlap=True)
