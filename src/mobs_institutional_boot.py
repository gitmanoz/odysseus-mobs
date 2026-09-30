from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class InstitutionalBootError(ValueError):
    """A governed execution must stop; never fall back to ordinary chat."""


_READ_ONLY_TOOLS = frozenset({"read_file", "ls", "grep", "glob", "get_workspace"})
_MUTATING_TOOLS = frozenset({"write_file", "edit_file", "apply_patch"})
_SHELL_TOOLS = frozenset({"bash"})
_SUPPORTED_TOOLS = _READ_ONLY_TOOLS | _MUTATING_TOOLS | _SHELL_TOOLS
_HIGH_IMPACT_OPERATIONS = frozenset({
    "delete", "publish", "deploy", "force_push", "credentials",
    "outside_project", "mandate_expansion",
})
_SECRET_PATH = re.compile(
    r"(?:^|/)(?:\.?env(?:\.[^/]*)?|secrets?|credentials?|passwords?|tokens?)(?:/|$)",
    re.IGNORECASE,
)
_SHELL_METACHARACTERS = re.compile(r"[\r\n;&|><`$%^!]")


def _command_tokens(value: Any, label: str) -> tuple[str, ...]:
    if (not isinstance(value, str) or not value.strip() or "\\" in value or ":" in value
            or _SHELL_METACHARACTERS.search(value)):
        raise InstitutionalBootError(f"Invalid {label}")
    try:
        tokens = tuple(shlex.split(value, posix=True))
    except ValueError as exc:
        raise InstitutionalBootError(f"Invalid {label}") from exc
    if not tokens or any(not token or token.startswith("/") or re.match(r"^[A-Za-z]:", token) for token in tokens):
        raise InstitutionalBootError(f"Invalid {label}")
    for token in tokens:
        if token == ".." or ".." in token.replace("\\", "/").split("/"):
            raise InstitutionalBootError(f"Invalid {label}")
    return tokens


def _shell_operation(tokens: tuple[str, ...]) -> str:
    """Closed local-development command grammar; a mandate can only narrow it."""
    program = tokens[0]
    args = tokens[1:]
    if program in {"pytest"} or tokens[:3] == ("python", "-m", "pytest"):
        return "test"
    if program == "ruff" and args and args[0] in {"check", "format"}:
        return "lint"
    if program in {"mypy", "pyright"}:
        return "typecheck"
    if program == "npm" and tuple(args[:2]) in {("test",), ("run", "lint"), ("run", "typecheck"), ("run", "build")}:
        return "build" if tuple(args[:2]) == ("run", "build") else ("test" if args[0] == "test" else "lint" if args[1] == "lint" else "typecheck")
    if program in {"godot", "godot4"} and tuple(args) == ("--headless", "--path", ".", "--editor", "--quit"):
        return "build"
    if program == "git":
        if not args:
            raise InstitutionalBootError("Git command is incomplete")
        if any(arg == "-C" or arg.startswith("-C") or arg == "-c" or arg.startswith("-c")
               or arg.startswith("--git-dir") or arg.startswith("--work-tree")
               or arg.startswith("--output") for arg in args):
            raise InstitutionalBootError("Git command may not change its repository or write output")
        if args[0] in {"status", "diff", "log", "show"}:
            return "git_read"
        if args[0] == "branch" and tuple(args[1:]) in {(), ("--show-current",)}:
            return "git_read"
        raise InstitutionalBootError("Git command is not read-only")
    raise InstitutionalBootError("Shell command is not in the local development allowlist")


def _command_allowed(tokens: tuple[str, ...], allowed: tuple[tuple[str, ...], ...]) -> bool:
    return any(tokens[:len(prefix)] == prefix for prefix in allowed)


def _portable_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value or ":" in value:
        raise InstitutionalBootError(f"Invalid {label}")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise InstitutionalBootError(f"{label} must be relative to the authorized project")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InstitutionalBootError(f"Invalid {label}")
    if any(part.endswith((".", " ")) or re.fullmatch(
            r"(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
            for part in parts):
        raise InstitutionalBootError(f"Invalid Windows {label}")
    return value


def _path_is_allowed(path: str, patterns: tuple[str, ...]) -> bool:
    from src.agent_tools.filesystem_tools import _glob_to_regex
    return any(_glob_to_regex(pattern).fullmatch(path) for pattern in patterns)


def _search_root_allowed(path: str, patterns: tuple[str, ...]) -> bool:
    """A search may only descend into a wholly approved subtree."""
    if not path:
        return "**" in patterns
    return "**" in patterns or any(
        pattern.endswith("/**") and
        (path == pattern[:-3] or path.startswith(pattern[:-3] + "/"))
        for pattern in patterns
    )


def _read_tool_path(content: str, tool: str) -> str:
    if tool == "get_workspace":
        return ""
    value = (content or "").strip()
    if value.startswith("{"):
        try:
            args = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InstitutionalBootError("Invalid read tool input") from exc
        if not isinstance(args, dict):
            raise InstitutionalBootError("Invalid read tool input")
        raw = args.get("path", "")
    elif tool in {"grep", "glob"}:
        raw = ""
    else:
        raw = value.split("\n", 1)[0]
    if raw in {"", "."} and tool != "read_file":
        return ""
    return _portable_path(raw, "read path")


def _tool_path(content: str, tool: str) -> str:
    """Parse the same path shapes accepted by the existing filesystem tools."""
    text = (content or "").strip()
    if text.startswith("{"):
        try:
            args = json.loads(text)
            if isinstance(args, dict) and "path" in args:
                return _portable_path(str(args["path"]), "tool path")
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if tool == "edit_file":
        raise InstitutionalBootError("edit_file requires a JSON path")
    return _portable_path((content or "").split("\n", 1)[0].strip(), "tool path")


def _write_tool_payload(content: str) -> tuple[str, str]:
    """Parse write_file without accepting model-controlled extra semantics."""
    try:
        value = json.loads((content or '').strip())
    except json.JSONDecodeError as exc:
        raise InstitutionalBootError('Promotion-private write_file requires JSON') from exc
    if not isinstance(value, dict) or set(value) != {'path', 'content'} or not isinstance(value['content'], str):
        raise InstitutionalBootError('Invalid promotion-private write_file payload')
    return _portable_path(value['path'], 'tool path'), value['content']


def _patch_paths(content: str) -> list[tuple[str, str]]:
    """Use the existing patch grammar so the authorizer and executor agree."""
    from src.agent_tools.filesystem_tools import _parse_agent_patch
    text = content or ""
    if text.strip().startswith("{"):
        try:
            args = json.loads(text)
            if isinstance(args, dict):
                text = str(args.get("patch_text") or args.get("patchText") or args.get("patch") or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    try:
        operations = _parse_agent_patch(text)
    except ValueError as exc:
        raise InstitutionalBootError(f"Invalid patch mandate input: {exc}") from exc
    if not operations:
        raise InstitutionalBootError("Patch has no file operations")
    return [(str(op["kind"]), _portable_path(op["path"], "patch path")) for op in operations]


def _working_tree_entries(root: Path) -> dict[str, str]:
    """A per-path snapshot used to distinguish this mutation from drift."""
    raw = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries: dict[str, str] = {}
    parts = raw.split(b"\0")
    index = 0
    while index < len(parts):
        entry = parts[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4:
            raise InstitutionalBootError("Invalid repository status evidence")
        state = entry[:2].decode("ascii", "strict")
        path = entry[3:].decode("utf-8", "surrogateescape").replace("\\", "/")
        if state[0] in {"R", "C"} or state[1] in {"R", "C"}:
            raise InstitutionalBootError("Rename/copy drift is unsupported in this slice")
        safe_path = _portable_path(path, "repository status path")
        candidate = root / safe_path
        digest = hashlib.sha256(state.encode("ascii"))
        if candidate.exists():
            if candidate.is_symlink() or not candidate.is_file():
                raise InstitutionalBootError("Non-regular changed path is unsupported in this slice")
            with candidate.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
        entries[safe_path] = digest.hexdigest()
    return entries


@dataclass(frozen=True)
class PendingMutation:
    tool: str
    paths: tuple[str, ...]
    operations: tuple[str, ...]
    before_entries: dict[str, str]


@dataclass(frozen=True)
class PendingCommand:
    command: str
    operation: str
    before_entries: dict[str, str]
    before_inventory: dict[str, str] | None = None
    boundary_policy: Any = None


@dataclass(frozen=True)
class ExecutionMandate:
    objective: str
    scope: str
    allowed_paths: tuple[str, ...]
    allowed_read_paths: tuple[str, ...]
    allowed_write_paths: tuple[str, ...]
    allowed_create_paths: tuple[str, ...]
    allowed_tools: frozenset[str]
    allowed_operations: frozenset[str]
    approval_required_operations: frozenset[str]
    approvals: dict[str, str]
    exclusions: str
    max_steps: int
    time_limit_seconds: int | None
    command_timeout_seconds: int | None
    allowed_commands: tuple[tuple[str, ...], ...]
    promotion_eligible: bool

    @classmethod
    def from_request(cls, request: dict) -> "ExecutionMandate":
        required = (
            "objective", "scope", "allowed_paths", "allowed_tools",
            "allowed_operations", "approval_required_operations", "approvals",
            "exclusions", "limits", "allowed_commands",
        )
        if any(name not in request for name in required):
            raise InstitutionalBootError("Executable mandate is incomplete")
        for name in ("objective", "scope", "exclusions"):
            if not isinstance(request[name], str) or not request[name].strip():
                raise InstitutionalBootError(f"Invalid mandate {name}")
        paths = request["allowed_paths"]
        if not isinstance(paths, list) or not paths:
            raise InstitutionalBootError("Mandate needs nonempty allowed_paths")
        allowed_paths = tuple(_portable_path(path, "allowed path") for path in paths)
        def permission_paths(key: str, fallback: list[str]) -> tuple[str, ...]:
            selected = request.get(key, fallback)
            if not isinstance(selected, list):
                raise InstitutionalBootError(f"Invalid {key}")
            resolved = tuple(_portable_path(path, key) for path in selected)
            if any(not any(parent == "**" or path == parent or
                           parent.endswith("/**") and path.startswith(parent[:-3] + "/")
                           for parent in allowed_paths) for path in resolved):
                raise InstitutionalBootError(f"{key} exceeds allowed_paths")
            return resolved
        read_paths = permission_paths("allowed_read_paths", paths)
        write_paths = permission_paths("allowed_write_paths", paths)
        create_paths = permission_paths("allowed_create_paths", paths)
        tools = request["allowed_tools"]
        if not isinstance(tools, list) or not tools or not all(isinstance(tool, str) for tool in tools):
            raise InstitutionalBootError("Mandate needs nonempty allowed_tools")
        allowed_tools = frozenset(tools)
        if not allowed_tools.issubset(_SUPPORTED_TOOLS):
            raise InstitutionalBootError("Mandate requests an unsupported tool")
        operations = request["allowed_operations"]
        if not isinstance(operations, list) or not operations or not all(isinstance(op, str) for op in operations):
            raise InstitutionalBootError("Mandate needs nonempty allowed_operations")
        approval_required = request["approval_required_operations"]
        if not isinstance(approval_required, list) or not all(isinstance(op, str) for op in approval_required):
            raise InstitutionalBootError("Invalid approval_required_operations")
        approvals = request["approvals"]
        if not isinstance(approvals, dict) or not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in approvals.items()):
            raise InstitutionalBootError("Invalid explicit approvals")
        limits = request["limits"]
        if not isinstance(limits, dict) or set(limits) - {"max_steps", "time_limit_seconds", "command_timeout_seconds"}:
            raise InstitutionalBootError("Invalid mandate limits")
        max_steps = limits.get("max_steps")
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 100:
            raise InstitutionalBootError("limits.max_steps must be between 1 and 100")
        time_limit = limits.get("time_limit_seconds")
        if time_limit is not None and (not isinstance(time_limit, int) or isinstance(time_limit, bool) or not 1 <= time_limit <= 3600):
            raise InstitutionalBootError("limits.time_limit_seconds must be between 1 and 3600")
        command_timeout = limits.get("command_timeout_seconds")
        if command_timeout is not None and (not isinstance(command_timeout, int) or isinstance(command_timeout, bool) or not 1 <= command_timeout <= 600):
            raise InstitutionalBootError("limits.command_timeout_seconds must be between 1 and 600")
        allowed_commands_raw = request["allowed_commands"]
        if not isinstance(allowed_commands_raw, list):
            raise InstitutionalBootError("Invalid allowed_commands")
        allowed_commands = tuple(_command_tokens(command, "allowed command") for command in allowed_commands_raw)
        for command in allowed_commands:
            _shell_operation(command)
        if "bash" in allowed_tools and (not allowed_commands or command_timeout is None):
            raise InstitutionalBootError("Shell mandates need allowed_commands and command_timeout_seconds")
        if "bash" not in allowed_tools and allowed_commands:
            raise InstitutionalBootError("allowed_commands requires bash in allowed_tools")
        promotion_eligible = request.get('promotion_eligible', False)
        if not isinstance(promotion_eligible, bool):
            raise InstitutionalBootError('Invalid promotion eligibility')
        return cls(
            objective=request["objective"].strip(), scope=request["scope"].strip(),
            allowed_paths=allowed_paths, allowed_tools=allowed_tools,
            allowed_read_paths=read_paths, allowed_write_paths=write_paths,
            allowed_create_paths=create_paths,
            allowed_operations=frozenset(operations),
            approval_required_operations=frozenset(approval_required),
            approvals={key: value.strip() for key, value in approvals.items()},
            exclusions=request["exclusions"].strip(), max_steps=max_steps,
            time_limit_seconds=time_limit, command_timeout_seconds=command_timeout,
            allowed_commands=allowed_commands, promotion_eligible=promotion_eligible,
        )


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ['git', '-C', str(root), *args], check=True, capture_output=True,
            timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstitutionalBootError('Cannot capture repository evidence') from exc


def _capture_repository(path: str) -> dict:
    """Read-only evidence for review. Capturing does NOT authorize a baseline."""
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise InstitutionalBootError('Workspace is not a directory')
    actual = Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if root != actual:
        raise InstitutionalBootError('Workspace must be the repository root')
    head = _git(root, 'rev-parse', 'HEAD').decode().strip()
    branch = _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD').decode().strip()
    status = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    if any(item[:2] in (b'UU', b'AA', b'DD', b'AU', b'UA', b'DU', b'UD')
           for item in status.split(b'\0')):
        raise InstitutionalBootError('Unresolved repository conflicts')
    if any(line.startswith(b"160000 ") for line in _git(root, 'ls-files', '--stage').splitlines()):
        raise InstitutionalBootError('Submodule baselines are unsupported in this slice')
    digest = hashlib.sha256(status)
    digest.update(_git(root, 'diff', '--cached', '--no-ext-diff', '--no-textconv', '--binary', '--'))
    digest.update(_git(root, 'diff', '--no-ext-diff', '--no-textconv', '--binary', 'HEAD', '--'))
    # Status alone misses edits to an already-untracked file.
    for name in _git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0'):
        if name:
            file = root / name.decode('utf-8')
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                raise InstitutionalBootError('Untracked path escapes workspace')
            digest.update(name)
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    digest.update(chunk)
    return dict(path=str(root), branch=branch, head=head,
                working_tree_status=status.decode('utf-8').replace('\0', '\n'),
                working_tree_sha256=digest.hexdigest())


def capture_repository(path: str) -> dict:
    """Capture a reproducible snapshot without approving it."""
    try:
        return _capture_repository(path)
    except InstitutionalBootError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise InstitutionalBootError('Invalid or unreadable repository workspace') from exc


def _document(root: Path, name: str) -> str:
    from src.tool_execution import _is_sensitive_path
    if not isinstance(name, str) or '\\' in name or '..' in name.split('/'):
        raise InstitutionalBootError('Invalid authority path')
    path = root / name
    if Path(name).is_absolute() or path.suffix != '.md':
        raise InstitutionalBootError('Authority must be a relative Markdown file')
    if not path.resolve().is_relative_to(root) or _is_sensitive_path(str(path.resolve())):
        raise InstitutionalBootError('Authority path is outside the permitted workspace')
    try:
        if path.stat().st_size > 256_000:
            raise InstitutionalBootError('Authority exceeds the context limit')
        content = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise InstitutionalBootError(f'Missing or unreadable authority: {name}') from exc
    if not content.strip() or '\x00' in content or re.search(r'(?m)^(<<<<<<<|=======|>>>>>>>)', content):
        raise InstitutionalBootError(f'Invalid or conflicted authority: {name}')
    return content


def authority_digest(content: str) -> str:
    """Digest of UTF-8 text with universal newlines (same on Windows/Linux)."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _required_authorities(index: str, category: str, *, materialization: bool = False) -> set[str]:
    """Read the selected branch, never maintain a second routing map."""
    tree = index.split('# Decision Tree', 1)
    if len(tree) != 2:
        raise InstitutionalBootError('Index has no Decision Tree')
    tree = tree[1].split('```')
    if len(tree) < 3:
        raise InstitutionalBootError('Unsupported Decision Tree format')
    branches = re.split(r'(?m)^[├└]─\s*', tree[1])
    matches = [b for b in branches[1:] if b.splitlines()[0].strip() == category]
    if len(matches) != 1:
        raise InstitutionalBootError('Missing or ambiguous Decision Tree category')
    required = {'PROJECT_INDEX.md', 'AI_CONTEXT.md', 'PROJECT_RULES.md'}
    # This consumer always integrates an external runtime. Discover its authority
    # from the official Index, including universal discovery links. Never pin a
    # physical institutional location in the runtime.
    integration = set(re.findall(r'[\w./-]+/AGENT_RUNTIME_INTEGRATION\.md', index))
    if len(integration) != 1:
        raise InstitutionalBootError('Index has missing or ambiguous Agent Runtime Integration authority')
    required.update(integration)
    for line in matches[0].splitlines()[1:]:
        # Only the explicit execution profile establishes materialization here;
        # other conditional branches need a task-specific routing adapter.
        if 'PROGRAMMER_PARTNER.md' in line and materialization:
            required.update(re.findall(r'[\w./-]+/PROGRAMMER_PARTNER\.md', line))
        if '→' not in line:
            continue
        if '←' in line and re.search(r'\b(se|quando)\b', line.split('←', 1)[1]):
            continue
        route = line.split('→', 1)[1].split('←', 1)[0].strip()
        if route.endswith('.md'):
            required.add(route)
        else:
            raise InstitutionalBootError('Category needs an explicit routing adapter; cannot guess required sources')
    return required


@dataclass
class InstitutionalContext:
    source: dict
    target: dict
    documents: dict[str, str]
    mandate: str
    exclusions: str
    category: str
    execution: ExecutionMandate
    expected_source: dict = field(default_factory=dict)
    expected_target: dict = field(default_factory=dict)
    mutation_ledger: list[dict] = field(default_factory=list)
    proposal_reference: dict = field(default_factory=dict)
    review_record: dict = field(default_factory=dict)
    _started_at: float = field(default_factory=time.monotonic, repr=False)
    _steps: int = field(default=0, repr=False)

    def verify(self) -> None:
        if capture_repository(self.source['path']) != self.expected_source:
            raise InstitutionalBootError('Institutional repository baseline/working tree drift')
        if capture_repository(self.target['path']) != self.expected_target:
            raise InstitutionalBootError('Execution repository baseline/working tree drift')
        root = Path(self.source['path'])
        for name, content in self.documents.items():
            if _document(root, name) != content:
                raise InstitutionalBootError(f'Authority changed during execution: {name}')
        from src.mobs_mandate_builder import validate_execution_review, MandateProposalError
        try:
            validate_execution_review({"source": self.source, "target": self.target,
                                       "category": self.category,
                                       "authorities": {name: authority_digest(content) for name, content in self.documents.items()}},
                                      self.review_record)
        except MandateProposalError as exc:
            raise InstitutionalBootError(str(exc)) from exc

    def _check_time_and_step(self) -> None:
        if self.execution.time_limit_seconds is not None:
            elapsed = time.monotonic() - self._started_at
            if elapsed > self.execution.time_limit_seconds:
                raise InstitutionalBootError('Mandate time limit exceeded')
        if self._steps >= self.execution.max_steps:
            raise InstitutionalBootError('Mandate step limit exceeded')

    def _require_operation(self, operation: str) -> None:
        if operation not in self.execution.allowed_operations:
            raise InstitutionalBootError(f'Operation is outside mandate: {operation}')
        requires_approval = (
            operation in _HIGH_IMPACT_OPERATIONS
            or operation in self.execution.approval_required_operations
        )
        if requires_approval and not self.execution.approvals.get(operation):
            raise InstitutionalBootError(f'Explicit approval required for operation: {operation}')

    def _authorize_path(self, path: str, operation: str) -> None:
        patterns = {
            "read": self.execution.allowed_read_paths,
            "write": self.execution.allowed_write_paths,
            "create": self.execution.allowed_create_paths,
        }[operation]
        if not _path_is_allowed(path, patterns):
            raise InstitutionalBootError(f'Path is outside mandate: {path}')
        root = Path(self.target['path']).resolve(strict=True)
        resolved = (root / path).resolve()
        try:
            actual = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise InstitutionalBootError(f'Path escapes target workspace: {path}') from exc
        if not _path_is_allowed(actual, patterns):
            raise InstitutionalBootError(f'Resolved path is outside mandate: {path}')

    def authorize_tool(self, tool: str, content: str) -> PendingMutation | PendingCommand | None:
        """Check a parsed existing tool invocation before its dispatcher runs."""
        self.verify()
        self._check_time_and_step()
        if tool not in self.execution.allowed_tools:
            raise InstitutionalBootError(f'Tool is outside mandate: {tool}')
        self._steps += 1
        if tool in _READ_ONLY_TOOLS:
            self._require_operation('read')
            if tool != 'get_workspace':
                path = _read_tool_path(content, tool)
                if tool == 'read_file':
                    self._authorize_path(path, 'read')
                else:
                    root = Path(self.target['path']).resolve(strict=True)
                    try:
                        actual = (root / path).resolve().relative_to(root).as_posix() if path else ''
                    except ValueError as exc:
                        raise InstitutionalBootError('Read search root escapes target workspace') from exc
                    if not _search_root_allowed(path, self.execution.allowed_read_paths) or not _search_root_allowed(actual, self.execution.allowed_read_paths):
                        raise InstitutionalBootError(f'Read search root is outside mandate: {path or "."}')
            return None
        if tool == 'bash':
            tokens = _command_tokens(content, 'shell command')
            operation = _shell_operation(tokens)
            if not _command_allowed(tokens, self.execution.allowed_commands):
                raise InstitutionalBootError('Shell command is outside mandate')
            self._require_operation(operation)
            from src.windows_native_execution import WindowsExecutionPolicy, inventory
            promotion_binding = None
            if self.execution.promotion_eligible:
                required = ('proposal_id', 'proposal_digest', 'authority_snapshot', '_promotion_session_id')
                if any(not self.proposal_reference.get(key) for key in required):
                    raise InstitutionalBootError('Promotion-eligible execution lacks trusted identity')
                promotion_binding = {
                    'session_id': self.proposal_reference['_promotion_session_id'],
                    'proposal_id': self.proposal_reference['proposal_id'],
                    'proposal_digest': self.proposal_reference['proposal_digest'],
                    'authority_snapshot': self.proposal_reference['authority_snapshot'],
                    'source_baseline': self.expected_source,
                    'target_baseline': self.expected_target,
                    'review_authorization': self.review_record.get('authorization', {}),
                }
            return PendingCommand(content.strip(), operation,
                                  _working_tree_entries(Path(self.target['path'])),
                                  inventory(Path(self.target['path']), include_git=True),
                                  WindowsExecutionPolicy(
                                      self.target['path'], tokens,
                                      self.execution.allowed_read_paths,
                                      self.execution.allowed_write_paths,
                                      self.execution.allowed_create_paths,
                                      self.execution.command_timeout_seconds,
                                      promotion_binding=promotion_binding,
                                  ))
        if tool in {'write_file', 'edit_file'}:
            if self.execution.promotion_eligible:
                if tool != 'write_file':
                    raise InstitutionalBootError('Direct writes are blocked for promotion-eligible executions')
                if self.execution.command_timeout_seconds is None:
                    raise InstitutionalBootError('Promotion-private write requires a command timeout')
                path, payload = _write_tool_payload(content)
                is_create = not (Path(self.target['path']) / path).exists()
                operation = 'create' if is_create else 'write'
                self._authorize_path(path, operation)
                if not is_create:
                    self._authorize_path(path, 'read'); self._require_operation('read')
                self._require_operation(operation)
                from src.windows_native_execution import WindowsExecutionPolicy, inventory
                required = ('proposal_id', 'proposal_digest', 'authority_snapshot', '_promotion_session_id')
                if any(not self.proposal_reference.get(key) for key in required):
                    raise InstitutionalBootError('Promotion-eligible execution lacks trusted identity')
                binding = {'session_id': self.proposal_reference['_promotion_session_id'],
                           'proposal_id': self.proposal_reference['proposal_id'],
                           'proposal_digest': self.proposal_reference['proposal_digest'],
                           'authority_snapshot': self.proposal_reference['authority_snapshot'],
                           'source_baseline': self.expected_source, 'target_baseline': self.expected_target,
                           'review_authorization': self.review_record.get('authorization', {})}
                return PendingCommand('private write_file ' + path, operation,
                                      _working_tree_entries(Path(self.target['path'])),
                                      inventory(Path(self.target['path']), include_git=True),
                                      WindowsExecutionPolicy(self.target['path'], ('python', '-I', '-c', ''),
                                                             self.execution.allowed_read_paths,
                                                             self.execution.allowed_write_paths,
                                                             self.execution.allowed_create_paths,
                                                             self.execution.command_timeout_seconds,
                                                             promotion_binding=binding,
                                                             private_write={'path': path, 'content': payload}))
            path = _tool_path(content, tool)
            is_create = tool == 'write_file' and not (Path(self.target['path']) / path).exists()
            operation = 'create' if is_create else 'write'
            self._authorize_path(path, operation)
            if not is_create:
                self._authorize_path(path, 'read')
                self._require_operation('read')
            operations = [operation]
            if _SECRET_PATH.search(path):
                operations.append('credentials')
            for operation in operations:
                self._require_operation(operation)
            return PendingMutation(tool, (path,), tuple(operations), _working_tree_entries(Path(self.target['path'])))
        if tool == 'apply_patch':
            if self.execution.promotion_eligible:
                raise InstitutionalBootError('Direct writes are blocked for promotion-eligible executions')
            patch_operations = _patch_paths(content)
            paths = []
            operations = []
            for kind, path in patch_operations:
                operation = 'delete' if kind == 'delete' else 'create' if kind == 'add' else 'write'
                self._authorize_path(path, 'write' if operation == 'delete' else operation)
                if operation != 'create':
                    self._authorize_path(path, 'read')
                    self._require_operation('read')
                paths.append(path)
                operations.append(operation)
                if _SECRET_PATH.search(path):
                    operations.append('credentials')
            for operation in sorted(set(operations)):
                self._require_operation(operation)
            return PendingMutation(tool, tuple(paths), tuple(sorted(set(operations))), _working_tree_entries(Path(self.target['path'])))
        raise InstitutionalBootError(f'Unsupported governed tool: {tool}')

    def _complete_workspace_action(self, before: dict[str, str], allowed_paths: tuple[str, ...], label: str) -> tuple[list[str], dict]:
        """Check post-action drift before accepting a new target snapshot."""
        root = Path(self.target['path'])
        after = _working_tree_entries(root)
        changed_paths = sorted({
            *{path for path in before if before.get(path) != after.get(path)},
            *{path for path in after if before.get(path) != after.get(path)},
        })
        unexpected = [path for path in changed_paths if not _path_is_allowed(path, allowed_paths)]
        if unexpected:
            raise InstitutionalBootError(f'Unexpected drift during {label}: ' + ', '.join(unexpected))
        root_source = Path(self.source['path'])
        for name, content in self.documents.items():
            if _document(root_source, name) != content:
                raise InstitutionalBootError(f'Authority changed during action: {name}')
        if root_source != root and capture_repository(self.source['path']) != self.expected_source:
            raise InstitutionalBootError('Institutional repository drift during action')
        next_target = capture_repository(self.target['path'])
        if _working_tree_entries(root) != after:
            raise InstitutionalBootError('Execution repository drift after action')
        self.expected_target = next_target
        if root_source == root:
            self.expected_source = dict(next_target)
        return changed_paths, next_target

    def complete_mutation(self, pending: PendingMutation) -> dict:
        """Record only the expected mutation and reject concurrent/out-of-scope drift."""
        if self.execution.time_limit_seconds is not None and time.monotonic() - self._started_at > self.execution.time_limit_seconds:
            raise InstitutionalBootError('Mandate time limit exceeded during mutation')
        before = pending.before_entries
        changed_paths, next_target = self._complete_workspace_action(before, pending.paths, 'mutation')
        event = {
            'tool': pending.tool,
            'paths': list(pending.paths),
            'operations': list(pending.operations),
            'before': self.mutation_ledger[-1]['after'] if self.mutation_ledger else self.target,
            'after': self.expected_target,
        }
        self.mutation_ledger.append(event)
        return event

    def complete_command(self, pending: PendingCommand, result: dict) -> dict:
        """Keep command evidence and accept only command-local workspace changes."""
        if self.execution.time_limit_seconds is not None and time.monotonic() - self._started_at > self.execution.time_limit_seconds:
            raise InstitutionalBootError('Mandate time limit exceeded during command')
        from src.windows_native_execution import TrustedExecutionUnavailable, inventory
        tool_name = 'write_file_private' if pending.command.startswith('private write_file ') else 'bash'
        boundary = result.get('trusted_execution') if isinstance(result, dict) else None
        if not isinstance(boundary, dict) or boundary.get('adapter') != 'windows_appcontainer_job_v1':
            self.mutation_ledger.append({
                'tool': tool_name, 'command': pending.command, 'operation': pending.operation,
                'status': 'blocked', 'exit_code': result.get('exit_code') if isinstance(result, dict) else None,
                'reason': result.get('error') if isinstance(result, dict) else 'Missing execution result',
            })
            raise InstitutionalBootError('Required Windows execution boundary was not applied')
        try:
            if inventory(Path(self.target['path']), include_git=True) != pending.before_inventory:
                raise InstitutionalBootError('Target workspace drift during private command')
            if capture_repository(self.target['path']) != self.expected_target:
                raise InstitutionalBootError('Repository baseline drift during private command')
            if capture_repository(self.source['path']) != self.expected_source:
                raise InstitutionalBootError('Institutional repository drift during private command')
        except (InstitutionalBootError, TrustedExecutionUnavailable) as exc:
            self.mutation_ledger.append({
                'tool': tool_name, 'command': pending.command, 'operation': pending.operation,
                'status': 'blocked', 'exit_code': result.get('exit_code'),
                'reason': str(exc), 'boundary': boundary,
            })
            raise InstitutionalBootError(str(exc)) from exc
        changed_paths, next_target = [], self.expected_target
        raw_output = str(result.get('output') or result.get('stdout') or result.get('error') or '')
        event = {
            'tool': tool_name, 'command': pending.command, 'operation': pending.operation,
            'exit_code': result.get('exit_code'), 'output_sha256': hashlib.sha256(raw_output.encode('utf-8')).hexdigest(),
            'output_chars': len(raw_output), 'changed_paths': changed_paths,
            'private_effects': boundary['effects'], 'boundary': boundary,
            'before': self.mutation_ledger[-1]['after'] if self.mutation_ledger else self.target,
            'after': next_target,
        }
        if self.execution.promotion_eligible:
            artifact = boundary.get('promotion_artifact')
            if artifact is None and not boundary.get('effects'):
                event['promotion'] = {'status': 'no_promotable_effect'}
            elif not isinstance(artifact, dict):
                raise InstitutionalBootError('Promotion-eligible private effect was not sealed')
            else:
                from src.mobs_controlled_promotion import PromotionError, record_pending
                try:
                    event['promotion'] = record_pending(self.proposal_reference['_promotion_session_id'], artifact)
                except PromotionError as exc:
                    raise InstitutionalBootError(str(exc)) from exc
        self.mutation_ledger.append(event)
        return event

    def message(self) -> dict:
        evidence = dict(source=self.source, target=self.target, category=self.category,
                        proposal_reference=self.proposal_reference,
                        review={"snapshot_id": self.review_record.get("snapshot_id"),
                                "reviewer": self.review_record.get("reviewer"),
                                "authorization": {key: self.review_record.get("authorization", {}).get(key)
                                                  for key in ("id", "version", "installation_id", "account_digest", "binding_sha256")}},
                        mandate=self.mandate, exclusions=self.exclusions,
                        execution=dict(objective=self.execution.objective, scope=self.execution.scope,
                                       allowed_paths=self.execution.allowed_paths,
                                       allowed_read_paths=self.execution.allowed_read_paths,
                                       allowed_write_paths=self.execution.allowed_write_paths,
                                       allowed_create_paths=self.execution.allowed_create_paths,
                                       allowed_tools=sorted(self.execution.allowed_tools),
                                       allowed_operations=sorted(self.execution.allowed_operations),
                                       approval_required_operations=sorted(self.execution.approval_required_operations),
                                       limits=dict(max_steps=self.execution.max_steps,
                                                   time_limit_seconds=self.execution.time_limit_seconds,
                                                   command_timeout_seconds=self.execution.command_timeout_seconds),
                                       allowed_commands=[' '.join(command) for command in self.execution.allowed_commands]),
                        authorities={n: authority_digest(c) for n, c in self.documents.items()})
        body = ('MOBS INSTITUTIONAL CONTEXT\nMOBS governs; Odysseus executes. '
                'This reviewed context is not permission to publish or institutionalize outputs.\n'
                + json.dumps(evidence, ensure_ascii=False) + '\n'
                + '\n'.join(f'\n--- {name} ---\n{content}' for name, content in self.documents.items()))
        return {'role': 'system', 'content': body, '_protected': True}


def institutional_boot(request: dict, workspace: str) -> InstitutionalContext:
    """Consume an explicitly reviewed mandate; never infer authority from a model name."""
    try:
        if not isinstance(request, dict):
            raise InstitutionalBootError('Expected an explicit MOBS execution mandate')
        for name in ('mandate', 'exclusions', 'category'):
            if not isinstance(request.get(name), str) or not request[name].strip():
                raise InstitutionalBootError(f'Missing {name}')
        if request.get('authority_review') != 'consistent':
            raise InstitutionalBootError('Authority review missing, ambiguous or contradictory')
        if 'proposal_id' in request:
            from src.mobs_mandate_builder import validate_proposal_identity, MandateProposalError
            try:
                validate_proposal_identity(request)
            except MandateProposalError as exc:
                raise InstitutionalBootError(str(exc)) from exc
        source, target = request['source'], request['target']
        from src.tool_execution import vet_workspace
        if not isinstance(source, dict) or not vet_workspace(source.get('path', '')):
            raise InstitutionalBootError('Invalid institutional workspace')
        for baseline in (source, target):
            if not isinstance(baseline, dict) or set(baseline) != {'path', 'branch', 'head', 'working_tree_status', 'working_tree_sha256'}:
                raise InstitutionalBootError('Incomplete authorized baseline')
            if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', baseline['head']):
                raise InstitutionalBootError('Baseline must be an immutable full commit id')
            if capture_repository(baseline['path']) != baseline:
                raise InstitutionalBootError('Authorized repository baseline does not match')
        from src.tool_execution import vet_workspace
        if not workspace or not vet_workspace(workspace) or Path(workspace).resolve() != Path(target['path']):
            raise InstitutionalBootError('Invalid or unauthorized execution workspace')
        root = Path(source['path'])
        # First institutional document read: always the Index.
        index = _document(root, 'PROJECT_INDEX.md')
        required = _required_authorities(index, request['category'],
                                         materialization='write' in request.get('allowed_operations', []))
        authorities = request['authorities']
        if not isinstance(authorities, dict) or not required.issubset(authorities):
            raise InstitutionalBootError('Mandate omits required authorities discovered through Index')
        if len(authorities) > 40:
            raise InstitutionalBootError('Too many authorities for this slice')
        documents = {'PROJECT_INDEX.md': index}
        for name, expected in authorities.items():
            content = documents.get(name) or _document(root, name)
            if authority_digest(content) != expected:
                raise InstitutionalBootError(f'Authority differs from reviewed content: {name}')
            documents[name] = content
        execution = ExecutionMandate.from_request(request)
        if execution.exclusions != request['exclusions'].strip():
            raise InstitutionalBootError('Mandate exclusions conflict with execution exclusions')
        context = InstitutionalContext(
            dict(source), dict(target), documents, request['mandate'],
            request['exclusions'], request['category'], execution,
            expected_source=dict(source),
            expected_target=dict(target),
            proposal_reference={key: request[key] for key in
                                ('proposal_id', 'proposal_digest', 'authority_snapshot', '_promotion_session_id') if key in request},
            review_record=request.get('review_record', {}),
        )
        if len(context.message()['content']) > 128_000:
            raise InstitutionalBootError('Minimum reviewed context exceeds limit; refine mandate')
        context.verify()
        return context
    except InstitutionalBootError:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise InstitutionalBootError('Invalid or incomplete institutional execution input') from exc
