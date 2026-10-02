"""Explicit offline trust and authenticated sessions for governance tests."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import AuthManager
from src import mobs_reviewer_authorization as authorization

INSTALLATION = "14141414-1414-4141-8141-141414141414"


def install_trust(monkeypatch, tmp_path, source, username="reviewer", *, database=True):
    auth_path = tmp_path / "fixture-auth.json"
    auth_path.write_text(json.dumps({"users": {username: {
        "created": 123.0, "is_admin": True, "password_hash": "unused-test-password-hash"}}}), encoding="utf-8")
    manager = AuthManager(str(auth_path))
    token = manager.create_session_trusted(username)
    statement = "Test fixture founder explicitly authorizes this account and scope to review snapshots."
    binding = {"format_version": 1, "installation_id": INSTALLATION, "authorization": {
        "id": "fixture-founder-binding", "version": 1, "state": "active",
        "account": authorization.account_identity(str(auth_path), username),
        "scope": {"institutional_root": str(Path(source).resolve()), "categories": ["Código"],
                  "authority_paths": [p.relative_to(source).as_posix() for p in Path(source).rglob("*.md")]},
        "approval": {"issuer": "founder", "reference": "fixture-only-approved-decision-v1",
                     "statement": statement, "statement_sha256": hashlib.sha256(statement.encode()).hexdigest()}}}
    path = tmp_path / "fixture-reviewer-binding.json"
    state = SimpleNamespace(path=path, binding=binding, manager=manager, token=token, username=username)
    def repin():
        data = (json.dumps(state.binding, sort_keys=True) + "\n").encode()
        path.write_bytes(data)
        monkeypatch.setattr(authorization, "_ANCHOR", authorization.TrustAnchor(
            str(path), hashlib.sha256(data).hexdigest(), INSTALLATION))
    state.repin = repin
    repin()
    monkeypatch.setenv("AUTH_ENABLED", "true")
    if database:
        import core.database as db
        engine = create_engine(f"sqlite:///{tmp_path / 'review-fixture.sqlite'}", connect_args={"check_same_thread": False})
        db.Base.metadata.create_all(engine)
        monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=engine))
        state.engine = engine
    return state


def authenticated_actor(state):
    app = FastAPI()
    app.state.auth_manager = state.manager
    request = Request({"type": "http", "app": app, "headers": [
        (b"cookie", f"odysseus_session={state.token}".encode())], "state": {"current_user": state.username}})
    return authorization.human_reviewer(request)


def install_junior_operational_profile(monkeypatch, tmp_path, *, self_development_preauthorized=False):
    """Pin the only provisioned promotion policy used by governance tests."""
    policy = {"format_version": 1, "installation_id": INSTALLATION, "id": "fixture-junior",
              "version": 2 if self_development_preauthorized else 1,
              "state": "active", "mode": "junior",
              "promotion_result": "human_approval_required"}
    if self_development_preauthorized:
        policy["self_development_promotion_result"] = "preauthorized"
    path = tmp_path / "fixture-junior-policy.json"
    raw = (json.dumps(policy, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    monkeypatch.setenv("MOBS_PROMOTION_STORE", str(tmp_path / "promotion-store"))
    monkeypatch.setenv("MOBS_OPERATIONAL_AUTHORITY_FILE", str(path))
    monkeypatch.setenv("MOBS_OPERATIONAL_AUTHORITY_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setenv("ODYSSEUS_INSTALLATION_ID", INSTALLATION)
    return policy


def attach_review(request, state):
    """Boot unit tests start from an explicitly persisted human decision."""
    from src.mobs_mandate_builder import _snapshot_id, save_authority_review
    review = {"snapshot_id": _snapshot_id(request["source"], request["authorities"]),
              "reviewer": state.username, "status": "consistent",
              "authorization": authorization.authorize_reviewer(request, authenticated_actor(state)),
              "institutional_scope": {key: request[key] for key in ("source", "category", "authorities")}}
    save_authority_review(review)
    request["review_record"] = review
    return request
