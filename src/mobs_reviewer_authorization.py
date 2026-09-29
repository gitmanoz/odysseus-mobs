"""Deployment-provisioned reviewer binding; never a browser setting or tool.

The founder-approved file and its SHA256 are provisioned out of band. Its
startup pin, not a claim in JSON, is the trust anchor. Hashes prove integrity,
not the biological identity of the founder who provisions the deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path


class ReviewerAuthorizationError(ValueError):
    pass


@dataclass(frozen=True)
class TrustAnchor:
    path: str
    sha256: str
    installation_id: str


# Read once at process startup. Request payloads, settings and subprocess
# environments cannot replace the running server's trust anchor.
_ANCHOR = TrustAnchor(os.getenv("MOBS_REVIEWER_BINDING_FILE", ""),
                      os.getenv("MOBS_REVIEWER_BINDING_SHA256", ""),
                      os.getenv("ODYSSEUS_INSTALLATION_ID", ""))


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _read_json(path: Path):
    if path.stat().st_size > 128_000:
        raise ReviewerAuthorizationError("Reviewer binding evidence exceeds limit")
    return json.loads(path.read_text(encoding="utf-8"))


def account_identity(auth_path: str, username: str) -> dict:
    """Use existing account incarnation metadata; never copy credentials."""
    try:
        realm = str(Path(auth_path).resolve(strict=True))
        name = username.strip().lower()
        account = _read_json(Path(realm))["users"][name]
        created = account["created"]
        if isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created):
            raise ValueError("Missing stable account incarnation")
        return {"realm": realm, "username": name, "created": created}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ReviewerAuthorizationError("Bound account is missing or has no stable identity") from exc


@dataclass(frozen=True)
class HumanReviewer:
    username: str
    realm: str
    account_digest: str
    _session_token: str | None = field(default=None, repr=False, compare=False)
    _auth_manager: object = field(default=None, repr=False, compare=False)


def human_reviewer(request) -> HumanReviewer:
    """Require a real existing cookie session, not owner attribution/bypass."""
    from core.middleware import INTERNAL_TOOL_HEADER
    from src.auth_helpers import _auth_disabled, get_current_user
    if (_auth_disabled() or getattr(request.state, "api_token", False)
            or request.headers.get(INTERNAL_TOOL_HEADER)):
        raise ReviewerAuthorizationError("A human authenticated session is required for MOBS review")
    manager = getattr(request.app.state, "auth_manager", None)
    if manager is None:
        raise ReviewerAuthorizationError("A human authenticated session is required for MOBS review")
    token = request.cookies.get("odysseus_session")
    username = manager.get_username_for_token(token)
    if not username or username != get_current_user(request):
        raise ReviewerAuthorizationError("A human authenticated session is required for MOBS review")
    identity = account_identity(manager.auth_path, username)
    return HumanReviewer(username, identity["realm"], _digest(identity), token, manager)


def _binding(proposal: dict) -> tuple[dict, str]:
    try:
        anchor = _ANCHOR
        if not anchor.path or not anchor.sha256 or not anchor.installation_id:
            raise ReviewerAuthorizationError("Institutional reviewer binding is not provisioned")
        uuid.UUID(anchor.installation_id)
        path = Path(anchor.path)
        if not path.is_absolute() or path.is_symlink():
            raise ReviewerAuthorizationError("Reviewer binding needs an external deployment path")
        path = path.resolve(strict=True)
        # This file must not be editable as part of either repository's mandate.
        for baseline in (proposal["source"], proposal.get("target", proposal["source"])):
            if path.is_relative_to(Path(baseline["path"]).resolve()):
                raise ReviewerAuthorizationError("Reviewer binding must be outside institutional and target workspaces")
        data = path.read_bytes()
        if len(data) > 128_000 or hashlib.sha256(data).hexdigest() != anchor.sha256:
            raise ReviewerAuthorizationError("Reviewer binding changed or has an invalid deployment pin")
        binding = json.loads(data)
        if type(binding["format_version"]) is not int or binding["format_version"] != 1 or binding["installation_id"] != anchor.installation_id:
            raise ReviewerAuthorizationError("Reviewer binding belongs to another installation")
        grant = binding["authorization"]
        if grant["state"] != "active":
            raise ReviewerAuthorizationError("Institutional reviewer authorization is revoked")
        if not isinstance(grant["id"], str) or not grant["id"].strip():
            raise ValueError("Missing authorization identity")
        if type(grant["version"]) is not int or grant["version"] < 1:
            raise ValueError("Invalid authorization version")
        approval = grant["approval"]
        if (approval["issuer"] != "founder" or not approval["reference"].strip()
                or not approval["statement"].strip()
                or approval["statement_sha256"] != hashlib.sha256(approval["statement"].encode()).hexdigest()):
            raise ReviewerAuthorizationError("Founder approval evidence is invalid")
        scope = grant["scope"]
        if any(not isinstance(scope[key], list) or not scope[key]
               or any(not isinstance(value, str) or not value.strip() for value in scope[key])
               for key in ("categories", "authority_paths")):
            raise ReviewerAuthorizationError("Invalid institutional reviewer scope")
        for name in scope["authority_paths"]:
            candidate = Path(name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ReviewerAuthorizationError("Invalid institutional authority path")
        if (Path(scope["institutional_root"]).resolve() != Path(proposal["source"]["path"]).resolve()
                or proposal["category"] not in scope["categories"]
                or not set(proposal["authorities"]).issubset(scope["authority_paths"])):
            raise ReviewerAuthorizationError("Reviewer authorization is incompatible with institutional scope")
        account = grant["account"]
        if account_identity(account["realm"], account["username"]) != account:
            raise ReviewerAuthorizationError("Bound account identity has changed")
        return grant, anchor.sha256
    except ReviewerAuthorizationError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ReviewerAuthorizationError("Invalid institutional reviewer binding") from exc


def _authorization_reference(proposal: dict, reviewer: HumanReviewer) -> dict:
    grant, digest = _binding(proposal)
    account = grant["account"]
    if (reviewer.username != account["username"] or reviewer.realm != account["realm"]
            or reviewer.account_digest != _digest(account)):
        raise ReviewerAuthorizationError("Authenticated reviewer has no institutional binding")
    return {"id": grant["id"], "version": grant["version"], "binding_sha256": digest,
            "installation_id": _ANCHOR.installation_id, "account_digest": reviewer.account_digest,
            "account": account, "approval_reference": grant["approval"]["reference"]}


def authorize_reviewer(proposal: dict, reviewer: HumanReviewer) -> dict:
    # A typed identity alone is not authentication. Revalidate the existing
    # session at the decision boundary; tokens never enter review JSON/ledger.
    from core.auth import AuthManager
    if (not isinstance(reviewer, HumanReviewer) or not isinstance(reviewer._auth_manager, AuthManager)
            or not reviewer._session_token
            or Path(reviewer._auth_manager.auth_path).resolve() != Path(reviewer.realm)
            or reviewer._auth_manager.get_username_for_token(reviewer._session_token) != reviewer.username):
        raise ReviewerAuthorizationError("A human authenticated reviewer is required")
    return _authorization_reference(proposal, reviewer)


def validate_review_authorization(proposal: dict, review: dict) -> None:
    """Revocation, substitution or account reincarnation never upgrades a review."""
    try:
        evidence = review["authorization"]
        account = evidence["account"]
        reviewer = HumanReviewer(review["reviewer"], account["realm"], evidence["account_digest"])
        if _authorization_reference(proposal, reviewer) != evidence:
            raise ReviewerAuthorizationError("Reviewer authorization version has changed; a new review is required")
    except ReviewerAuthorizationError:
        raise
    except (KeyError, TypeError) as exc:
        raise ReviewerAuthorizationError("Review has no institutional authorization evidence; a new review is required") from exc


def main():
    """Offline provisioning only. Creating a file does not enable it in a server."""
    parser = argparse.ArgumentParser(description="Prepare a founder-confirmed MOBS reviewer binding offline")
    parser.add_argument("--output", required=True)
    parser.add_argument("--auth-file", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--institutional-root", required=True)
    parser.add_argument("--category", action="append", required=True)
    parser.add_argument("--authority-path", action="append", required=True)
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--approval-evidence-file", required=True)
    parser.add_argument("--founder-confirmed", action="store_true", required=True)
    args = parser.parse_args()
    uuid.UUID(args.installation_id)
    if args.version < 1:
        parser.error("version must be positive")
    output = Path(args.output).resolve()
    root = Path(args.institutional_root).resolve(strict=True)
    if output.is_relative_to(root):
        parser.error("output must be outside the institutional repository")
    for name in args.authority_path:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not (root / path).resolve().is_relative_to(root):
            parser.error("authority paths must be relative and confined")
        if not (root / path).is_file():
            parser.error("authority path does not exist")
    statement = Path(args.approval_evidence_file).read_text(encoding="utf-8").strip()
    if not statement or not args.approval_reference.strip():
        parser.error("explicit founder approval evidence is required")
    binding = {"format_version": 1, "installation_id": args.installation_id, "authorization": {
        "id": args.authorization_id, "version": args.version, "state": "active",
        "account": account_identity(args.auth_file, args.username),
        "scope": {"institutional_root": str(root), "categories": args.category,
                  "authority_paths": args.authority_path},
        "approval": {"issuer": "founder", "reference": args.approval_reference, "statement": statement,
                     "statement_sha256": hashlib.sha256(statement.encode()).hexdigest()}}}
    data = (json.dumps(binding, indent=2, ensure_ascii=False) + "\n").encode()
    with output.open("xb") as handle:
        handle.write(data)
    print("Prepared offline; inspect and pin in deployment configuration before restarting the server.")
    print("MOBS_REVIEWER_BINDING_FILE=" + str(output))
    print("MOBS_REVIEWER_BINDING_SHA256=" + hashlib.sha256(data).hexdigest())
    print("ODYSSEUS_INSTALLATION_ID=" + args.installation_id)


if __name__ == "__main__":
    main()
