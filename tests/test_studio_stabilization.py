"""Regression probes use only synthetic identities and disposable databases."""
import ast
import asyncio
from contextlib import contextmanager
from datetime import timedelta
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


def endpoint(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    node = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), namespace)
    return namespace[name]


@pytest.mark.parametrize('body', [{}, {'keep_count': False}, {'keep_count': -1}, {'keep_count': 1.5}, [], None])
def test_truncate_invalid_body_never_calls_mutation(body):
    calls = []
    async def json(): return body
    route = endpoint('routes/history/history_routes.py', 'truncate_session', {
        'Request': object, 'HTTPException': HTTPException,
        'logger': logging.getLogger('test'), '_verify_session_owner': lambda *a: None,
        'session_manager': SimpleNamespace(truncate_messages=lambda *a: calls.append(a)),
    })
    with pytest.raises(HTTPException) as failure:
        asyncio.run(route(SimpleNamespace(json=json), 'synthetic'))
    assert failure.value.status_code == 400
    assert calls == []


def test_generated_image_ownership_outage_fails_closed(monkeypatch):
    import core.database as database
    def unavailable(): raise RuntimeError('Synthetic DB outage')
    monkeypatch.setattr(database, 'SessionLocal', unavailable)
    request = SimpleNamespace(state=SimpleNamespace(current_user='synthetic-alice'))
    route = endpoint('app.py', 'serve_generated_image', {
        'Request': object, 'HTTPException': HTTPException,
        'resolve_generated_image_path': lambda _: 'synthetic.png',
        'logger': logging.getLogger('test'),
    })
    with pytest.raises(HTTPException) as failure:
        asyncio.run(route('synthetic.png', request))
    assert failure.value.status_code == 503


def test_cleanup_rechecks_durable_rows_before_deleting(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base, Session, ChatMessage, utcnow_naive
    import core.session_manager as manager_module
    import src.database as database
    from src import cleanup_service
    engine = create_engine('sqlite:///' + (tmp_path / 'synthetic.sqlite').as_posix())
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(manager_module, 'SessionLocal', factory)
    now = utcnow_naive()
    with factory() as db:
        for i in range(12):
            db.add(Session(id=f'recent-{i}', name='recent', model='fixture', endpoint_url='', created_at=now-timedelta(days=i), last_accessed=now, message_count=0))
        db.add(Session(id='stale', name='candidate', model='fixture', endpoint_url='', created_at=now-timedelta(days=90), last_accessed=now-timedelta(days=90), message_count=0, archived=True))
        db.flush()
        for i in range(30):
            db.add(ChatMessage(id=f'msg-{i}', session_id='stale', role='user', content='synthetic message', timestamp=now))
        db.commit()
    manager = manager_module.SessionManager.__new__(manager_module.SessionManager)
    manager.sessions = {}
    preview = asyncio.run(cleanup_service.get_cleanup_preview())
    assert all(s['id'] != 'stale' for s in preview['sessions_to_delete'])
    assert next(s for s in preview['preserved_sessions'] if s['id'] == 'stale')['message_count'] == 30
    assert asyncio.run(cleanup_service.cleanup_old_sessions(manager))[0] == 0
    manager.cleanup_empty_sessions()
    with factory() as db:
        assert db.query(Session).filter(Session.id == 'stale').one()
        assert db.query(ChatMessage).filter(ChatMessage.session_id == 'stale').count() == 30
    engine.dispose()


def test_reminder_copy_failure_never_stores_deleted_or_expunges():
    class Mail:
        def __init__(self): self.calls = []
        def select(self, folder): return 'OK', []
        def uid(self, command, *args):
            self.calls.append(command)
            return ('OK', [b'17']) if command == 'SEARCH' else ('NO', [b'Trash unavailable'])
        def expunge(self): self.calls.append('EXPUNGE')
    mail = Mail()
    @contextmanager
    def imap(*a, **kw): yield mail
    route = endpoint('routes/email_routes.py', 'delete_odysseus_reminder_emails', {
        'Query': lambda v: v, 'Depends': lambda v: v, 'require_owner': lambda: None,
        '_assert_owns_account': lambda *a: None, '_get_email_config': lambda *a, **kw: {},
        '_imap': imap, '_detect_sent_folder': lambda _: 'Sent', '_q': lambda s: s,
        '_invalidate_list_cache': lambda _: None, 'logger': logging.getLogger('test'),
    })
    result = asyncio.run(route(account_id=None, permanent=False, owner='synthetic'))
    assert 'COPY' in mail.calls
    assert 'STORE' not in mail.calls and 'EXPUNGE' not in mail.calls
    assert result['deleted'] == 0 and result['success'] is False


@pytest.mark.parametrize('message,expected', [('oi', True), ('olá', True), ('bom dia', True), ('oi execute os testes', False), ('olá, abra o arquivo', False)])
def test_portuguese_greeting_fast_path_preserves_real_requests(message, expected):
    from routes.chat_helpers import _is_casual_low_signal
    assert _is_casual_low_signal(message) is expected


def test_streaming_does_not_render_private_deliberation():
    source = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    start = source.index('// Model deliberation is not an operational event.')
    end = source.index('} else if (!hasUnclosedThink && isThinking)', start)
    block = source[start:end]
    assert 'thinking-content expanded' not in block
    assert '_liveThinkInner.innerHTML' not in block
    assert 'role="status"' in block


def test_obsolete_docker_publication_removed():
    assert not (ROOT / '.github/workflows/docker-publish.yml').exists()
