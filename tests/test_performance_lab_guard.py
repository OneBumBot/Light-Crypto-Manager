"""A lab runner must reject another project/state before any Docker mutation."""
import json
import pytest
from scripts.performance_lab import Lab


def fixture_root(tmp_path,project='lcm-stage10-performance-test',devices=None,mode='MANUAL_AUTHORIZED_CONTROL'):
    tmp_path.chmod(0o700)
    (tmp_path/'stage10.json').write_text(json.dumps(dict(project=project,devices=devices if devices is not None else ['alpha','beta','gamma'])))
    (tmp_path/'compose.env').write_text(f'COMPOSE_PROJECT_NAME={project}\nCONTROL_INPUT_DIR={tmp_path}\nCONTROL_MODE={mode}\n')
    return tmp_path


@pytest.mark.parametrize('project',['lightcrypto','lcm-stage9-demo-test','lcm-stage10-performance-','lcm-stage10-performance-'+('a'*19)])
def test_rejects_non_performance_project(tmp_path,project):
    with pytest.raises(ValueError):Lab(fixture_root(tmp_path,project))


@pytest.mark.parametrize('devices',[[],['alpha']*51,['alpha','alpha'],['alpha','../other']])
def test_rejects_unbounded_or_aliased_devices(tmp_path,devices):
    with pytest.raises(ValueError):Lab(fixture_root(tmp_path,devices=devices))


def test_rejects_non_private_or_non_manual(tmp_path):
    root=fixture_root(tmp_path);root.chmod(0o755)
    with pytest.raises(ValueError):Lab(root)
    root=fixture_root(tmp_path,mode='AUTOMATIC')
    with pytest.raises(ValueError):Lab(root)


def test_verified_project_has_only_separate_device_names(tmp_path):
    lab=Lab(fixture_root(tmp_path))
    assert lab.agents()==['device-alpha','device-beta','device-gamma']
    assert lab.commands==[]
    assert 'compose.stage9.yaml' not in lab.base
