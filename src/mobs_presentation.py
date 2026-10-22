"""Read-only projection of existing institutional state for the product shell.

This module neither resumes runs nor records decisions. Presentation eligibility
is advisory: the existing action handlers still revalidate every exact reference.
"""
from __future__ import annotations

import json
import os
import re
import hashlib
import difflib
from pathlib import Path

from src.mobs_mandate_builder import (
    load_proposal, load_authority_review, proposal_summary,
    validate_authority_snapshot, validate_execution_review, capture_repository,
)
from src.mobs_reviewer_authorization import human_reviewer, authorize_reviewer


TEXTLESS_ACTIONS = {"review", "approve", "cancel", "promote"}
PREVIEW_FILE_BYTES = 64 * 1024


def _sealed_text_preview(artifact, target):
    """Read bounded, exact sealed bytes; no target writes or execution helpers."""
    _inspect_sealed_files(artifact, target)
    directory = Path(os.environ["MOBS_PROMOTION_STORE"]).resolve(strict=True) / artifact["id"]
    effects = artifact.get("effects") or [artifact]
    files = []
    for index, effect in enumerate(effects):
        if effect.get("effect") not in {"write", "create"}:
            raise ValueError("Unsupported effect")
        prefix = f"-{index}" if artifact.get("effects") else ""
        texts = {}
        for label, filename, expected in (
            ("after", f"content{prefix}.bin", effect["content_sha256"]),
            ("before", f"preimage{prefix}.bin", effect.get("preimage_sha256")),
        ):
            if label == "before" and effect["effect"] == "create":
                texts[label] = ""
                continue
            path = directory / filename
            if path.is_symlink() or not path.is_file():
                raise ValueError("Evidence unavailable")
            with path.open("rb") as stream:
                content = stream.read(PREVIEW_FILE_BYTES + 1)
            if len(content) > PREVIEW_FILE_BYTES or hashlib.sha256(content).hexdigest() != expected:
                raise ValueError("Evidence unavailable or too large")
            text = content.decode("utf-8")
            if "\x00" in text or len(text.splitlines()) > 2000:
                raise ValueError("Unsupported preview")
            texts[label] = text
        diff = '\n'.join(difflib.unified_diff(texts['before'].splitlines(), texts['after'].splitlines(),
                    fromfile='antes/' + effect['path'], tofile='depois/' + effect['path'], lineterm=''))
        files.append({"path": effect["path"], "effect": effect["effect"],
                      "before": texts["before"], "after": texts["after"], "diff": diff,
                      "content_sha256": effect["content_sha256"],
                      "preimage_sha256": effect.get("preimage_sha256")})
    return files


def _inspect_sealed_files(artifact, target):
    """Verify existing files without the execution helper's mkdir side effect."""
    from src.mobs_controlled_promotion import _file_digest, _require_separate_runtime, _self_development_target
    _require_separate_runtime(target)
    if _self_development_target(target) != artifact.get("self_development", False):
        raise ValueError("Target identity changed")
    raw = Path(os.environ.get("MOBS_PROMOTION_STORE", ""))
    if not raw.is_absolute() or not raw.is_dir() or raw.is_symlink():
        raise ValueError("Store unavailable")
    root = raw.resolve(strict=True)
    if root.is_relative_to(target.resolve(strict=True)) or not re.fullmatch(r"[0-9a-f]{32}", artifact["id"]):
        raise ValueError("Invalid store binding")
    directory = root / artifact["id"]
    if directory.is_symlink() or not directory.is_dir() or not directory.resolve(strict=True).is_relative_to(root):
        raise ValueError("Invalid sealed directory")
    effects = artifact.get("effects")
    if effects is not None and (artifact.get("format_version") != 2 or len(effects) != 2):
        raise ValueError("Invalid cardinality")
    for i, effect in enumerate(effects or [artifact]):
        prefix = f"-{i}" if effects else ""
        checks = [(f"content{prefix}.bin", effect["content_sha256"])]
        if effect["effect"] == "write":
            checks.append((f"preimage{prefix}.bin", effect["preimage_sha256"]))
        for filename, digest in checks:
            path = directory / filename
            if path.is_symlink() or not path.is_file() or _file_digest(path) != digest:
                raise ValueError("Sealed evidence unavailable")


def complete_textless_action(action, payload):
    """Only explicit, fully identified decisions may bypass text requirements."""
    if action not in TEXTLESS_ACTIONS or not isinstance(payload, dict):
        return False
    fields = ("mobs_promotion_id", "mobs_promotion_digest") if action == "promote" else (
        "mobs_proposal_id", "mobs_proposal_digest", "mobs_authority_snapshot")
    return isinstance(payload.get("session"), str) and bool(payload["session"].strip()) and all(
        isinstance(payload.get(key), str) and payload[key].strip() for key in fields)


def session_presentation(session_id, request, preview_reference=None):
    from core.database import SessionLocal, MobsPromotion
    from src import agent_runs
    from src.mobs_controlled_promotion import (
        _load_artifact, _policy, _self_development_target,
        _assert_target_not_quarantined, _verify_target_inventory,
        promotion_summary,
    )

    result = {"session_id": session_id, "active": agent_runs.is_active(session_id),
              "validity": "valid", "proposal": None, "reviewed": False, "reviewer_available": False,
              "actions": [], "promotions": []}
    try:
        proposal = load_proposal(session_id)
        if proposal is None:
            return result
        result["proposal"] = proposal_summary(proposal)
        result["workspace"] = proposal["target"]["path"]
        try:
            validate_authority_snapshot(proposal)
            if capture_repository(proposal["target"]["path"]) != proposal["target"]:
                raise ValueError("Target drift")
        except Exception:
            # Preserve attributable historical records without claiming freshness.
            result["validity"] = "unavailable"
        actor = None
        try:
            if result["validity"] != "valid":
                raise ValueError("Unverified state")
            actor = human_reviewer(request)
            authorization = authorize_reviewer(proposal, actor)
            review = load_authority_review(proposal["authority_snapshot"], actor.username)
            if review is not None:
                validate_execution_review(proposal, review)
                result["reviewed"] = review["authorization"] == authorization
        except Exception:
            # Missing or revoked binding must not hide the pending proposal.
            actor = None
            result["reviewed"] = False
        result["reviewer_available"] = actor is not None
        result["proposal"]["authority_review"] = "consistent" if result["reviewed"] else "pending"
        if result["validity"] == "valid" and proposal["status"] == "pending" and not result["active"]:
            result["actions"] = ["cancel"]
            if actor is not None:
                result["actions"].insert(0, "approve" if result["reviewed"] else "review")
        result["continuity"] = ("active" if result["active"] else
            "unconfirmed" if proposal["status"] == "approved" else "recorded")
        with SessionLocal() as db:
            rows = db.query(MobsPromotion).filter(MobsPromotion.session_id == session_id).all()
            before_rows = [(r.id, r.status, r.artifact_json, r.outcome_json, r.approval_json) for r in rows]
            for row in rows:
                item = {"id": row.id, "status": row.status, "validity": "invalid", "actions": []}
                result["promotions"].append(item)
                try:
                    artifact = _load_artifact(row)
                    if (artifact["proposal_id"] != proposal["proposal_id"] or
                            artifact["proposal_digest"] != proposal["proposal_digest"] or
                            artifact["authority_snapshot"] != proposal["authority_snapshot"]):
                        continue
                    item.update(promotion_summary(artifact, row.status))
                    if row.status not in {"human_approval_required", "promotion_preauthorized"}:
                        item["validity"] = "historical"
                        continue
                    if result["validity"] != "valid" or proposal["status"] not in {"approved", "completed"}:
                        continue
                    target = Path(artifact["target_baseline"]["path"])
                    _assert_target_not_quarantined(db, target)
                    if (artifact["operational_policy"] != _policy() or
                            artifact["operational_policy"] != proposal["operational_authority_profile"] or
                            capture_repository(str(target)) != artifact["target_baseline"]):
                        continue
                    _verify_target_inventory(target, artifact["target_inventory_sha256"])
                    multi = bool(artifact.get("effects"))
                    _inspect_sealed_files(artifact, target)
                    if row.status == "promotion_preauthorized":
                        if (multi or not artifact.get("self_development") or
                                artifact["operational_policy"].get("self_development_result") != "preauthorized" or
                                not _self_development_target(target)):
                            continue
                    elif actor is None or not result["reviewed"]:
                        continue
                    review = load_authority_review(artifact["authority_snapshot"])
                    validate_execution_review(proposal, review)
                    if review["authorization"] != artifact["review_authorization"]:
                        continue
                    receipt = json.loads(row.outcome_json or "{}").get("validation") or {}
                    validated = (receipt.get("artifact_digest") == artifact["artifact_digest"] and
                        receipt.get("proposal_digest") == artifact["proposal_digest"] and
                        receipt.get("authority_snapshot") == artifact["authority_snapshot"] and
                        receipt.get("target_baseline") == artifact["target_baseline"] and
                        receipt.get("target_inventory_sha256") == artifact["target_inventory_sha256"] and
                        receipt.get("exit_code") == 0 and
                        receipt.get("boundary", {}).get("validated_artifact_digest") == artifact["artifact_digest"] and
                        receipt.get("boundary", {}).get("target_before_sha256") == artifact["target_inventory_sha256"] and
                        receipt.get("boundary", {}).get("target_after_sha256") == artifact["target_inventory_sha256"])
                    item.update(validity="valid", validated=validated)
                    if (preview_reference == (artifact["id"], artifact["artifact_digest"])
                            and not result["active"]):
                        try:
                            result["preview"] = {"validity": "valid", "session_id": session_id,
                                "promotion_id": artifact["id"], "artifact_digest": artifact["artifact_digest"],
                                "files": _sealed_text_preview(artifact, target)}
                        except (ValueError, OSError, UnicodeError, KeyError):
                            result["preview"] = {"validity": "unavailable"}
                    if not result["active"]:
                        item["actions"] = (["validate_promotion"] if multi or artifact.get("self_development") else [])
                        if row.status == "human_approval_required" and (
                                validated or not (multi or artifact.get("self_development"))):
                            item["actions"].append("promote")
                except Exception:
                    # Never return exception text: drift may concern unreadable paths.
                    item["validity"] = "invalid"
                    item["actions"] = []
            after_rows = db.query(MobsPromotion.id, MobsPromotion.status, MobsPromotion.artifact_json,
                                  MobsPromotion.outcome_json, MobsPromotion.approval_json).filter(
                                      MobsPromotion.session_id == session_id).all()
            if sorted(before_rows, key=lambda r: r[0]) != sorted(map(tuple, after_rows), key=lambda r: r[0]):
                raise ValueError("Concurrent promotion change")
            _assert_target_not_quarantined(db, Path(proposal["target"]["path"]))
        # A replaced proposal or concurrent lifecycle change invalidates this view.
        if result["validity"] == "valid" and (load_proposal(session_id) != proposal or
                capture_repository(proposal["target"]["path"]) != proposal["target"]):
            raise ValueError("Concurrent state change")
        if result["validity"] == "valid":
            validate_authority_snapshot(proposal)
    except Exception:
        result.update(validity="unavailable", reviewed=False, reviewer_available=False, actions=[])
        for item in result["promotions"]:
            item.update(validity="invalid", actions=[])
    result["active"] = agent_runs.is_active(session_id)
    if result["active"]:
        result["actions"] = []
        result["continuity"] = "active"
        for item in result["promotions"]:
            item["actions"] = []
    if preview_reference is not None:
        if (result["validity"] != "valid" or result["active"] or not any(
                p.get("validity") == "valid" and (p["id"], p.get("artifact_digest")) == preview_reference
                for p in result["promotions"])):
            result["preview"] = {"validity": "unavailable"}
        result.setdefault("preview", {"validity": "unavailable"})
    return result
