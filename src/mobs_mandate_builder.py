"""Trusted construction and session persistence for reviewed MOBS mandates."""
from __future__ import annotations

import json
import os
import hashlib
import uuid
from pathlib import Path
from typing import Any

from src.mobs_institutional_boot import (
    InstitutionalBootError, _document, _required_authorities, authority_digest,
    capture_repository, institutional_boot,
)
from src.tool_execution import vet_workspace
from src.mobs_reviewer_authorization import (
    HumanReviewer, ReviewerAuthorizationError, authorize_reviewer, validate_review_authorization,
)


_READ_TOOLS = ["read_file", "ls", "grep", "glob", "get_workspace"]
_DEV_TOOLS = _READ_TOOLS + ["write_file", "edit_file", "apply_patch", "bash"]
_DEV_COMMANDS = ["pytest", "python -m pytest"]
CAPABILITY_PROFILE_VERSION = "2"
_GODOT_DIRECTORIES = (
    "addons", "scripts", "scenes", "assets", "resources", "shaders", "tests", "docs",
    "art", "audio", "fonts", "materials", "models", "textures", "ui",
)


class MandateProposalError(ValueError):
    pass


def _workspace(path: str, label: str) -> str:
    resolved = vet_workspace(path or "")
    if not resolved:
        raise MandateProposalError(f"Invalid {label} workspace")
    return resolved


def _ordinary_root_entries(target: Path) -> tuple[list[str], list[str]]:
    directories, files = [], []
    for item in target.iterdir():
        if item.name in {".git", ".github", ".env"} or item.name.startswith("."):
            continue
        if item.is_dir() and not item.is_symlink():
            directories.append(item.name)
        elif item.is_file() and not item.is_symlink():
            files.append(item.name)
    return sorted(directories), sorted(files)


def derive_capabilities(target: Path, project_profile: str) -> dict[str, Any]:
    """Return fixed capabilities for a confirmed profile and real target paths."""
    if project_profile not in {"generic", "python", "godot"}:
        raise MandateProposalError("Unsupported project capability profile")
    directories, files = _ordinary_root_entries(target)
    if project_profile == "generic":
        paths = [f"{name}/**" for name in directories] + files
        if not paths:
            raise MandateProposalError("Generic project has no safe project paths")
        return {"project_profile": "generic", "version": CAPABILITY_PROFILE_VERSION,
                "allowed_paths": paths, "creation_paths": [f"{name}/**" for name in directories],
                "allowed_commands": list(_DEV_COMMANDS)}
    if project_profile == "python":
        paths = [f"{name}/**" for name in ("src", "tests", "docs") if (target / name).is_dir()]
        paths += [name for name in ("pyproject.toml", "setup.py", "setup.cfg", "tox.ini") if (target / name).is_file()]
        paths += [name for name in files if name.startswith("requirements") and name.endswith(".txt")]
        if not paths:
            raise MandateProposalError("Python profile found no supported project paths")
        return {"project_profile": "python", "version": CAPABILITY_PROFILE_VERSION,
                "allowed_paths": paths, "creation_paths": [p for p in paths if p.endswith("/**")],
                "allowed_commands": list(_DEV_COMMANDS)}
    if not (target / "project.godot").is_file():
        raise MandateProposalError("Godot profile requires project.godot")
    paths = ["project.godot"] + [f"{name}/**" for name in _GODOT_DIRECTORIES if (target / name).is_dir()]
    commands = list(_DEV_COMMANDS)
    return {"project_profile": "godot", "version": CAPABILITY_PROFILE_VERSION,
            "allowed_paths": paths, "creation_paths": [p for p in paths if p.endswith("/**")],
            "allowed_commands": commands}


def _authority_evidence(source: str, category: str, *, materialization: bool = False) -> tuple[dict, dict[str, str], dict[str, str]]:
    """Read the exact local authorities selected by Index for one category."""
    source_baseline = capture_repository(source)
    root = Path(source)
    index = _document(root, "PROJECT_INDEX.md")  # Must remain first.
    required = _required_authorities(index, category, materialization=materialization)
    documents = {"PROJECT_INDEX.md": index}
    for name in sorted(required - {"PROJECT_INDEX.md"}):
        documents[name] = _document(root, name)
    if capture_repository(source) != source_baseline:
        raise InstitutionalBootError("Institutional workspace changed while collecting evidence")
    return source_baseline, {name: authority_digest(content) for name, content in documents.items()}, documents


def _snapshot_id(source: dict, authorities: dict[str, str]) -> str:
    evidence = {"source": source, "authorities": dict(sorted(authorities.items()))}
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _proposal_digest(proposal: dict[str, Any]) -> str:
    # Lifecycle state is kept separately. All presented mandate, selection,
    # baseline, permissions and evidence belong to the immutable version.
    content = {key: value for key, value in proposal.items()
               if key not in {"proposal_digest", "status", "authority_review", "review_record"}
               and not key.startswith("_")}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def validate_proposal_identity(proposal: dict[str, Any]) -> None:
    version = proposal.get("capability_profile_version")
    capabilities = proposal.get("capabilities")
    if (version != CAPABILITY_PROFILE_VERSION or not isinstance(capabilities, dict)
            or capabilities.get("version") != version
            or capabilities.get("project_profile") != proposal.get("project_profile")):
        raise MandateProposalError("Capability profile version or permissions are incompatible; request a new proposal, review and approval")
    if not proposal.get("proposal_id") or proposal.get("proposal_digest") != _proposal_digest(proposal):
        raise MandateProposalError("Proposal version or permissions are invalid; request a new proposal")
    if proposal.get("promotion_eligible"):
        try:
            from src.mobs_controlled_promotion import operational_profile_identity
            if proposal.get("operational_authority_profile") != operational_profile_identity():
                raise MandateProposalError("Operational Authority Profile changed; request a new proposal and approval")
        except MandateProposalError:
            raise
        except Exception as exc:
            raise MandateProposalError("Operational Authority Profile is unavailable; promotion execution is blocked") from exc


def proposal_reference(proposal: dict[str, Any]) -> dict[str, str]:
    return {key: proposal[key] for key in ("proposal_id", "proposal_digest", "authority_snapshot")}


def build_proposal(
    user_request: str,
    *,
    target_workspace: str,
    authority_workspace: str | None,
    category: str,
    profile: str = "read_only",
    project_profile: str = "generic",
) -> dict[str, Any]:
    """Read local MOBS authorities and propose a fixed, non-escalating mandate.

    Category and profile are explicit UI choices.  No model output participates
    in authority review or permission selection.
    """
    if not isinstance(user_request, str) or not user_request.strip():
        raise MandateProposalError("MOBS proposal needs a user request")
    if not isinstance(category, str) or not category.strip():
        raise MandateProposalError("MOBS proposal needs an explicit category")
    if profile not in {"read_only", "development"}:
        raise MandateProposalError("Unsupported MOBS profile")
    target = _workspace(target_workspace, "target")
    source = _workspace(authority_workspace or os.getenv("MOBS_WORKSPACE", ""), "institutional")
    try:
        source_baseline, authorities, authority_documents = _authority_evidence(
            source, category.strip(), materialization=profile == "development")
        target_baseline = capture_repository(target)
    except InstitutionalBootError as exc:
        raise MandateProposalError(str(exc)) from exc

    capabilities = derive_capabilities(Path(target), project_profile)
    if profile == "read_only":
        execution = dict(
            allowed_paths=capabilities["allowed_paths"], allowed_tools=list(_READ_TOOLS),
            allowed_read_paths=capabilities["allowed_paths"],
            allowed_write_paths=[], allowed_create_paths=[],
            allowed_operations=["read"], allowed_commands=[],
            limits={"max_steps": 12, "time_limit_seconds": 600, "command_timeout_seconds": None},
            exclusions="No writes, shell commands, Git writes, deployment, publication, secrets, or mandate expansion.",
        )
    else:
        execution = dict(
            allowed_paths=capabilities["allowed_paths"], allowed_tools=list(_DEV_TOOLS),
            allowed_read_paths=capabilities["allowed_paths"],
            allowed_write_paths=capabilities["allowed_paths"],
            allowed_create_paths=capabilities["creation_paths"],
            allowed_operations=["read", "write", "create", "test", "lint", "typecheck", "build", "git_read"],
            allowed_commands=capabilities["allowed_commands"],
            limits={"max_steps": 24, "time_limit_seconds": 1800, "command_timeout_seconds": 300},
            exclusions="No deletion, Git writes, installation, deployment, publication, secrets, paths outside the target, or mandate expansion.",
        )
    capabilities = {**capabilities, "allowed_commands": execution["allowed_commands"],
                    "allowed_tools": execution["allowed_tools"], "allowed_operations": execution["allowed_operations"],
                    "allowed_read_paths": execution["allowed_read_paths"],
                    "allowed_write_paths": execution["allowed_write_paths"],
                    "allowed_create_paths": execution["allowed_create_paths"],
                    "creation_paths": capabilities["creation_paths"] if profile == "development" else []}
    operational_profile = None
    if profile == "development":
        try:
            from src.mobs_controlled_promotion import operational_profile_identity
            operational_profile = operational_profile_identity()
        except Exception as exc:
            raise MandateProposalError("Operational Authority Profile is unavailable; cannot propose promotion-eligible execution") from exc
    proposal = dict(
        proposal_id=uuid.uuid4().hex,
        request=user_request.strip(), source=source_baseline, target=target_baseline,
        mandate=user_request.strip(), objective=user_request.strip(),
        scope="Only the listed paths in the selected target project.", category=category.strip(),
        authorities=authorities, authority_documents=authority_documents,
        authority_snapshot=_snapshot_id(source_baseline, authorities),
        authority_review="pending", approval_required_operations=[], approvals={},
        status="pending", profile=profile, project_profile=project_profile,
        capability_profile_version=CAPABILITY_PROFILE_VERSION,
        # Development is deliberately private-first. Its file mutations must
        # return through the sealed promotion path, never the direct tools.
        promotion_eligible=profile == "development",
        operational_authority_profile=operational_profile,
        capabilities=capabilities, **execution,
    )
    proposal["proposal_digest"] = _proposal_digest(proposal)
    return proposal


def build_workspace_proposal(
    user_request: str,
    *,
    target_workspace: str,
    category: str | None = None,
    profile: str | None = None,
    project_profile: str | None = None,
) -> dict[str, Any]:
    """Build through the existing mandate path from trusted workspace-first inputs."""
    from src.mobs_workspace_boot import WorkspaceBootError, workspace_boot_inputs
    try:
        inputs = workspace_boot_inputs(
            user_request,
            target_workspace,
            category=category,
            profile=profile,
            project_profile=project_profile,
        )
    except WorkspaceBootError as exc:
        raise MandateProposalError(str(exc)) from exc
    return build_proposal(user_request, target_workspace=target_workspace, **inputs)


def proposal_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    summary = {key: proposal[key] for key in (
        "objective", "scope", "category", "allowed_paths", "allowed_read_paths",
        "allowed_write_paths", "allowed_create_paths", "allowed_tools",
        "allowed_operations", "allowed_commands", "exclusions", "limits",
        "approval_required_operations", "profile", "project_profile", "capability_profile_version",
        "promotion_eligible",
        "operational_authority_profile",
        "capabilities", "status", "authority_review", "authority_snapshot", "proposal_id", "proposal_digest",
    )}
    summary["authority_evidence"] = {
        "source": proposal["source"], "authorities": proposal["authorities"],
        "documents": proposal["authority_documents"],
    }
    return summary


def validate_authority_snapshot(proposal: dict[str, Any]) -> str:
    """Re-read the authorities; any changed baseline or document voids review."""
    validate_proposal_identity(proposal)
    try:
        current_source, current_hashes, _ = _authority_evidence(
            proposal["source"]["path"], proposal["category"],
            materialization=proposal["profile"] == "development")
    except (KeyError, InstitutionalBootError) as exc:
        raise MandateProposalError("Authority snapshot is invalid") from exc
    expected = proposal.get("authority_snapshot")
    if current_source != proposal.get("source") or current_hashes != proposal.get("authorities"):
        raise MandateProposalError("Authority snapshot has changed since review")
    actual = _snapshot_id(current_source, current_hashes)
    if not isinstance(expected, str) or actual != expected:
        raise MandateProposalError("Authority snapshot identifier is invalid")
    return actual


def review_authority_snapshot(proposal: dict[str, Any], reviewer: HumanReviewer) -> dict[str, Any]:
    """Record a human review; it cannot be supplied by a model or payload flag."""
    snapshot_id = validate_authority_snapshot(proposal)
    try:
        authorization = authorize_reviewer(proposal, reviewer)
    except ReviewerAuthorizationError as exc:
        raise MandateProposalError(str(exc)) from exc
    return {"snapshot_id": snapshot_id, "reviewer": reviewer.username, "status": "consistent",
            "authorization": authorization,
            "institutional_scope": {key: proposal[key] for key in ("source", "category", "authorities")}}


def validate_execution_review(proposal: dict, review: dict | None = None) -> dict:
    """Require the persisted human receipt, including its current delegation."""
    from core.database import MobsAuthorityReview, SessionLocal
    snapshot = _snapshot_id(proposal["source"], proposal["authorities"])
    receipt = review if review is not None else proposal.get("review_record")
    if not isinstance(receipt, dict) or receipt.get("status") != "consistent" or receipt.get("snapshot_id") != snapshot:
        raise MandateProposalError("Authority review does not match this snapshot")
    try:
        validate_review_authorization(proposal, receipt)
    except ReviewerAuthorizationError as exc:
        raise MandateProposalError(str(exc)) from exc
    db = SessionLocal()
    try:
        row = db.query(MobsAuthorityReview).filter(MobsAuthorityReview.snapshot_id == snapshot).first()
        if (row is None or row.status != "consistent" or row.reviewer != receipt.get("reviewer")
                or json.loads(row.snapshot_json) != receipt):
            raise MandateProposalError("Authority review is not a persisted human decision")
    finally:
        db.close()
    return receipt


def approved_execution(proposal: dict[str, Any], review: dict[str, Any] | None = None) -> dict[str, Any]:
    """Turn a human-approved stored proposal into the existing loop contract."""
    if proposal.get("status") != "approved":
        raise MandateProposalError("MOBS mandate has not been approved")
    if not isinstance(review, dict) or review.get("status") != "consistent":
        raise MandateProposalError("MOBS authority snapshot has not been reviewed")
    snapshot_id = validate_authority_snapshot(proposal)
    if review.get("snapshot_id") != snapshot_id:
        raise MandateProposalError("Authority review does not match this snapshot")
    candidate = dict(proposal)
    candidate["authority_review"] = "consistent"  # Derived only from stored human review.
    candidate["review_record"] = validate_execution_review(proposal, review)
    try:
        institutional_boot(candidate, candidate["target"]["path"])
    except InstitutionalBootError as exc:
        raise MandateProposalError(str(exc)) from exc
    return candidate


def _row(session_id: str):
    from core.database import MobsExecution, SessionLocal
    db = SessionLocal()
    return db, db.query(MobsExecution).filter(MobsExecution.session_id == session_id).first()


def save_authority_review(review: dict[str, Any]) -> None:
    validate_review_authorization(review["institutional_scope"], review)
    from core.database import MobsAuthorityReview, SessionLocal
    db = SessionLocal()
    try:
        row = db.query(MobsAuthorityReview).filter(MobsAuthorityReview.snapshot_id == review["snapshot_id"]).first()
        if row is None:
            db.add(MobsAuthorityReview(snapshot_id=review["snapshot_id"], snapshot_json=json.dumps(review),
                                       reviewer=review["reviewer"], status="consistent"))
            db.commit()
    finally:
        db.close()


def load_authority_review(snapshot_id: str, reviewer: str | None = None) -> dict[str, Any] | None:
    from core.database import MobsAuthorityReview, SessionLocal
    db = SessionLocal()
    try:
        row = db.query(MobsAuthorityReview).filter(MobsAuthorityReview.snapshot_id == snapshot_id).first()
        if not row or row.status != "consistent" or (reviewer is not None and row.reviewer != reviewer):
            return None
        review = json.loads(row.snapshot_json)
        try:
            validate_review_authorization(review["institutional_scope"], review)
        except (ReviewerAuthorizationError, KeyError):
            return None
        return review
    finally:
        db.close()


def save_proposal(session_id: str, proposal: dict[str, Any]) -> None:
    from core.database import MobsExecution
    db, row = _row(session_id)
    try:
        validate_proposal_identity(proposal)
        if row is None:
            row = MobsExecution(session_id=session_id, target_path=proposal["target"]["path"],
                                status="pending", proposal_json=json.dumps(proposal), ledger_json="[]")
            db.add(row)
        else:
            if row.status == "approved":
                raise MandateProposalError("An execution is active for this session")
            changed = db.query(MobsExecution).filter(
                MobsExecution.session_id == session_id, MobsExecution.status == row.status,
                MobsExecution.proposal_json == row.proposal_json).update(
                    {MobsExecution.target_path: proposal["target"]["path"],
                     MobsExecution.status: "pending", MobsExecution.proposal_json: json.dumps(proposal)},
                    synchronize_session=False)
            if changed != 1:
                raise MandateProposalError("Proposal changed concurrently; replacement rejected")
        db.commit()
    finally:
        db.close()


def load_proposal(session_id: str) -> dict[str, Any] | None:
    db, row = _row(session_id)
    try:
        if row is None:
            return None
        proposal = json.loads(row.proposal_json)
        proposal["status"] = row.status
        validate_proposal_identity(proposal)
        return proposal
    finally:
        db.close()


def apply_proposal_action(session_id: str, action: str, reference: dict[str, str], reviewer: HumanReviewer | str) -> dict:
    """Apply a human action to the exact presented version in one DB transaction.

    The conditional update also prevents a concurrent replacement/approval from
    consuming an action intended for another version. Client evidence is never
    used to assemble an execution.
    """
    from core.database import MobsExecution, MobsAuthorityReview
    db, row = _row(session_id)
    try:
        if row is None:
            raise MandateProposalError("No MOBS proposal for this session")
        original_json = row.proposal_json
        proposal = json.loads(original_json)
        proposal["status"] = row.status
        validate_proposal_identity(proposal)
        if reference != proposal_reference(proposal):
            raise MandateProposalError("Stale proposal or snapshot; request and review the current version")
        if row.status != "pending":
            raise MandateProposalError("MOBS proposal is no longer pending approval")
        if action not in {"review", "approve", "cancel"}:
            raise MandateProposalError("Invalid MOBS proposal action")
        review_row = None
        actor = reviewer.username if isinstance(reviewer, HumanReviewer) else reviewer
        if action == "review":
            result = review_authority_snapshot(proposal, reviewer)
            review_row = db.query(MobsAuthorityReview).filter(
                MobsAuthorityReview.snapshot_id == proposal["authority_snapshot"]).first()
        elif action == "approve":
            review_row = db.query(MobsAuthorityReview).filter(
                MobsAuthorityReview.snapshot_id == proposal["authority_snapshot"],
                MobsAuthorityReview.reviewer == actor,
                MobsAuthorityReview.status == "consistent").first()
            review = json.loads(review_row.snapshot_json) if review_row else None
            try:
                current_authorization = authorize_reviewer(proposal, reviewer)
                if review is not None and review.get("authorization") != current_authorization:
                    raise ReviewerAuthorizationError("Reviewer authorization version has changed; a new review is required")
            except ReviewerAuthorizationError as exc:
                raise MandateProposalError(str(exc)) from exc
            result = approved_execution({**proposal, "status": "approved"}, review)
        else:
            result = {**proposal_reference(proposal), "status": "cancelled"}
        status = {"review": "pending", "approve": "approved", "cancel": "cancelled"}[action]
        ledger = json.loads(row.ledger_json)
        decision = {"action": action, "actor": actor, **proposal_reference(proposal)}
        if action in {"review", "approve"}:
            decision["authorization"] = result["authorization"] if action == "review" else result["review_record"]["authorization"]
        ledger.append(decision)
        changed = db.query(MobsExecution).filter(
            MobsExecution.session_id == session_id, MobsExecution.status == "pending",
            MobsExecution.proposal_json == original_json).update(
                {MobsExecution.status: status, MobsExecution.ledger_json: json.dumps(ledger)},
                synchronize_session=False)
        if changed != 1:
            raise MandateProposalError("Proposal changed concurrently; action rejected")
        if action == "review":
            if review_row is None:
                db.add(MobsAuthorityReview(snapshot_id=result["snapshot_id"],
                                           snapshot_json=json.dumps(result), reviewer=actor, status="consistent"))
            else:
                review_row.snapshot_json = json.dumps(result)
                review_row.reviewer = actor
                review_row.status = "consistent"
            result = {**proposal_reference(proposal), **result}
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_status(session_id: str, status: str, ledger: list[dict] | None = None,
               *, proposal_id: str | None = None) -> None:
    if status not in {"pending", "approved", "cancelled", "completed", "blocked"}:
        raise MandateProposalError("Invalid MOBS execution status")
    db, row = _row(session_id)
    try:
        if row is None:
            raise MandateProposalError("No MOBS proposal for this session")
        if proposal_id is not None and json.loads(row.proposal_json).get("proposal_id") != proposal_id:
            raise MandateProposalError("Execution belongs to a replaced proposal")
        row.status = status
        if ledger is not None:
            row.ledger_json = json.dumps(json.loads(row.ledger_json) + ledger)
        db.commit()
    finally:
        db.close()
