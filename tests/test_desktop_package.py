import json
import subprocess
from pathlib import Path
import pytest
from src import desktop_package as package


@pytest.fixture
def payload(tmp_path, monkeypatch):
    root=tmp_path/'package'; root.mkdir()
    for name in package.REQUIRED:
        p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'fixture payload')
    monkeypatch.setattr(package,'capture_source',lambda *a:{'head':'fixture','dirty':True,'files':{'src/a.py':'digest'}})
    return root


def test_manifest_verifies_all_payload_bytes_and_detects_extra_or_changed_file(payload):
    record=package.write_manifest(payload,Path('.'))
    assert package.verify_manifest(payload)==record
    (payload/'_internal/static/js/studioSources.js').write_text('changed')
    with pytest.raises(ValueError): package.verify_manifest(payload)


def test_missing_component_and_source_drift_fail_before_manifest(payload):
    with pytest.raises(ValueError,match='inputs changed'):
        package.write_manifest(payload,Path('.'),{'head':'different'})
    assert not (payload/package.MANIFEST).exists()
    (payload/package.REQUIRED[0]).unlink()
    with pytest.raises(ValueError,match='missing'): package.write_manifest(payload,Path('.'))


def test_source_capture_is_content_sensitive_and_omits_private_data(tmp_path):
    subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    (tmp_path/'src').mkdir(); (tmp_path/'src/a.py').write_text('one')
    (tmp_path/'.env').write_text('DO_NOT_CAPTURE=secret')
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','fixture'],check=True,capture_output=True)
    first=package.capture_source(tmp_path)
    assert first['dirty'] and set(first['files'])=={'src/a.py'}
    (tmp_path/'src/a.py').write_text('two')
    second=package.capture_source(tmp_path)
    assert first['source_digest']!=second['source_digest']
    assert 'secret' not in json.dumps(second)
