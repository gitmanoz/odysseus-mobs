import asyncio
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import prefs_routes as prefs


def test_drafts_use_existing_preferences_owner_isolation_and_roundtrip(tmp_path,monkeypatch):
    monkeypatch.setattr(prefs,'PREFS_FILE',str(tmp_path/'prefs.json'))
    monkeypatch.setattr(prefs,'get_current_user',lambda request:request.headers.get('x-fixture-user'))
    app=FastAPI();app.include_router(prefs.setup_prefs_routes())
    client=TestClient(app);key='studio-task-draft-'+'a'*64
    value={'format':1,'kind':'bug','objective':'<script>literal private A</script>','acceptance':'known fixture'}
    assert client.put('/api/prefs/'+key,headers={'x-fixture-user':'A'},json={'value':value}).status_code==200
    assert client.get('/api/prefs/'+key,headers={'x-fixture-user':'A'}).json()['value']==value
    assert client.get('/api/prefs/'+key,headers={'x-fixture-user':'B'}).json()['value'] is None
    assert 'private A' not in client.get('/api/prefs',headers={'x-fixture-user':'B'}).text
    assert not (tmp_path/'prefs.json.tmp').exists()


def test_legacy_anonymous_drafts_do_not_leak_when_accounts_are_enabled(tmp_path,monkeypatch):
    path=tmp_path/'prefs.json';monkeypatch.setattr(prefs,'PREFS_FILE',str(path))
    path.write_text(json.dumps({'theme':'graphite','studio-task-draft-'+('a'*64):{'objective':'anonymous private'}}))
    assert prefs._load_for_user(None)['theme']=='graphite'
    assert 'anonymous private' not in json.dumps(prefs._load_for_user('new-user'))
    path.write_text('{broken')
    assert prefs._load_for_user('new-user')=={}
