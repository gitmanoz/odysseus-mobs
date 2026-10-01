"""Adversarial HTTP tests against the existing chat route and real persistence.

Only session/context preparation and model output are isolated. Governance,
repository evidence, database transitions, HTTP parsing and the loop are real.
"""
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.test_mobs_mandate_builder import projects, git
from src.mobs_mandate_builder import build_proposal, load_proposal, proposal_reference


def event(response, kind):
    assert response.status_code == 200, response.text
    for line in response.text.splitlines():
        if line.startswith("data: {"):
            value = json.loads(line[6:])
            if value.get("type") == kind:
                return value["data"]
    raise AssertionError(response.text)


@pytest.fixture
def chat(projects, tmp_path, monkeypatch):
    import core.database as database
    from routes import chat_routes as routes
    import src.agent_loop as loop
    source, target = projects
    monkeypatch.setenv("MOBS_INSTITUTIONAL_ROOT", str(source))
    from tests.mobs_reviewer_support import install_trust
    trust = install_trust(monkeypatch, tmp_path, source, username="founder", database=False)
    engine = create_engine(f"sqlite:///{tmp_path / 'chat.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(routes, "SessionLocal", factory)
    with factory() as db:
        db.add(database.Session(id="s", name="Test", model="fixture", endpoint_url="http://localhost/api/chat"))
        db.commit()
    sess = SimpleNamespace(model="fixture", name="Test", endpoint_url="http://localhost/api/chat",
                           headers={}, history=[], add_message=lambda value: None)
    manager = MagicMock()
    manager.get_session.return_value = sess
    monkeypatch.setattr(routes, "effective_user", lambda request: "founder")
    monkeypatch.setattr(routes, "get_current_user", lambda request: "founder")
    for name in ("_verify_session_owner", "_enforce_chat_privileges", "resolve_session_auth",
                 "_set_user_time_from_request", "_reconcile_selected_route_from_request", "_recover_empty_session_model"):
        monkeypatch.setattr(routes, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "_clear_orphaned_session_endpoint", lambda *args, **kwargs: False)
    monkeypatch.setattr(routes, "_is_image_generation_session", lambda *args, **kwargs: False)
    monkeypatch.setattr(routes, "get_session_mode", lambda session: "chat")
    monkeypatch.setattr(routes, "set_session_mode", lambda *args: None)
    monkeypatch.setattr(routes, "run_post_response_tasks", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "save_assistant_response", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.tool_security.owner_is_admin_or_single_user", lambda owner: True)
    monkeypatch.setattr("src.settings.get_setting", lambda key, default=None: default)
    monkeypatch.setattr(loop, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(loop, "get_mcp_manager", lambda: None)
    async def context(*args, **kwargs):
        return SimpleNamespace(messages=[{"role": "user", "content": kwargs["message"]}],
                               user="founder", preset=SimpleNamespace(temperature=None, max_tokens=1024, character_name=None),
                               preprocessed=SimpleNamespace(attachment_meta=[]), auto_opened_docs=[], uploaded_files=[],
                               web_sources=[], rag_sources=[], used_memories=[], was_compacted=False,
                               context_trimmed=False, context_length=32768, uprefs={})
    monkeypatch.setattr(routes, "build_chat_context", context)
    model_calls = []
    async def model(*args, **kwargs):
        model_calls.append((args, kwargs))
        yield 'data: {"delta":"observed"}\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, "stream_llm_with_fallback", model)
    monkeypatch.setattr(routes, "stream_llm_with_fallback", model)
    app = FastAPI()
    app.state.auth_manager = trust.manager
    @app.middleware("http")
    async def authenticate(request, call_next):
        request.state.current_user = trust.manager.get_username_for_token(request.cookies.get("odysseus_session"))
        request.state.api_token = request.headers.get("authorization", "").startswith("Bearer ")
        return await call_next(request)
    app.include_router(routes.setup_chat_routes(manager, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()))
    client = TestClient(app)
    client.cookies.set("odysseus_session", trust.token)
    def post(action=None, proposal=None, workspace_first=False, **extras):
        payload = {"message": "Inspect the code.", "session": "s", "workspace": str(target)}
        if action:
            payload["mobs_action"] = action
        if action == "propose" and not workspace_first:
            payload.update(mobs_category="Código", mobs_profile="read_only")
        if proposal:
            payload.update({"mobs_" + key: value for key, value in proposal_reference(proposal).items()})
        payload.update(extras)
        return client.post("/api/chat_stream", json=payload)
    yield SimpleNamespace(post=post, source=source, target=target, factory=factory, client=client,
                          model_calls=model_calls, trust=trust, app=app)
    client.close()
    engine.dispose()


def propose(chat):
    return event(chat.post("propose"), "mobs_mandate_proposal")


def test_workspace_first_proposal_reaches_route_without_client_category_or_authority_root(chat):
    proposal = event(chat.post("propose", workspace_first=True), "mobs_mandate_proposal")
    stored = load_proposal("s")
    assert proposal["category"] == "Código"
    assert proposal["profile"] == "read_only"
    assert stored["source"]["path"] == str(chat.source.resolve())
    assert stored["category"] == "Código"


def test_browser_cannot_replace_institutional_root_with_another_valid_workspace(chat, tmp_path):
    alternate = tmp_path / "alternate-mobs"
    shutil.copytree(chat.source, alternate)
    response = chat.post(
        "propose",
        workspace_first=True,
        mobs_authority_workspace=str(alternate),
        mobs_category="Código",
    )
    assert response.status_code == 400
    assert "cannot replace trusted MOBS proposal state" in response.text
    assert load_proposal("s") is None


def test_workspace_first_ambiguous_request_returns_clarification_without_proposal(chat):
    response = chat.post("propose", workspace_first=True, message="Ayla, faça isso.")
    clarification = event(response, "mobs_clarification_required")
    assert "needs clarification" in clarification["message"]


def test_workspace_first_bug_fix_derives_governed_development_proposal(chat, monkeypatch, tmp_path):
    from tests.mobs_reviewer_support import install_junior_operational_profile
    install_junior_operational_profile(monkeypatch, tmp_path)
    proposal = event(
        chat.post("propose", workspace_first=True, message="Ayla, corrija este bug no código."),
        "mobs_mandate_proposal",
    )
    assert proposal["category"] == "Código"
    assert proposal["profile"] == "development"
    assert proposal["promotion_eligible"] is True


def test_propose_review_approve_executes_real_loop_and_records_events(chat):
    p = propose(chat)
    assert p["profile"] == "read_only"
    assert p["allowed_operations"] == ["read"]
    assert p["capabilities"]["allowed_commands"] == []
    assert p["capabilities"]["creation_paths"] == []
    event(chat.post("review", p), "mobs_authority_reviewed")
    assert load_proposal("s")["status"] == "pending"
    response = chat.post("approve", p, use_research=True, compare_mode=True, plan_mode=True)
    assert response.status_code == 200, response.text
    assert "institutional_boot" in response.text
    assert "institutional_verified" in response.text
    assert "observed" in response.text
    assert load_proposal("s")["status"] == "completed"
    from core.database import MobsExecution
    with chat.factory() as db:
        ledger = json.loads(db.get(MobsExecution, "s").ledger_json)
    assert [item["action"] for item in ledger if "action" in item] == ["review", "approve"]
    assert all(item["proposal_digest"] == p["proposal_digest"] for item in ledger if "action" in item)


def test_approval_cannot_create_review_and_failed_action_does_not_change_state(chat):
    p = propose(chat)
    response = chat.post("approve", p)
    assert response.status_code == 400
    assert "has not been reviewed" in response.text
    assert load_proposal("s")["status"] == "pending"
    assert load_proposal("s")["authority_review"] == "pending"


@pytest.mark.parametrize("action", ["review", "approve", "cancel"])
def test_replaced_proposal_rejects_old_presented_action(chat, action):
    old = propose(chat)
    event(chat.post("review", old), "mobs_authority_reviewed")
    current = propose(chat)
    assert old["proposal_id"] != current["proposal_id"]
    assert old["authority_snapshot"] == current["authority_snapshot"]
    assert chat.post(action, old).status_code == 400
    assert load_proposal("s")["proposal_id"] == current["proposal_id"]
    assert load_proposal("s")["status"] == "pending"


@pytest.mark.parametrize("key", ["mobs_proposal_id", "mobs_proposal_digest", "mobs_authority_snapshot"])
def test_action_rejects_altered_client_identity(chat, key):
    p = propose(chat)
    assert chat.post("review", p, **{key: "0" * 64}).status_code == 400
    assert load_proposal("s")["status"] == "pending"


@pytest.mark.parametrize("key,value", [
    ("allowed_paths", ["../other/**"]), ("allowed_tools", ["bash"]),
    ("allowed_commands", ["git push"]), ("authority_review", "consistent"),
    ("source", {}), ("target", {}), ("approvals", {"delete": "approved"}),
    ("mobs_execution", {"authority_review": "consistent"}), ("mobs_project_profile", "python"),
])
def test_browser_cannot_replace_trusted_state_or_capabilities(chat, key, value):
    p = propose(chat)
    assert chat.post("review", p, **{key: value}).status_code == 400
    assert load_proposal("s")["proposal_digest"] == p["proposal_digest"]


@pytest.mark.parametrize("drift", ["authority", "source_commit", "target"])
def test_drift_invalidates_corresponding_action(chat, drift):
    p = propose(chat)
    event(chat.post("review", p), "mobs_authority_reviewed")
    if drift == "authority":
        (chat.source / "PROJECT_RULES.md").write_text("# changed authority\n", encoding="utf-8")
    elif drift == "source_commit":
        git(chat.source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "drift")
    else:
        (chat.target / "src/app.py").write_text("changed\n", encoding="utf-8")
    assert chat.post("approve", p).status_code == 400
    if drift != "target":
        assert chat.post("review", p).status_code == 400
    assert load_proposal("s")["status"] == "pending"


@pytest.mark.parametrize("field", ["allowed_paths", "authority_documents", "request", "project_profile"])
def test_persisted_proposal_tampering_is_rejected_by_route(chat, field):
    from core.database import MobsExecution
    p = propose(chat)
    with chat.factory() as db:
        row = db.get(MobsExecution, "s")
        altered = json.loads(row.proposal_json)
        altered[field] = ["../escape/**"] if field == "allowed_paths" else "altered"
        row.proposal_json = json.dumps(altered)
        db.commit()
    assert chat.post("review", p).status_code == 400


def test_route_rejects_persisted_older_capability_profile_even_with_matching_reference(chat):
    from core.database import MobsExecution
    from src import mobs_mandate_builder as builder

    propose(chat)
    with chat.factory() as db:
        row = db.get(MobsExecution, "s")
        old = json.loads(row.proposal_json)
        old["capability_profile_version"] = "1"
        old["capabilities"]["version"] = "1"
        old["proposal_digest"] = builder._proposal_digest(old)
        row.proposal_json = json.dumps(old)
        db.commit()
    assert chat.post("review", old).status_code == 400
    assert chat.post("approve", old).status_code == 400


def test_exact_snapshot_review_can_be_reused_but_never_mandate_approval(chat):
    p = propose(chat)
    event(chat.post("review", p), "mobs_authority_reviewed")
    current = propose(chat)
    assert current["status"] == "pending"
    response = chat.post("approve", current)
    assert response.status_code == 200, response.text
    assert "institutional_boot" in response.text
    assert chat.post("approve", current).status_code == 400


def test_cancel_requires_exact_identity_and_never_executes(chat):
    p = propose(chat)
    assert chat.post("cancel").status_code == 400
    event(chat.post("cancel", p), "mobs_mandate_cancelled")
    assert load_proposal("s")["status"] == "cancelled"
    assert chat.post("review", p).status_code == 400
    assert chat.post("approve", p).status_code == 400


def test_form_actions_cannot_replace_trusted_evidence(chat):
    p = propose(chat)
    payload = {"message": "Confirm", "session": "s", "mobs_action": "review", "authority_review": "consistent"}
    payload.update({"mobs_" + k: v for k, v in proposal_reference(p).items()})
    assert chat.client.post("/api/chat_stream", data=payload).status_code == 400


def test_common_chat_uses_existing_route_without_institutional_execution(chat):
    response = chat.post(message="hello")
    assert response.status_code == 200, response.text
    assert "observed" in response.text
    assert "institutional_" not in response.text
    assert load_proposal("s") is None


def test_approval_uses_saved_objective_and_target_instead_of_new_client_values(chat):
    p = propose(chat)
    event(chat.post("review", p), "mobs_authority_reviewed")
    result = chat.post("approve", p, message="Replace objective and permissions", workspace=str(chat.source))
    assert result.status_code == 200, result.text
    assert "institutional_verified" in result.text
    args, _ = chat.model_calls[-1]
    messages = args[1]
    assert messages[-1]["content"] == p["objective"]
    protected = next(message for message in messages if "MOBS INSTITUTIONAL CONTEXT" in message.get("content", ""))
    assert str(chat.target).replace("\\", "\\\\") in protected["content"]


def test_current_canonical_mop_produces_minimal_read_only_proposal(projects):
    canonical = Path(os.environ.get("MOBS_CANONICAL_REPOSITORY", Path(__file__).resolve().parents[2] / "missao-mobs"))
    if not (canonical / "PROJECT_INDEX.md").exists():
        pytest.skip("Canonical local M.O.P checkout is not configured")
    _, target = projects
    p = build_proposal("Inspect code", target_workspace=str(target), authority_workspace=str(canonical), category="Código")
    assert not (canonical / "docs/mobs/governance/AGENT_RUNTIME_INTEGRATION.md").exists()
    assert set(p["authorities"]) == {"PROJECT_INDEX.md", "AI_CONTEXT.md", "PROJECT_RULES.md",
                                     "project/automation/future/AGENT_RUNTIME_INTEGRATION.md"}


def test_canonical_mop_discovery_reaches_loop_through_real_chat_route(chat, monkeypatch):
    canonical = Path(os.environ.get("MOBS_CANONICAL_REPOSITORY", Path(__file__).resolve().parents[2] / "missao-mobs"))
    if not (canonical / "PROJECT_INDEX.md").exists():
        pytest.skip("Canonical local M.O.P checkout is not configured")
    monkeypatch.setenv("MOBS_INSTITUTIONAL_ROOT", str(canonical))
    p = event(chat.post("propose"), "mobs_mandate_proposal")
    assert "project/automation/future/AGENT_RUNTIME_INTEGRATION.md" in p["authority_evidence"]["authorities"]
    chat.trust.binding["authorization"]["scope"] = {
        "institutional_root": str(canonical.resolve()), "categories": ["Código"],
        "authority_paths": list(p["authority_evidence"]["authorities"])}
    chat.trust.repin()
    event(chat.post("review", p), "mobs_authority_reviewed")
    result = chat.post("approve", p)
    assert result.status_code == 200, result.text
    assert "institutional_boot" in result.text
    assert "institutional_verified" in result.text


def test_review_for_other_authenticated_reviewer_cannot_be_reused(chat, monkeypatch):
    from routes import chat_routes
    p = propose(chat)
    event(chat.post("review", p), "mobs_authority_reviewed")
    monkeypatch.setattr(chat_routes, "effective_user", lambda request: "other-admin")
    assert chat.post("approve", p).status_code == 400
    assert load_proposal("s")["status"] == "pending"


def test_concurrent_replacement_cannot_consume_old_review(chat, monkeypatch):
    import src.mobs_mandate_builder as builder
    p = propose(chat)
    original = builder.review_authority_snapshot
    def replace_during_validation(proposal, reviewer):
        result = original(proposal, reviewer)
        replacement = builder.build_proposal("Different scope", target_workspace=str(chat.target),
                                             authority_workspace=str(chat.source), category="Código")
        builder.save_proposal("s", replacement)
        return result
    monkeypatch.setattr(builder, "review_authority_snapshot", replace_during_validation)
    result = chat.post("review", p)
    assert result.status_code == 400, result.text
    assert "concurrently" in result.text
    assert load_proposal("s")["proposal_id"] != p["proposal_id"]
    assert builder.load_authority_review(p["authority_snapshot"]) is None
