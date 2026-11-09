"""Trusted-local artifact boundary: owner/modes, path, manifest, hash and exact versions."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
from datetime import datetime, timezone
import joblib
from .schema import safe_name, NETWORK_VERSION, TELEMETRY_VERSION

LIBRARIES=['numpy','pandas','scipy','scikit-learn','joblib']
MAX_ARTIFACT=64*1024*1024


def versions():
    return {'python':platform.python_version(),**{name:importlib.metadata.version(name) for name in LIBRARIES}}


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    return digest.hexdigest()


def artifact_path(root,model_id,version):
    safe_name(model_id);safe_name(version)
    root=Path(root).absolute()
    if root.is_symlink(): raise ValueError('Symlink model root forbidden')
    root=root.resolve(strict=True)
    path=root/model_id/version
    for part in [root,root/model_id,path]:
        if part.is_symlink(): raise ValueError('Symlink artifact path forbidden')
    return root,path


def verify(root,model_id,version,*,enforce_owner=True):
    root,path=artifact_path(root,model_id,version)
    for directory in [root,path.parent,path]:
        mode=directory.stat()
        if stat.S_IMODE(mode.st_mode)&0o077 or (enforce_owner and mode.st_uid!=os.getuid()):
            raise ValueError('Private owned model directories required')
    for name,limit in [('manifest.json',1024*1024),('model.joblib',MAX_ARTIFACT)]:
        file=path/name
        info=file.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size>limit or info.st_mode&0o077 or (enforce_owner and info.st_uid!=os.getuid()):
            raise ValueError('Private regular artifact files required')
    from src.telemetry import strict_json
    manifest=strict_json((path/'manifest.json').read_bytes())
    if manifest.get('manifest_version')!=1 or manifest.get('model_id')!=model_id or manifest.get('model_version')!=version:
        raise ValueError('Artifact identity/version mismatch')
    # New offline schema is additive; legacy v1 meanings and telemetry contract stay unchanged.
    expected={NETWORK_VERSION,'tcp-packet-passive-v1'} if manifest.get('task')=='network_ids' else {TELEMETRY_VERSION}
    if manifest.get('feature_version')=='tcp-packet-passive-v1':
        if manifest.get('trusted_detector') is not False or manifest.get('preprocessing',{}).get('feature_order')!=['frame.len','tcp.len','tcp.flags','tcp.window_size_value','tcp.time_delta']:
            raise ValueError('Invalid offline research schema/trust declaration')
    if manifest.get('task') not in ('network_ids','telemetry_anomaly') or type(manifest.get('feature_version')) is not str or manifest.get('feature_version') not in expected:
        raise ValueError('Unsupported artifact feature contract')
    if manifest.get('versions')!=versions(): raise ValueError('Artifact dependency version mismatch')
    if manifest.get('artifact_sha256')!=file_hash(path/'model.joblib'):
        raise ValueError('Artifact integrity mismatch')
    if manifest.get('mode') not in ('DEMO','RESEARCH'): raise ValueError('Unsupported model trust level')
    threshold=manifest.get('threshold')
    if type(threshold) not in (int,float) or (not __import__('math').isfinite(threshold) or threshold<0):
        raise ValueError('Invalid artifact threshold')
    return manifest,path


def export(root,model_id,version,pipeline,metadata):
    safe_name(model_id);safe_name(version)
    os.umask(0o077)
    root=Path(root).absolute()
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.is_symlink() or root.stat().st_mode&0o077 or root.stat().st_uid!=os.getuid():
        raise ValueError('Private owned model root required')
    directory=root/model_id
    directory.mkdir(mode=0o700,exist_ok=True)
    if directory.is_symlink(): raise ValueError('Symlink model directory forbidden')
    path=directory/version
    path.mkdir(mode=0o700,exist_ok=False)
    joblib.dump(pipeline,path/'model.joblib',compress=3,protocol=5)
    (path/'model.joblib').chmod(0o600)
    if (path/'model.joblib').stat().st_size>MAX_ARTIFACT: raise ValueError('Artifact exceeds local size bound')
    manifest={**metadata,'manifest_version':1,'model_id':model_id,'model_version':version,
        'versions':versions(),'trained_at':datetime.now(timezone.utc).isoformat(),
        'artifact_sha256':file_hash(path/'model.joblib')}
    (path/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    (path/'manifest.json').chmod(0o600)
    verify(root,model_id,version)
    return manifest


def load(root,model_id,version):
    manifest,path=verify(root,model_id,version)
    # Hash is integrity, not signature/authenticity: private trusted root is mandatory.
    pipeline=joblib.load(path/'model.joblib')
    return manifest,pipeline
