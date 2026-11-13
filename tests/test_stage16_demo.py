"""Release guards, not substitutes for the actual Stage16 network smoke."""
import json
import subprocess
from pathlib import Path
import pytest
from scripts import stage16_demo as demo
from scripts.stage9_common import Demo as LegacyDemo


@pytest.fixture
def saved(tmp_path):
    tmp_path.chmod(0o700)
    d=object.__new__(demo.Demo)
    d.root=tmp_path;d.project='lcm-stage16-final-demo-unit'
    return d


def test_missing_used_volume_fails_closed(saved,monkeypatch):
    demo.write(saved.root/'used-volumes.json',{saved.project+'_alpha-control':{'created_at':'original'}})
    monkeypatch.setattr(demo,'docker',lambda *args:(_ for _ in ()).throw(subprocess.CalledProcessError(1,['docker','volume','inspect'])))
    with pytest.raises(ValueError,match='Used volume missing'):saved.check_volumes()


def test_recreated_volume_same_name_is_not_original(saved,monkeypatch):
    demo.write(saved.root/'used-volumes.json',{saved.project+'_alpha-control':{'created_at':'original'}})
    monkeypatch.setattr(demo,'docker',lambda *args:json.dumps([{'CreatedAt':'replacement','Labels':{'com.docker.compose.project':saved.project}}]))
    with pytest.raises(ValueError,match='replaced'):saved.check_volumes()


def test_used_project_without_volume_marker_refused(saved):
    demo.write(saved.root/'agents-start-intent.json',{})
    with pytest.raises(ValueError,match='marker missing'):saved.check_volumes()


def test_lost_setup_marker_never_provisions_used_keys(saved):
    demo.write(saved.root/'agents-start-intent.json',{})
    with pytest.raises(ValueError,match='setup marker missing'):saved.check_material()


def test_modified_private_material_refused(saved,monkeypatch):
    demo.write(saved.root/'material.json',{'keyfile':'old'})
    monkeypatch.setattr(demo,'material',lambda root:{'keyfile':'different'})
    with pytest.raises(ValueError,match='material changed'):saved.check_material()


def test_stage16_manifest_does_not_authorize_other_project(saved):
    demo.write(saved.root/'stage16.json',{'project':'main'})
    with pytest.raises(ValueError,match='Dedicated demo project'):LegacyDemo(saved.root)
