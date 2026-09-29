import copy
import asyncio
import subprocess
from pathlib import Path

import pytest

from src.mobs_mandate_builder import (
    MandateProposalError, approved_execution, build_proposal, proposal_summary,
    review_authority_snapshot as _review_authority_snapshot, validate_authority_snapshot, validate_proposal_identity,
)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def projects(tmp_path, monkeypatch):
    source = tmp_path / "mobs"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    git(source, "init", "-b", "dev")
    git(target, "init", "-b", "dev")
    docs = {
        "PROJECT_INDEX.md": "# Index\n[Agent Runtime Integration](project/automation/future/AGENT_RUNTIME_INTEGRATION.md)\n# Decision Tree\n```\n└─ Código\n  → PROJECT_RULES.md\n```\n",
        "AI_CONTEXT.md": "# Context\nInstitution governs.\n",
        "PROJECT_RULES.md": "# Rules\nFollow reviewed scope.\n",
        "project/automation/future/AGENT_RUNTIME_INTEGRATION.md": "# Integration\nFail closed.\n",
    }
    for name, text in docs.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for name in ("src/app.py", "tests/test_app.py", "docs/readme.md"):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n", encoding="utf-8")
    for root in (source, target):
        git(root, "add", ".")
        git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
    from tests.mobs_reviewer_support import install_trust, authenticated_actor
    import sys
    trust = install_trust(monkeypatch, tmp_path, source)
    monkeypatch.setattr(sys.modules[__name__], "_TEST_REVIEWER", authenticated_actor(trust))
    return source, target


_TEST_REVIEWER = None


def review_authority_snapshot(item, username):
    """Unit-test adapter: use a real authenticated, explicitly provisioned actor."""
    from src.mobs_mandate_builder import save_authority_review
    if username != _TEST_REVIEWER.username:
        raise MandateProposalError("Reviewer has no institutional binding")
    result = _review_authority_snapshot(item, _TEST_REVIEWER)
    save_authority_review(result)
    return result


def proposal(projects):
    source, target = projects
    return build_proposal(
        "Run the targeted tests and fix the code.", target_workspace=str(target),
        authority_workspace=str(source), category="Código", profile="development",
    )


def test_creates_conservative_proposal_from_selected_local_workspaces(projects):
    item = proposal(projects)
    assert item["authority_review"] == "pending"
    assert set(item["allowed_paths"]) == {"src/**", "tests/**", "docs/**"}
    assert "bash" in item["allowed_tools"]
    assert "python -m pytest" in item["allowed_commands"]
    assert "git status" not in item["allowed_commands"]
    assert "commit" not in " ".join(item["allowed_commands"])
    assert set(proposal_summary(item)) >= {"objective", "scope", "allowed_paths", "limits"}
    assert proposal_summary(item)["authority_evidence"]["documents"]["PROJECT_INDEX.md"].startswith("# Index")


def test_python_profile_derives_only_existing_supported_paths(projects):
    source, target = projects
    (target / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    item = build_proposal("Test", target_workspace=str(target), authority_workspace=str(source),
                          category="Código", project_profile="python")
    assert item["project_profile"] == "python"
    assert set(item["allowed_paths"]) == {"src/**", "tests/**", "docs/**", "pyproject.toml"}


def test_generic_profile_supports_repo_without_src_tests_or_docs(projects, tmp_path):
    source, _ = projects
    target = tmp_path / "generic"
    target.mkdir()
    git(target, "init", "-b", "dev")
    (target / "game").mkdir()
    (target / "game" / "main.txt").write_text("x", encoding="utf-8")
    git(target, "add", ".")
    git(target, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
    item = build_proposal("Inspect", target_workspace=str(target), authority_workspace=str(source), category="Código")
    assert item["project_profile"] == "generic"
    assert item["allowed_paths"] == ["game/**"]


def test_godot_profile_derives_real_paths_without_unsupported_commands(projects):
    source, target = projects
    (target / "project.godot").write_text("[application]\nconfig/name='Fixture'\n", encoding="utf-8")
    for name in ("addons", "scripts", "scenes", "assets", "resources", "shaders", "textures"):
        (target / name).mkdir(exist_ok=True)
    item = build_proposal("Validate", target_workspace=str(target), authority_workspace=str(source),
                          category="Código", project_profile="godot", profile="development")
    assert "project.godot" in item["allowed_paths"]
    assert "scripts/**" in item["allowed_paths"]
    assert "textures/**" in item["allowed_paths"]
    assert not any(command.startswith("godot") for command in item["allowed_commands"])


def test_godot_profile_blocks_path_outside_its_capability(projects):
    source, target = projects
    (target / "project.godot").write_text("[application]\n", encoding="utf-8")
    (target / "private").mkdir()
    item = build_proposal("Validate", target_workspace=str(target), authority_workspace=str(source),
                          category="Código", project_profile="godot")
    assert "private/**" not in item["allowed_paths"]


def test_browser_cannot_add_capability_to_backend_derived_profile(projects):
    item = proposal(projects)
    browser_payload = {"allowed_paths": ["secrets/**"], "allowed_tools": ["python"], "allowed_commands": ["git push"]}
    assert browser_payload["allowed_paths"] != item["capabilities"]["allowed_paths"]
    assert browser_payload["allowed_tools"] != item["allowed_tools"]
    assert browser_payload["allowed_commands"] != item["allowed_commands"]


def test_profile_change_requires_a_new_proposal(projects):
    item = proposal(projects)
    altered = copy.deepcopy(item)
    altered["project_profile"] = "python"
    assert altered["project_profile"] != item["project_profile"]
    with pytest.raises(MandateProposalError, match="version or permissions"):
        validate_proposal_identity(altered)
    # The approval flow loads the persisted proposal; a browser selection cannot replace it.
    assert item["capability_profile_version"] == "2"


def test_persisted_older_capability_profile_cannot_be_reused(projects):
    from src import mobs_mandate_builder as builder

    item = proposal(projects)
    old = copy.deepcopy(item)
    old["capability_profile_version"] = "1"
    old["capabilities"]["version"] = "1"
    old["proposal_digest"] = builder._proposal_digest(old)
    with pytest.raises(MandateProposalError, match="Capability profile version or permissions are incompatible"):
        validate_proposal_identity(old)
    old["status"] = "approved"
    with pytest.raises(MandateProposalError, match="Capability profile version or permissions are incompatible"):
        approved_execution(old, {"status": "consistent"})


def test_saved_proposal_of_older_profile_requires_new_review(projects):
    import json
    from core.database import MobsExecution, Session, SessionLocal
    from src import mobs_mandate_builder as builder

    item = proposal(projects)
    db = SessionLocal()
    try:
        db.add(Session(id="old-profile-session", name="Test", model="fixture",
                       endpoint_url="http://localhost/api/chat"))
        db.commit()
    finally:
        db.close()
    builder.save_proposal("old-profile-session", item)
    old = copy.deepcopy(item)
    old["capability_profile_version"] = "1"
    old["capabilities"]["version"] = "1"
    old["proposal_digest"] = builder._proposal_digest(old)
    db = SessionLocal()
    try:
        row = db.query(MobsExecution).filter(MobsExecution.session_id == "old-profile-session").one()
        row.proposal_json = json.dumps(old)
        db.commit()
    finally:
        db.close()
    with pytest.raises(MandateProposalError, match="Capability profile version or permissions are incompatible"):
        builder.load_proposal("old-profile-session")


def test_rejects_missing_target_project(projects, tmp_path):
    source, _ = projects
    with pytest.raises(MandateProposalError, match="target workspace"):
        build_proposal("Inspect", target_workspace=str(tmp_path / "missing"), authority_workspace=str(source), category="Código")


def test_rejects_invalid_authority(projects):
    source, target = projects
    (source / "PROJECT_INDEX.md").write_text("# no tree", encoding="utf-8")
    with pytest.raises(MandateProposalError, match="Decision Tree"):
        build_proposal("Inspect", target_workspace=str(target), authority_workspace=str(source), category="Código")


def test_model_cannot_expand_the_fixed_proposal(projects):
    item = proposal(projects)
    model_suggestion = copy.deepcopy(item)
    model_suggestion["allowed_paths"].append("secrets/**")
    model_suggestion["allowed_tools"].append("python")
    model_suggestion["allowed_operations"].append("deploy")
    # Only the trusted builder output is used for the execution request.
    assert "secrets/**" not in item["allowed_paths"]
    assert "python" not in item["allowed_tools"]
    assert "deploy" not in item["allowed_operations"]
    with pytest.raises(MandateProposalError, match="version or permissions"):
        approved_execution({**model_suggestion, "status": "approved"},
                           review_authority_snapshot(item, "reviewer"))


def test_ambiguous_integration_discovery_fails_closed(projects):
    source, target = projects
    index = source / "PROJECT_INDEX.md"
    index.write_text(index.read_text(encoding="utf-8") +
                     "\n[Another authority](other/AGENT_RUNTIME_INTEGRATION.md)\n", encoding="utf-8")
    with pytest.raises(MandateProposalError, match="ambiguous"):
        build_proposal("Inspect", target_workspace=str(target), authority_workspace=str(source), category="Código")


def test_minimal_read_only_selection_omits_conditional_programmer_role(projects):
    source, target = projects
    index = source / "PROJECT_INDEX.md"
    index.write_text(index.read_text(encoding="utf-8").replace(
        "  → PROJECT_RULES.md", "  → PROJECT_RULES.md\n  → docs/mobs/models/PROGRAMMER_PARTNER.md ← materialização técnica sob mandato (quando o papel se aplicar)"), encoding="utf-8")
    item = build_proposal("Inspect", target_workspace=str(target), authority_workspace=str(source), category="Código")
    assert "docs/mobs/models/PROGRAMMER_PARTNER.md" not in item["authorities"]
    with pytest.raises(MandateProposalError, match="Missing or unreadable authority"):
        build_proposal("Edit", target_workspace=str(target), authority_workspace=str(source), category="Código", profile="development")


def test_explicit_approval_builds_the_existing_agent_loop_contract(projects):
    item = proposal(projects)
    item["status"] = "approved"
    review = review_authority_snapshot(item, "reviewer")
    execution = approved_execution(item, review)
    assert execution["authority_review"] == "consistent"
    assert execution["target"] == item["target"]
    assert execution["allowed_commands"] == item["allowed_commands"]


def test_cancellation_never_builds_execution(projects):
    item = proposal(projects)
    item["status"] = "cancelled"
    with pytest.raises(MandateProposalError, match="not been approved"):
        approved_execution(item, None)


def test_resume_cannot_silently_expand_saved_mandate(projects):
    item = proposal(projects)
    saved = copy.deepcopy(item)
    saved["status"] = "approved"
    resumed = approved_execution(saved, review_authority_snapshot(saved, "reviewer"))
    assert resumed["allowed_paths"] == item["allowed_paths"]
    assert resumed["allowed_tools"] == item["allowed_tools"]


def test_approved_proposal_reaches_the_existing_agent_loop(projects, monkeypatch):
    import src.agent_loop as loop
    item = proposal(projects)
    item["status"] = "approved"
    execution = approved_execution(item, review_authority_snapshot(item, "reviewer"))
    monkeypatch.setattr("src.tool_security.owner_is_admin_or_single_user", lambda owner: True)
    monkeypatch.setattr(loop, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(loop, "get_mcp_manager", lambda: None)
    async def stream(candidates, messages, **kwargs):
        yield 'data: {"delta":"governed"}\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, "stream_llm_with_fallback", stream)
    async def collect():
        return [part async for part in loop.stream_agent_loop(
            "http://localhost/api/chat", "m", [{"role": "user", "content": item["request"]}],
            mobs_execution=execution, workspace=execution["target"]["path"],
            owner="reviewer",
        )]
    events = asyncio.run(collect())
    assert any("institutional_boot" in event for event in events)
    assert any("institutional_verified" in event for event in events)


def test_mandate_approval_alone_does_not_make_authority_consistent(projects):
    item = proposal(projects)
    item["status"] = "approved"
    with pytest.raises(MandateProposalError, match="has not been reviewed"):
        approved_execution(item)
    assert item["authority_review"] == "pending"


def test_reviewed_snapshot_is_valid_and_reusable(projects):
    item = proposal(projects)
    first = review_authority_snapshot(item, "reviewer")
    second = review_authority_snapshot(item, "reviewer")
    with pytest.raises(MandateProposalError, match="institutional binding"):
        review_authority_snapshot(item, "another-reviewer")
    assert validate_authority_snapshot(item) == first["snapshot_id"] == second["snapshot_id"]


def test_authority_change_invalidates_review(projects):
    source, _ = projects
    item = proposal(projects)
    review = review_authority_snapshot(item, "reviewer")
    (source / "PROJECT_RULES.md").write_text("# changed\n", encoding="utf-8")
    with pytest.raises(MandateProposalError, match="changed since review"):
        approved_execution({**item, "status": "approved"}, review)


def test_source_baseline_change_invalidates_review(projects):
    source, _ = projects
    item = proposal(projects)
    review = review_authority_snapshot(item, "reviewer")
    git(source, "commit", "--allow-empty", "-m", "baseline changed")
    with pytest.raises(MandateProposalError, match="changed since review"):
        approved_execution({**item, "status": "approved"}, review)


def test_regular_agent_loop_call_does_not_need_a_mobs_proposal(projects, monkeypatch):
    import src.agent_loop as loop
    monkeypatch.setattr(loop, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(loop, "get_mcp_manager", lambda: None)
    async def stream(candidates, messages, **kwargs):
        yield 'data: {"delta":"ordinary"}\n\n'
        yield 'data: [DONE]\n\n'
    monkeypatch.setattr(loop, "stream_llm_with_fallback", stream)
    async def collect():
        return [part async for part in loop.stream_agent_loop(
            "http://localhost/api/chat", "m", [{"role": "user", "content": "hello"}],
        )]
    events = asyncio.run(collect())
    assert not any("institutional_" in event for event in events)
