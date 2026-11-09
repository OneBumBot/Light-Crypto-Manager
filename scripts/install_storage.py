"""Copy database credentials into separate service volumes with restricted access."""
import os
from pathlib import Path
import shutil

for role, names, uid in [('mongo', ['root', 'relay', 'history'], 999),
                         ('relay', ['relay'], 10001), ('web', ['history'], 10001),
                         ('tests', ['relay', 'history'], 10001)]:
    target = Path('/out') / role
    target.mkdir(exist_ok=True)
    target.chmod(0o700)
    os.chown(target, uid, uid)
    for name in names:
        path = target / (name + '.password')
        shutil.copyfile(Path('/input') / path.name, path)
        path.chmod(0o600)
        os.chown(path, uid, uid)
print('Database role credentials installed')
