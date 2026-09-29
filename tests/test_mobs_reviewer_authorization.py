"""Authorization adversaries use the real route, SQL persistence and cookie validator."""
import asyncio
import hashlib
import json
import subprocess
import sys

import pytest

from tests.test_mobs_chat_identity import chat, propose, event
from tests.test_mobs_mandate_builder import projects
from tests.mobs_reviewer_support import authenticated_actor
from src import mobs_reviewer_authorization as authorization
from src.mobs_mandate_builder import (
    apply_proposal_action, load_authority_review, load_proposal, proposal_reference,
    review_authority_snapshot, MandateProposalError,
)


def test_founder_binding_records_identity_version_and_separate_decisions(chat):
    p = propose(chat)
    reviewed = event(chat.post("review", p), "mobs_authority_reviewed")
    evidence = reviewed["authorization"]
    assert evidence["installation_id"] == authorization._ANCHOR.installation_id
    assert evidence["account"]["created"] == 123.0
    assert evidence["version"] == 1
    assert load_proposal("s")["status"] == "pending"
    assert load_proposal("s")["authority_review"] == "pending"
    assert load_authority_review(p["authority_snapshot"], "founder")["authorization"] == evidence
    with chat.factory() as db:
        from core.database import MobsExecution
        ledger = json.loads(db.get(MobsExecution, "s").ledger_json)
    assert ledger[-1]["authorization"] == evidence
    assert chat.post("approve", p).status_code == 200


@pytest.mark.parametrize("failure", ["missing", "admin_without_binding", "category", "repository",
                                     "authorities", "revoked", "installation", "approval", "invalid_scope"])
def test_rejects_insufficient_institutional_authorization(chat, monkeypatch, failure):
    p = propose(chat)
    grant = chat.trust.binding["authorization"]
    if failure == "missing":
        monkeypatch.setattr(authorization, "_ANCHOR", authorization.TrustAnchor("", "", ""))
    else:
        if failure == "admin_without_binding":
            chat.trust.manager._config["users"]["other"] = {"created": 456.0, "is_admin": True}
            chat.trust.manager._save()
            grant["account"] = authorization.account_identity(chat.trust.manager.auth_path, "other")
        elif failure == "category":
            grant["scope"]["categories"] = ["Branding"]
        elif failure == "repository":
            grant["scope"]["institutional_root"] = str(chat.target)
        elif failure == "authorities":
            grant["scope"]["authority_paths"] = ["PROJECT_INDEX.md"]
        elif failure == "revoked":
            grant["state"] = "revoked"
        elif failure == "installation":
            chat.trust.binding["installation_id"] = "other-installation"
        elif failure == "approval":
            grant["approval"]["statement"] = "An unauthorized changed claim"
        else:
            grant["scope"]["categories"] = "Código"
        chat.trust.repin()
    response = chat.post("review", p)
    assert response.status_code == 400, response.text
    assert "blocked" in response.text
    assert load_authority_review(p["authority_snapshot"]) is None
    assert load_proposal("s")["status"] == "pending"
    assert not chat.model_calls


@pytest.mark.parametrize("change", ["revoked", "version", "scope", "recreated", "deleted", "installation"])
def test_prior_review_is_not_inherited_after_authorization_change(chat, change):
    p = propose(chat)
    old = event(chat.post("review", p), "mobs_authority_reviewed")
    grant = chat.trust.binding["authorization"]
    if change == "recreated":
        chat.trust.manager._config["users"]["founder"]["created"] = 456.0
        chat.trust.manager._save()
    elif change == "deleted":
        del chat.trust.manager._config["users"]["founder"]
        chat.trust.manager._save()
    else:
        if change == "revoked":
            grant["state"] = "revoked"
        elif change == "version":
            grant["version"] += 1
        elif change == "scope":
            grant["scope"]["categories"] = ["Branding"]
        else:
            chat.trust.binding["installation_id"] = "other-installation"
        chat.trust.repin()
    assert load_authority_review(p["authority_snapshot"], "founder") is None
    assert chat.post("approve", p).status_code in {400, 403}
    if change == "version":
        new = event(chat.post("review", p), "mobs_authority_reviewed")
        assert new["snapshot_id"] == old["snapshot_id"]
        assert new["authorization"]["version"] == 2
        assert new["authorization"] != old["authorization"]
        assert chat.post("approve", p).status_code == 200
    else:
        assert chat.post("review", p).status_code in {400, 403}


@pytest.mark.parametrize("mode", ["anonymous", "api", "internal_tool", "auth_disabled"])
def test_automatic_or_unauthenticated_call_cannot_record_human_review(chat, monkeypatch, mode):
    p = propose(chat)
    payload = {"message": "Inspect", "session": "s", "workspace": str(chat.target), "mobs_action": "review",
               **{"mobs_" + key: value for key, value in proposal_reference(p).items()}}
    headers = {}
    if mode == "anonymous":
        chat.client.cookies.clear()
    elif mode == "api":
        headers["Authorization"] = "Bearer automated-client"
    elif mode == "internal_tool":
        headers["X-Odysseus-Internal-Token"] = "automated-tool-attribution"
    else:
        monkeypatch.setenv("AUTH_ENABLED", "false")
    response = chat.client.post("/api/chat_stream", json=payload, headers=headers)
    assert response.status_code == 403
    assert "human authenticated" in response.text
    assert load_authority_review(p["authority_snapshot"]) is None


@pytest.mark.parametrize("key", ["authorization", "review_record", "reviewer_binding", "installation_id",
                                 "account", "founder_approval", "authorization_version", "mobs_reviewer_binding"])
def test_client_cannot_provision_authority(chat, key):
    p = propose(chat)
    assert chat.post("review", p, **{key: {"state": "active", "issuer": "founder"}}).status_code == 400
    assert load_authority_review(p["authority_snapshot"]) is None


def test_changing_file_or_request_environment_cannot_replace_startup_pin(chat, monkeypatch):
    p = propose(chat)
    chat.trust.binding["authorization"]["scope"]["categories"].append("Branding")
    data = json.dumps(chat.trust.binding).encode()
    chat.trust.path.write_bytes(data)
    monkeypatch.setenv("MOBS_REVIEWER_BINDING_SHA256", hashlib.sha256(data).hexdigest())
    assert chat.post("review", p).status_code == 400
    assert load_authority_review(p["authority_snapshot"]) is None


def test_username_or_fabricated_receipt_is_insufficient(chat):
    p = propose(chat)
    with pytest.raises(MandateProposalError, match="human authenticated"):
        review_authority_snapshot(load_proposal("s"), "founder")
    identity = authorization.account_identity(chat.trust.manager.auth_path, "founder")
    forged = authorization.HumanReviewer("founder", identity["realm"], authorization._digest(identity))
    with pytest.raises(MandateProposalError, match="human authenticated"):
        review_authority_snapshot(load_proposal("s"), forged)
    from src.mobs_institutional_boot import institutional_boot, InstitutionalBootError
    request = {**load_proposal("s"), "status": "approved", "authority_review": "consistent"}
    with pytest.raises(InstitutionalBootError, match="review"):
        institutional_boot(request, str(chat.target))


def test_legacy_review_does_not_gain_authorization_retroactively(chat):
    p = propose(chat)
    from core.database import MobsAuthorityReview
    with chat.factory() as db:
        db.add(MobsAuthorityReview(snapshot_id=p["authority_snapshot"], reviewer="founder", status="consistent",
            snapshot_json=json.dumps({"snapshot_id": p["authority_snapshot"], "reviewer": "founder", "status": "consistent"})))
        db.commit()
    assert load_authority_review(p["authority_snapshot"]) is None
    assert chat.post("approve", p).status_code == 400
    event(chat.post("review", p), "mobs_authority_reviewed")
    assert chat.post("approve", p).status_code == 200


def test_binding_inside_target_is_not_trusted(chat, monkeypatch):
    p = propose(chat)
    path = chat.target / "local-binding.json"
    data = chat.trust.path.read_bytes()
    path.write_bytes(data)
    monkeypatch.setattr(authorization, "_ANCHOR", authorization.TrustAnchor(
        str(path), hashlib.sha256(data).hexdigest(), authorization._ANCHOR.installation_id))
    response = chat.post("review", p)
    assert response.status_code == 400
    assert "outside institutional and target" in response.text


def test_runtime_and_resume_revalidate_authorization(chat, monkeypatch):
    p = propose(chat)
    event(chat.post("review", p), "mobs_authority_reviewed")
    execution = apply_proposal_action("s", "approve", proposal_reference(p), authenticated_actor(chat.trust))
    from src import agent_runs
    monkeypatch.setattr(agent_runs, "is_active", lambda session: True)
    async def subscribe(session):
        yield "data: [DONE]\n\n"
    monkeypatch.setattr(agent_runs, "subscribe", subscribe)
    assert chat.client.get("/api/chat/resume/s").status_code == 200
    chat.trust.binding["authorization"]["state"] = "revoked"
    chat.trust.repin()
    assert chat.client.get("/api/chat/resume/s").status_code == 403
    import src.agent_loop as loop
    async def collect():
        return [part async for part in loop.stream_agent_loop(
            "http://localhost/api/chat", "fixture", [{"role": "user", "content": "Inspect"}],
            mobs_execution=execution, workspace=str(chat.target), owner="founder")]
    events = asyncio.run(collect())
    assert any("institutional_blocked" in part for part in events)
    assert not any("institutional_boot" in part for part in events)
    assert not chat.model_calls


def test_authorization_revoked_between_rounds_blocks_continuity(chat, monkeypatch):
    import src.agent_loop as loop
    p = propose(chat)
    event(chat.post("review", p), "mobs_authority_reviewed")
    async def model(*args, **kwargs):
        yield 'data: {"delta":"observed"}\n\n'
        chat.trust.binding["authorization"]["state"] = "revoked"
        chat.trust.repin()
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, "stream_llm_with_fallback", model)
    response = chat.post("approve", p)
    assert response.status_code == 200
    assert "institutional_boot" in response.text
    assert "institutional_blocked" in response.text
    assert "institutional_verified" not in response.text
    assert load_proposal("s")["status"] == "blocked"


def test_offline_provisioning_creates_file_but_does_not_enable_server(chat, tmp_path):
    before = authorization._ANCHOR
    output = tmp_path / "offline-candidate.json"
    evidence = tmp_path / "founder-confirmation.txt"
    evidence.write_text("Fixture founder explicitly approves this exact account, installation and scope.", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "src.mobs_reviewer_authorization", "--output", str(output),
        "--auth-file", chat.trust.manager.auth_path, "--username", "founder",
        "--installation-id", before.installation_id, "--authorization-id", "offline-v2", "--version", "2",
        "--institutional-root", str(chat.source), "--category", "Código", "--authority-path", "PROJECT_INDEX.md",
        "--approval-reference", "fixture-approved-v2", "--approval-evidence-file", str(evidence),
        "--founder-confirmed"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert authorization._ANCHOR == before
    assert "password_hash" not in output.read_text()
    assert "pin in deployment configuration" in result.stdout
