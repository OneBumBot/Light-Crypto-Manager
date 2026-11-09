"""Explicit trusted-local model install; verifies hashes without root unpickling."""
import os
from pathlib import Path
import shutil
from src.classifier.ml.artifacts import verify
from src.classifier.ml.schema import safe_name

mid=safe_name(os.environ.get('ML_MODEL_ID','telemetry-statistical'))
version=safe_name(os.environ.get('ML_MODEL_VERSION','1.0.0'))
manifest,source=verify('/input',mid,version,enforce_owner=False)
root=Path('/models')
for path in [root,root/mid,root/mid/version]:
    if path.is_symlink():raise ValueError('Symlink install path forbidden')
    path.mkdir(exist_ok=True);path.chmod(0o700);os.chown(path,10001,10001)
for name in ['model.joblib','manifest.json']:
    path=root/mid/version/name
    if path.is_symlink():raise ValueError('Symlink installed artifact forbidden')
    if path.exists() and path.read_bytes()!=(source/name).read_bytes():
        raise ValueError('Refusing to overwrite an immutable installed model')
    shutil.copyfile(source/name,path);path.chmod(0o600);os.chown(path,10001,10001)
print('Trusted local model installed; model not deserialized by root')
