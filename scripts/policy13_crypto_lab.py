"""Reuse verified three-profile provisioning, strictly within fresh Stage13 namespace.

The version1 private manifest remains stage12.json for adapter compatibility;
project/volumes/credentials are new Stage13 identities, never old Stage12 state.
"""
import json,re
from pathlib import Path
from scripts import crypto_research_lab as base

base.PREFIX=re.compile(r'lcm-stage13-policy-[a-z0-9-]{1,18}\Z')
original_prepare=base.prepare


def prepare(root,project,count):
    original_prepare(root,project,count)
    root=Path(root);p=root/'research.compose.json';config=json.loads(p.read_text())
    config['services']['control-init']['command']=['python','-m','scripts.install_policy13_crypto']
    p.write_text(json.dumps(config,indent=2));p.chmod(0o600)


base.prepare=prepare
Lab=base.Lab
if __name__=='__main__':base.main()
