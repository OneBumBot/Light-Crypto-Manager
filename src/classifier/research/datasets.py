"""Explicit local CSV import with source hashes, packet provenance and bounded RAM."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import numpy as np
import pandas as pd
from src.classifier.ml.artifacts import file_hash
from .schema import VERSION,FEATURES,META,packet_frame

LABELS={'legitimate':'Normal','normal':'Normal','bruteforce':'Bruteforce','dos':'DoS',
        'malformed':'Malformed','slowite':'SlowITe','flood':'Flood','aggressivescan':'AggressiveScan',
        'udpscan':'UDPScan','sshbruteforce':'SSHBruteforce','mqttbruteforce':'MQTTBruteforce'}
ONTOLOGIES={'mqttset':sorted(['Normal','Bruteforce','DoS','Malformed','SlowITe','Flood']),
            'mqtt-iot-ids2020':sorted(['Normal','AggressiveScan','UDPScan','SSHBruteforce','MQTTBruteforce'])}
RAW=FEATURES+['frame.time_epoch','frame.number','tcp.stream','ip.proto']


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def mapping(value):
    if not isinstance(value,str) or value.strip().lower() not in LABELS:raise ValueError('Unknown attack class; explicit mapping required')
    name=LABELS[value.strip().lower()];return name,0 if name=='Normal' else 1


def header(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:cols=next(csv.reader(stream),[])
    if not cols or len(set(cols))!=len(cols):raise ValueError('Missing/duplicate CSV header')
    return cols


def import_csv(config,output,max_rows=100000):
    if type(max_rows) is not int or not 10<=max_rows<=1000000:raise ValueError('Explicit import resource bound required')
    if config.get('schema_version')!=1 or type(config.get('schema_version')) is not int or config.get('granularity')!='packet':
        raise ValueError('Only packet granularity schema1 is accepted; flows cannot be coerced')
    if config.get('feature_version')!=VERSION:raise ValueError('Extractor version mismatch')
    if type(config.get('synthetic')) is not bool or not config.get('source_url') or not config.get('dataset_version') or not config.get('license'):
        raise ValueError('Source/version/license/synthetic declaration required')
    if config.get('label_scope') not in {'capture_scenario','packet_audited','synthetic_fixture'}:raise ValueError('Label provenance required')
    family=config.get('dataset_family','mqttset')
    if family not in ONTOLOGIES:raise ValueError('Unsupported dataset class ontology')
    sources=config.get('files')
    if type(sources) is not list or not 1<=len(sources)<=100:raise ValueError('Bounded source file list required')
    output=Path(output)
    if output.exists() or output.with_suffix('.manifest.json').exists():raise ValueError('Prepared dataset is immutable')
    raw_files=[];frames=[];seen_hashes=set();captures=set();total=0;non_tcp=0
    for entry in sources:
        path=Path(entry['path']);capture=entry['capture_id'];source=entry['source_id']
        if not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',v) for v in [source,capture]):raise ValueError('Invalid provenance identity')
        digest=file_hash(path)
        if not isinstance(entry.get('sha256'),str) or digest!=entry['sha256']:raise ValueError('Dataset provenance/hash mismatch')
        if digest in seen_hashes or (source,capture) in captures:raise ValueError('Duplicate capture or byte-identical source file')
        seen_hashes.add(digest);captures.add((source,capture))
        if not set(RAW)<=set(header(path)):raise ValueError('Missing capture/session/TCP fields; reduced or flow CSV incompatible')
        label_name,label=mapping(entry['attack_type'])
        if label_name not in ONTOLOGIES[family]:raise ValueError('Attack class incompatible with source ontology')
        label_column=entry.get('label_column') if config['label_scope']=='packet_audited' else None
        if config['label_scope']=='packet_audited' and (not isinstance(label_column,str) or label_column not in header(path)):
            raise ValueError('Audited per-packet binary label column required')
        raw=pd.read_csv(path,usecols=RAW+([label_column] if label_column else []),dtype=str,keep_default_na=False,nrows=max_rows-total+1)
        total+=len(raw)
        if total>max_rows:raise ValueError('Import exceeds explicit max_rows; no silent truncation')
        proto=pd.to_numeric(raw['ip.proto'],errors='raise');non_tcp+=int((proto!=6).sum());raw=raw.loc[proto==6].copy()
        features=packet_frame(raw)
        epoch=pd.to_numeric(raw['frame.time_epoch'],errors='raise').astype(float)
        if not np.isfinite(epoch).all() or (epoch<=0).any() or (epoch>32503680000).any():raise ValueError('Invalid packet timestamp')
        number=pd.to_numeric(raw['frame.number'],errors='raise')
        if (number<=0).any() or (number%1!=0).any():raise ValueError('Invalid physical packet identity')
        stream=pd.to_numeric(raw['tcp.stream'],errors='raise')
        if (stream<0).any() or (stream%1!=0).any():raise ValueError('Invalid session provenance')
        labels=label
        types=label_name
        if label_column:
            labels=pd.to_numeric(raw[label_column],errors='raise')
            if labels.isna().any() or not labels.isin([0,1]).all() or (label_name=='Normal' and (labels==1).any()):raise ValueError('Invalid audited packet labels')
            types=np.where(labels==0,'Normal',label_name)
        features=features.assign(source_id=source,capture_id=source+':'+capture,
            session_id=source+':'+capture+':'+stream.astype('int64').astype(str),
            packet_id=source+':'+capture+':'+number.astype('int64').astype(str),epoch_seconds=epoch,
            attack_type=types,label=labels)
        frames.append(features)
        raw_files.append(dict(filename=path.name,sha256=digest,source_id=source,capture_id=source+':'+capture,
                              attack_type=label_name,rows=len(raw)))
    if not frames or sum(map(len,frames))==0:raise ValueError('No TCP packet observations')
    data=pd.concat(frames,ignore_index=True)
    repeated=data.duplicated('packet_id',keep=False)
    if repeated.any():
        for _,group in data.loc[repeated].groupby('packet_id'):
            if len(group.drop_duplicates())>1:raise ValueError('Conflicting physical packet identity')
    removed=int(data.duplicated('packet_id').sum());data=data.drop_duplicates('packet_id').reset_index(drop=True)
    os.umask(0o077);output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with output.open('x') as stream:data.to_csv(stream,index=False)
    output.chmod(0o600)
    manifest=dict(schema_version=1,feature_version=VERSION,granularity='packet',extractor='tshark CSV to validated TCP packet fields v1',
        synthetic=config['synthetic'],source_url=config['source_url'],dataset_version=config['dataset_version'],license=config['license'],
        label_scope=config['label_scope'],dataset_family=family,class_ontology=ONTOLOGIES[family],raw_files=raw_files,source_rows=total,rows=len(data),non_tcp_excluded=non_tcp,
        duplicate_packet_rows_removed=removed,sha256=file_hash(output),feature_order=FEATURES,
        columns=list(data),captures=int(data.capture_id.nunique()),sessions=int(data.session_id.nunique()),
        devices=None,time_range_epoch=[float(data.epoch_seconds.min()),float(data.epoch_seconds.max())],
        class_counts={k:int(v) for k,v in data.attack_type.value_counts().items()},
        limitations=['Packet labels inherited from declared source; capture_scenario is not independently audited per-frame ground truth',
                     'Passive features visible under TLS, but online collector and encrypted-domain quality not verified'])
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    return manifest


def read_prepared(path,manifest_path,max_rows=100000):
    if type(max_rows) is not int or not 10<=max_rows<=1000000:raise ValueError('Invalid prepared-data resource bound')
    path=Path(path);manifest=json.loads(Path(manifest_path).read_text())
    if type(manifest.get('schema_version')) is not int or manifest['schema_version']!=1 or manifest.get('granularity')!='packet' or manifest.get('feature_version')!=VERSION:
        raise ValueError('Incompatible prepared schema/granularity')
    if manifest.get('sha256')!=file_hash(path):raise ValueError('Prepared data hash mismatch')
    if manifest.get('feature_order')!=FEATURES:raise ValueError('Extractor feature order mismatch')
    if not set(FEATURES+META)<=set(header(path)):raise ValueError('Missing prepared metadata')
    frame=pd.read_csv(path,nrows=max_rows+1)
    if len(frame)>max_rows or len(frame)!=manifest.get('rows'):raise ValueError('Prepared size mismatch/resource limit')
    packet_frame(frame)
    if frame[META].isna().any().any() or frame.packet_id.duplicated().any():raise ValueError('Invalid prepared provenance')
    if frame.label.map(lambda v:isinstance(v,(bool,np.bool_))).any():raise ValueError('Boolean class label forbidden')
    for column in ['session_id','packet_id']:
        if not all(isinstance(v,str) and v.startswith(str(c)+':') for v,c in zip(frame[column],frame.capture_id)):raise ValueError('Capture/session provenance conflict')
    if not frame.label.isin([0,1]).all() or ((frame.label==0)!=(frame.attack_type=='Normal')).any():raise ValueError('Conflicting class mapping')
    family=manifest.get('dataset_family')
    if family not in ONTOLOGIES or manifest.get('class_ontology')!=ONTOLOGIES[family] or not frame.attack_type.isin(ONTOLOGIES[family]).all():raise ValueError('Unknown or incompatible prepared attack ontology')
    actual={k:int(v) for k,v in frame.attack_type.value_counts().items()}
    if actual!=manifest.get('class_counts') or int(frame.capture_id.nunique())!=manifest.get('captures') or int(frame.session_id.nunique())!=manifest.get('sessions'):
        raise ValueError('Prepared manifest statistics mismatch')
    return frame,manifest
