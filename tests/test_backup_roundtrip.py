"""Run existing backup CLI against disposable SQLite WAL/config only."""
import json
import sqlite3
from types import SimpleNamespace
from tests.helpers.cli_loader import load_script


def test_snapshot_restore_preserves_committed_wal_and_config(tmp_path, monkeypatch):
    backup = load_script('odysseus-backup')
    data = tmp_path/'data'; data.mkdir()
    monkeypatch.setattr(backup, '_REPO_ROOT', tmp_path)
    monkeypatch.setattr(backup, '_DATA_DIR', data)
    monkeypatch.setattr(backup, '_BACKUP_DIR', tmp_path/'backups')
    monkeypatch.setattr(backup, 'emit', lambda *a: None)
    db = sqlite3.connect(data/'sessions.db')
    db.execute('PRAGMA journal_mode=WAL'); db.execute('CREATE TABLE conversations(id TEXT, text TEXT)')
    db.execute('INSERT INTO conversations VALUES (?,?)', ('fixture','kept')); db.commit()
    (data/'settings.json').write_text(json.dumps({'theme':'graphite','fixture':True}))
    archive=tmp_path/'snapshot.tar.gz'
    backup.cmd_snapshot(SimpleNamespace(out=str(archive),include_research=False,include_attachments=False,pretty=False))
    db.close()
    (data/'settings.json').write_text('{}')
    backup.cmd_verify(SimpleNamespace(path=str(archive),pretty=False))
    backup.cmd_restore(SimpleNamespace(path=str(archive),yes=True,pretty=False))
    restored=sqlite3.connect(data/'sessions.db')
    assert restored.execute('PRAGMA integrity_check').fetchone()==('ok',)
    assert restored.execute('SELECT * FROM conversations').fetchall()==[('fixture','kept')]
    restored.close()
    assert json.loads((data/'settings.json').read_text())['theme']=='graphite'
    assert list(tmp_path.glob('data.before-restore-*'))
