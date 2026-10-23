import asyncio
import json
import os
import re
import difflib
import fnmatch
import shutil
from typing import Optional, Dict, Any, Tuple, List

from src.constants import MAX_READ_CHARS, MAX_DIFF_LINES, MAX_OUTPUT_CHARS

_CODENAV_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".next", ".cache", "site-packages", ".idea", ".tox",
})
_CODENAV_MAX_HITS = 200
_CODENAV_MAX_LINE = 400


def _is_link_or_junction(path: str) -> bool:
    return os.path.islink(path) or bool(getattr(os.path, "isjunction", lambda _: False)(path))


def _glob_to_regex(pat: str) -> "re.Pattern":
    """Translate a forward-slash glob (**, *, ?) into a compiled regex.
    `**/` matches zero or more complete directories.
    `*` matches within a single path segment (does not cross /).
    """
    i, n, out = 0, len(pat), []
    while i < n:
        if pat[i : i + 3] == "**/":
            out.append("(?:[^/]+/)*")
            i += 3
        elif pat[i : i + 2] == "**":
            out.append(".*")
            i += 2
        elif pat[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return re.compile("".join(out))

def _unified_diff(old: str, new: str, path: str) -> Optional[Dict[str, Any]]:
    if old == new:
        return None
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    label = path or "file"
    diff_lines = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{label}", tofile=f"b/{label}",
        lineterm="",
    ))
    # Only the first two rows are headers. Content beginning in ++/-- still
    # counts as an added/removed line when prefixed by the diff marker.
    added = sum(1 for line in diff_lines[2:] if line.startswith("+"))
    removed = sum(1 for line in diff_lines[2:] if line.startswith("-"))
    truncated = False
    if len(diff_lines) > MAX_DIFF_LINES:
        diff_lines = diff_lines[:MAX_DIFF_LINES]
        truncated = True
    text = "\n".join(diff_lines)
    if not diff_lines:
        text = 'Text lines unchanged; line endings or final newline changed. Compare the full contents.'
    if truncated:
        text += f"\n… diff truncated at {MAX_DIFF_LINES} lines"
    return {
        "text": text,
        "added": added,
        "removed": removed,
        "truncated": truncated,
        "new_file": old == "",
        "file": os.path.basename(path) or (path or "file"),
    }

class EditFileTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import _resolve_tool_path, _resolve_search_root, _truncate
        try:
            args = json.loads(content) if isinstance(content, str) else None
        except (json.JSONDecodeError, TypeError):
            args = None
        if not isinstance(args, dict):
            return {"error": "edit_file: JSON object required", "exit_code": 1}
        if any(not isinstance(args.get(key), str) for key in ('path', 'old_string', 'new_string')):
            return {"error": "edit_file: path, old_string and new_string must be explicitly supplied strings", "exit_code": 1}
        if type(args.get('replace_all', False)) is not bool:
            return {"error": "edit_file: replace_all must be a boolean", "exit_code": 1}
        raw_path = args['path'].strip()
        old, new = args['old_string'], args['new_string']
        replace_all = args.get('replace_all', False)
        try:
            old.encode('utf-8'); new.encode('utf-8')
        except UnicodeEncodeError:
            return {"error": "edit_file: replacement strings must be valid UTF-8 text", "exit_code": 1}
        if not raw_path:
            return {"error": "edit_file: path required", "exit_code": 1}
        try:
            path = _resolve_tool_path(raw_path)
        except ValueError as e:
            return {"error": f"edit_file: {e}", "exit_code": 1}
        if old == "":
            return {"error": "edit_file: old_string required (use write_file to create a file)", "exit_code": 1}
        if old == new:
            return {"error": "edit_file: old_string and new_string are identical", "exit_code": 1}

        # Preserve the existing universal-newline matching semantics without
        # normalizing/re-encoding every untouched line in the file. Everything
        # except newline equivalence is literal; replacement is not regex text.
        old_lines = old.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        # A CRLF is one newline, never two matches obtained by backtracking.
        newline_pattern = r'(?:\r\n|\r(?!\n)|(?<!\r)\n)'
        pattern = re.compile(newline_pattern.join(re.escape(line) for line in old_lines))

        def _apply():
            """Helper function that performs the actual string replacement and file writing logic."""
            with open(path, "r", encoding="utf-8", newline="") as f:
                original = f.read()
            count = sum(1 for _ in pattern.finditer(original))
            if count == 0:
                return original, None, "not_found", 0
            if count > 1 and not replace_all:
                return original, None, f"not_unique:{count}", 0
            updated, replaced = pattern.subn(lambda _: new, original, count=0 if replace_all else 1)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(updated)
            return original, updated, "ok", replaced

        try:
            original, updated, status, n = await asyncio.to_thread(_apply)
        except FileNotFoundError:
            return {"error": f"edit_file: {path}: not found (use write_file to create it)", "exit_code": 1}
        except (IsADirectoryError, UnicodeDecodeError):
            return {"error": f"edit_file: {path}: not an editable text file", "exit_code": 1}
        except PermissionError:
            return {"error": f"edit_file: {path}: permission denied", "exit_code": 1}
        except OSError as e:
            return {"error": f"edit_file: {path}: {e}", "exit_code": 1}

        if status == "not_found":
            return {"error": f"edit_file: old_string not found in {path}. Read the file and match it exactly.", "exit_code": 1}
        if status.startswith("not_unique"):
            n = status.split(":", 1)[1]
            return {"error": f"edit_file: old_string is not unique in {path} ({n} matches). Add surrounding context or set replace_all=true.", "exit_code": 1}

        result = {"output": f"Edited {path} ({n} replacement{'s' if n != 1 else ''})", "exit_code": 0}
        diff = _unified_diff(original, updated, path)
        if diff:
            result["diff"] = diff
        return result

class ReadFileTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import _resolve_tool_path, _resolve_search_root, _truncate
        raw_path, offset, limit = content.split("\n", 1)[0].strip(), 0, 0
        _stripped = content.strip()
        if _stripped.startswith("{"):
            try:
                _a = json.loads(_stripped)
                raw_path = str(_a.get("path", "")).strip()
                offset = int(_a.get("offset") or 0)
                limit = int(_a.get("limit") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        try:
            path = _resolve_tool_path(raw_path)
        except ValueError as e:
            return {"error": f"read_file: {e}", "exit_code": 1}
        try:
            def _read():
                start = max(offset, 1)
                out, lines_read, budget = [], 0, MAX_READ_CHARS
                has_more = partial_line = False
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for _ in range(start - 1):
                        # Skip long preceding lines in bounded chunks too.
                        while True:
                            skipped = f.readline(MAX_READ_CHARS + 1)
                            if not skipped or skipped.endswith("\n"):
                                break
                        if not skipped:
                            return "", 0, False, None, False
                    while True:
                        if limit > 0 and lines_read >= limit:
                            has_more = bool(f.read(1))
                            break
                        line = f.readline(budget + 1)
                        if not line:
                            break
                        if len(line) > budget:
                            has_more = True
                            if not out:
                                # A partial line cannot be resumed by a line offset.
                                # Do not skip its unread suffix or promise completeness.
                                out.append(line[:budget])
                                partial_line = True
                            break
                        out.append(line)
                        lines_read += 1
                        budget -= len(line)
                next_offset = start + lines_read if has_more and not partial_line else None
                return "".join(out), lines_read, has_more, next_offset, partial_line
            data, lines_read, has_more, next_offset, partial_line = await asyncio.to_thread(_read)
        except FileNotFoundError:
            return {"error": f"read_file: {path}: not found", "exit_code": 1}
        except PermissionError:
            return {"error": f"read_file: {path}: permission denied", "exit_code": 1}
        except IsADirectoryError:
            return {"error": f"read_file: {path}: is a directory (use ls)", "exit_code": 1}
        except OSError as e:
            return {"error": f"read_file: {path}: {e}", "exit_code": 1}
        return {"output": data, "exit_code": 0,
                "has_more": has_more, "next_offset": next_offset,
                "partial_line": partial_line, "lines_read": lines_read,
                "truncated": has_more, "start_line": max(offset, 1),
                "source_reference": {"path": raw_path, "start_line": max(offset, 1),
                                     "kind": "read_file_snapshot"}}

class WriteFileTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import _resolve_tool_path, _resolve_search_root, _truncate
        if not isinstance(content, str):
            return {"error": "write_file: text arguments required", "exit_code": 1}
        lines = content.split("\n", 1)
        raw_path = lines[0].strip()
        body = lines[1] if len(lines) > 1 else ""
        # Decode JSON-object args (the fenced inline-args shape
        # ```write_file {"path": "...", "content": "..."}```), matching
        # ReadFileTool above. Without this the whole JSON string becomes the
        # path and the file is written under a garbage name. This is the live
        # path: there is no filesystem MCP server, so write_file always runs
        # here via _direct_fallback, not through _build_mcp_args.
        _stripped = content.strip()
        if _stripped.startswith("{"):
            try:
                _a = json.loads(_stripped)
                if not isinstance(_a, dict) or any(not isinstance(_a.get(key), str) for key in ('path','content')):
                    return {"error": "write_file: path and content must be explicitly supplied strings", "exit_code": 1}
                raw_path = _a['path'].strip()
                body = _a['content']
            except (json.JSONDecodeError, TypeError, ValueError):
                return {"error": "write_file: invalid JSON object", "exit_code": 1}
        try:
            byte_size = len(body.encode('utf-8'))
        except UnicodeEncodeError:
            return {"error": "write_file: content must be valid UTF-8 text", "exit_code": 1}
        try:
            path = _resolve_tool_path(raw_path)
        except ValueError as e:
            return {"error": f"write_file: {e}", "exit_code": 1}
        try:
            def _write():
                old = ""
                try:
                    with open(path, "r", encoding="utf-8", newline="") as f:
                        old = f.read()
                except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
                    old = ""
                d = os.path.dirname(path)
                if d:
                    os.makedirs(d, exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(body)
                return old, byte_size
            old_content, size = await asyncio.to_thread(_write)
        except PermissionError:
            return {"error": f"write_file: {path}: permission denied", "exit_code": 1}
        except OSError as e:
            return {"error": f"write_file: {path}: {e}", "exit_code": 1}
        diff = _unified_diff(old_content, body, path)
        result = {"output": f"Wrote {size} bytes to {path}", "exit_code": 0}
        if diff:
            result["diff"] = diff
        return result

class ApplyPatchTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        """Apply a small Codex-style patch using exact context matching.

        This is deliberately stricter than git-apply: if an update hunk's old
        text is not found exactly once, the whole patch is rejected before any
        file is changed. That keeps agent edits reviewable and avoids fuzzy
        corruption when the model patches stale context.
        """
        from src.tool_execution import _resolve_tool_path

        if not isinstance(content, str):
            return {"error": "apply_patch: patch text must be a string", "exit_code": 1}
        patch_text = content
        stripped = patch_text.strip()
        if stripped.startswith("{"):
            try:
                args = json.loads(stripped)
                keys = [key for key in ('patch_text','patchText','patch') if isinstance(args,dict) and key in args]
                if len(keys)!=1 or not isinstance(args[keys[0]],str):
                    return {"error": "apply_patch: supply exactly one string patch_text, patchText or patch", "exit_code": 1}
                patch_text = args[keys[0]]
            except (json.JSONDecodeError, TypeError):
                return {"error": "apply_patch: invalid JSON object", "exit_code": 1}
        if not patch_text.strip():
            return {"error": "apply_patch: patch_text required", "exit_code": 1}

        try:
            ops = _parse_agent_patch(patch_text)
            if not ops:
                return {"error": "apply_patch: no file operations found", "exit_code": 1}
            prepared = []
            targets = []
            for op in ops:
                if not op['path']:
                    raise ValueError('empty patch target')
                path = _resolve_tool_path(op["path"])
                target = os.path.normcase(os.path.abspath(path))
                for previous in targets:
                    try:
                        shared = os.path.commonpath((previous,target))
                    except ValueError:
                        continue  # distinct drives
                    if shared in (previous,target):
                        raise ValueError('repeated or conflicting patch targets')
                targets.append(target)
                kind = op["kind"]
                if kind == "add":
                    if os.path.exists(path):
                        return {"error": f"apply_patch: {op['path']}: already exists", "exit_code": 1}
                    old = ""
                    new = op["content"]
                elif kind == "delete":
                    if not os.path.isfile(path):
                        return {"error": f"apply_patch: {op['path']}: not found", "exit_code": 1}
                    with open(path, "r", encoding="utf-8", newline="") as f:
                        old = f.read()
                    new = ""
                else:
                    if not os.path.isfile(path):
                        return {"error": f"apply_patch: {op['path']}: not found", "exit_code": 1}
                    with open(path, "r", encoding="utf-8", newline="") as f:
                        old = f.read()
                    new = _apply_patch_hunks(old, op["hunks"], op["path"])
                new.encode('utf-8')  # validate every operation before the commit loop
                prepared.append((kind, path, old, new))

            diffs = []
            for kind, path, old, new in prepared:
                if kind == "delete":
                    os.remove(path)
                else:
                    directory = os.path.dirname(path)
                    if directory:
                        os.makedirs(directory, exist_ok=True)
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(new)
                diff = _unified_diff(old, new, path)
                if diff:
                    diffs.append(diff)
        except (ValueError, UnicodeDecodeError, PermissionError, OSError) as e:
            return {"error": f"apply_patch: {e}", "exit_code": 1}

        added = sum(int(d.get("added") or 0) for d in diffs)
        removed = sum(int(d.get("removed") or 0) for d in diffs)
        text_parts = [d.get("text", "") for d in diffs if d.get("text")]
        diff_text = "\n".join(text_parts)
        truncated = any(d.get('truncated') for d in diffs)
        if len(diff_text.splitlines()) > MAX_DIFF_LINES:
            truncated = True
            diff_text = "\n".join(diff_text.splitlines()[:MAX_DIFF_LINES]) + f"\n... diff truncated at {MAX_DIFF_LINES} lines"
        result = {
            "output": f"Applied patch ({len(prepared)} file{'s' if len(prepared) != 1 else ''}, +{added}/-{removed})",
            "exit_code": 0,
        }
        if diffs:
            result["diff"] = {
                "text": diff_text,
                "added": added,
                "removed": removed,
                "truncated": truncated,
                "new_file": any(d.get("new_file") for d in diffs),
                "file": "patch",
            }
        return result

def _parse_agent_patch(patch_text: str) -> List[Dict[str, Any]]:
    lines = patch_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[0].strip() != "*** Begin Patch":
        raise ValueError("patch must start with *** Begin Patch")
    if lines[-1].strip() != "*** End Patch":
        raise ValueError("patch must end with *** End Patch")

    ops: List[Dict[str, Any]] = []
    i = 1
    while i < len(lines) - 1:
        line = lines[i]
        if not line:
            i += 1
            continue
        if line.startswith("*** Add File: "):
            path = line[len("*** Add File: "):].strip()
            body = []
            i += 1
            while i < len(lines) - 1 and not lines[i].startswith("*** "):
                if not lines[i].startswith("+"):
                    raise ValueError(f"add file {path}: every content line must start with +")
                body.append(lines[i][1:])
                i += 1
            ops.append({"kind": "add", "path": path, "content": "\n".join(body) + ("\n" if body else "")})
            continue
        if line.startswith("*** Delete File: "):
            path = line[len("*** Delete File: "):].strip()
            ops.append({"kind": "delete", "path": path})
            i += 1
            continue
        if line.startswith("*** Update File: "):
            path = line[len("*** Update File: "):].strip()
            hunks = []
            current = []
            i += 1
            if i < len(lines) - 1 and lines[i].startswith("*** Move to: "):
                raise ValueError("move operations are not supported")
            while i < len(lines) - 1 and not lines[i].startswith("*** "):
                if lines[i].startswith("@@"):
                    if current:
                        hunks.append(current)
                        current = []
                elif lines[i].startswith((" ", "-", "+")):
                    current.append(lines[i])
                elif lines[i] == "":
                    current.append(" ")
                else:
                    raise ValueError(f"update file {path}: invalid patch line {lines[i]!r}")
                i += 1
            if current:
                hunks.append(current)
            if not hunks:
                raise ValueError(f"update file {path}: no hunks")
            ops.append({"kind": "update", "path": path, "hunks": hunks})
            continue
        raise ValueError(f"unexpected patch line: {line!r}")
    return ops

def _apply_patch_hunks(original: str, hunks: List[List[str]], label: str) -> str:
    # Physical rows keep their original terminators; match entire logical rows.
    parts = re.split(r'(\r\n|\r|\n)', original)
    rows = [(parts[i], parts[i+1] if i+1<len(parts) else '')
            for i in range(0,len(parts),2) if i+1<len(parts) or parts[i]]
    cursor = 0
    for idx, hunk in enumerate(hunks, 1):
        old_lines = [line[1:] for line in hunk if line.startswith((' ','-'))]
        if not old_lines:
            raise ValueError(f'{label}: hunk {idx} needs existing line context')
        texts = [body for body, _ in rows]
        matches = [i for i in range(len(rows)-len(old_lines)+1)
                   if texts[i]==old_lines[0] and texts[i:i+len(old_lines)]==old_lines]
        if not matches:
            raise ValueError(f"{label}: hunk {idx} context not found")
        if len(matches)!=1:
            raise ValueError(f'{label}: hunk {idx} context matched {len(matches)} times')
        start=matches[0];end=start+len(old_lines)
        if start<cursor:
            raise ValueError(f'{label}: hunk {idx} is out of order or overlaps')
        matched=rows[start:end]
        ending=next((eol for _,eol in matched if eol),next((eol for _,eol in rows if eol),'\n'))
        replacement=[];offset=0
        for line in hunk:
            if line[0]==' ':
                replacement.append(matched[offset]);offset+=1
            elif line[0]=='-':
                offset+=1
            else:
                replacement.append((line[1:],ending))
        if end==len(rows) and replacement and hunk[-1].startswith('+') and not matched[-1][1]:
            replacement[-1]=(replacement[-1][0],'')
        # Appending after an EOF context row needs a separator, not concatenation.
        replacement=[(body,eol or ending) if i<len(replacement)-1 else (body,eol)
                     for i,(body,eol) in enumerate(replacement)]
        rows[start:end]=replacement
        cursor=start+len(replacement)
    return ''.join(body+eol for body,eol in rows)

class LsTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import _resolve_tool_path, _resolve_search_root, _truncate
        raw_path = ""
        _s = (content or "").strip()
        if _s.startswith("{"):
            try:
                raw_path = str(json.loads(_s).get("path", "")).strip()
            except json.JSONDecodeError:
                raw_path = ""
        else:
            raw_path = _s.split("\n", 1)[0].strip()
        try:
            root = _resolve_search_root(raw_path)
        except ValueError as e:
            return {"error": f"ls: {e}", "exit_code": 1}

        def _ls():
            if not os.path.isdir(root):
                return None, f"ls: {root}: not a directory"
            rows = []
            try:
                with os.scandir(root) as it:
                    for entry in it:
                        if entry.name.startswith("."):
                            continue
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                            size = entry.stat(follow_symlinks=False).st_size if not is_dir else 0
                        except OSError:
                            continue
                        rows.append((is_dir, entry.name, size))
            except (PermissionError, OSError) as _e:
                return None, f"ls: {_e}"
            rows.sort(key=lambda r: (not r[0], r[1].lower()))
            lines = [f"{root}:"]
            for is_dir, name, size in rows[:_CODENAV_MAX_HITS]:
                lines.append(f"  {name}/" if is_dir else f"  {name}  ({size} B)")
            if len(rows) > _CODENAV_MAX_HITS:
                lines.append(f"  ... [{len(rows) - _CODENAV_MAX_HITS} more]")
            if not rows:
                lines.append("  (empty)")
            return "\n".join(lines), None

        out, err = await asyncio.to_thread(_ls)
        if err:
            return {"error": err, "exit_code": 1}
        return {"output": _truncate(out), "exit_code": 0}

class GlobTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import (
            _SENSITIVE_BASENAMES,
            _is_sensitive_path,
            _resolve_tool_path,
            _resolve_search_root,
            _truncate,
        )
        args = {}
        _s = (content or "").strip()
        if _s.startswith("{"):
            try:
                args = json.loads(_s)
            except json.JSONDecodeError:
                args = {}
        else:
            args = {"pattern": _s}
        pattern = str(args.get("pattern", "")).strip()
        if not pattern:
            return {"error": "glob: pattern is required", "exit_code": 1}
        try:
            root = _resolve_search_root(str(args.get("path", "")))
        except ValueError as e:
            return {"error": f"glob: {e}", "exit_code": 1}

        def _glob():
            base = os.path.abspath(root)
            if not os.path.isdir(base):
                return None, f"glob: {root}: not a directory"
            rbase = os.path.realpath(base)
            norm_pat = pattern.replace("\\", "/")
            # Fast path: literal pattern (no wildcards) → direct path lookup.
            if not any(c in norm_pat for c in "*?["):
                cand = os.path.realpath(os.path.join(base, norm_pat))
                # Keep the literal lookup inside the search root. os.path.join
                # lets an absolute pattern (or one containing ../) escape `base`,
                # which would turn glob into an existence/path oracle for
                # arbitrary host files — bypassing the workspace/allowlist
                # confinement that _resolve_search_root applies to the root.
                # An escaping literal falls through to the walk, which only ever
                # yields paths under base.
                nbase = os.path.normcase(rbase)
                try:
                    inside = cand == rbase or os.path.commonpath(
                        [os.path.normcase(cand), nbase]
                    ) == nbase
                except ValueError:
                    inside = False
                # A literal that names a deny-listed sensitive file (.env,
                # .ssh/id_rsa, …) falls through to the walk, which skips it —
                # otherwise glob would surface secret paths that read_file /
                # grep already refuse to touch.
                if inside and os.path.exists(cand) and not _is_sensitive_path(cand) and not (ctx.get("governed_read") and _is_link_or_junction(cand)):
                    return [cand], None
                # Literal not at exact path — fall through to walk so
                # e.g. "foo.py" still matches at any depth (like rglob).
            # Compile glob to regex: * stays within one segment, **/ spans dirs.
            regex = _glob_to_regex(norm_pat)
            matched = []
            cap = _CODENAV_MAX_HITS * 5
            try:
                for dp, dns, fns in os.walk(base):
                    # Prune skipped dirs before descending (unlike rglob which
                    # descends first then filters — fatal on large node_modules).
                    # Sensitive dirs (.ssh, .gnupg, …) are pruned too so glob
                    # never enumerates the keys/tokens inside them.
                    dns[:] = [
                        d for d in dns
                        if d not in _CODENAV_SKIP_DIRS and d not in _SENSITIVE_BASENAMES
                        and not (ctx.get("governed_read") and _is_link_or_junction(os.path.join(dp, d)))
                    ]
                    for name in fns + dns:
                        full = os.path.join(dp, name)
                        if ctx.get("governed_read") and _is_link_or_junction(full):
                            continue
                        rel = os.path.relpath(full, base).replace(os.sep, "/")
                        if regex.fullmatch(rel) or regex.fullmatch(name):
                            # Skip deny-listed sensitive files (.env, id_rsa,
                            # known_hosts, …) the same way grep does.
                            if _is_sensitive_path(os.path.realpath(full)):
                                continue
                            try:
                                mtime = os.stat(full).st_mtime
                            except OSError:
                                mtime = 0
                            matched.append((mtime, full))
                    if len(matched) > cap:
                        break
            except OSError as _e:
                return None, f"glob: {_e}"
            matched.sort(key=lambda t: t[0], reverse=True)
            return [pth for _, pth in matched[:_CODENAV_MAX_HITS]], None

        paths, err = await asyncio.to_thread(_glob)
        if err:
            return {"error": err, "exit_code": 1}
        if not paths:
            return {"output": f"No files matching {pattern!r} under {root}", "exit_code": 0}
        out = "\n".join(paths)
        if len(paths) >= _CODENAV_MAX_HITS:
            out += f"\n... [capped at {_CODENAV_MAX_HITS} files]"
        return {"output": _truncate(out), "exit_code": 0}

class GrepTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import (
            _SENSITIVE_FILE_PATTERNS,
            _is_sensitive_path,
            _resolve_tool_path,
            _resolve_search_root,
            _truncate,
        )
        args: Dict[str, Any] = {}
        _s = (content or "").strip()
        if _s.startswith("{"):
            try:
                args = json.loads(_s)
            except json.JSONDecodeError:
                args = {}
        else:
            args = {"pattern": _s}
        pattern = str(args.get("pattern", "")).strip()
        if not pattern:
            return {"error": "grep: pattern is required", "exit_code": 1}
        ignore_case = bool(args.get("ignore_case"))
        glob_pat = str(args.get("glob", "") or "").strip()
        try:
            max_hits = int(args.get("max_results") or _CODENAV_MAX_HITS)
        except (TypeError, ValueError):
            max_hits = _CODENAV_MAX_HITS
        max_hits = max(1, min(max_hits, _CODENAV_MAX_HITS))
        try:
            root = _resolve_search_root(str(args.get("path", "")))
        except ValueError as e:
            return {"error": f"grep: {e}", "exit_code": 1}

        def _grep():
            import re as _re
            import shutil
            rg = None if ctx.get("governed_read") else shutil.which("rg")
            if rg:
                cmd = [rg, "--line-number", "--no-heading", "--color=never",
                       "--max-count", str(max_hits)]
                if ignore_case:
                    cmd.append("--ignore-case")
                if glob_pat:
                    cmd += ["--glob", glob_pat]
                # --iglob (not --glob) so the exclusion is case-insensitive:
                # on a case-insensitive filesystem "ID_RSA"/"Known_Hosts"
                # resolve to the same secret as their lowercase forms, and the
                # Python fallback below already folds case via _is_sensitive_path.
                for _pat in _SENSITIVE_FILE_PATTERNS:
                    cmd += ["--iglob", f"!*{_pat}*"]
                for _d in _CODENAV_SKIP_DIRS:
                    cmd += ["--glob", f"!**/{_d}/**"]
                cmd += ["--regexp", pattern, root]
                try:
                    import subprocess
                    p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                    lines = [ln for ln in (p.stdout or "").splitlines() if ln][:max_hits]
                    return lines, None
                except subprocess.TimeoutExpired:
                    return None, "grep: timed out"
                except Exception as _e:
                    return None, f"grep: {_e}"
            try:
                rx = _re.compile(pattern, _re.IGNORECASE if ignore_case else 0)
            except _re.error as _e:
                return None, f"grep: bad pattern: {_e}"
            hits = []
            if os.path.isfile(root):
                file_iter = [root]
            else:
                file_iter = []
                for dp, dns, fns in os.walk(root):
                    dns[:] = [d for d in dns if d not in _CODENAV_SKIP_DIRS and
                              not (ctx.get("governed_read") and _is_link_or_junction(os.path.join(dp, d)))]
                    for fn in fns:
                        if glob_pat and not fnmatch.fnmatch(fn, glob_pat):
                            continue
                        file_iter.append(os.path.join(dp, fn))
            for fp in file_iter:
                if len(hits) >= max_hits:
                    break
                if ctx.get("governed_read") and (_is_link_or_junction(fp) or
                        os.path.commonpath((os.path.realpath(fp), os.path.realpath(root))) != os.path.realpath(root)):
                    continue
                if _is_sensitive_path(os.path.realpath(fp)):
                    continue
                try:
                    with open(fp, "r", encoding="utf-8", errors="strict") as f:
                        for i, line in enumerate(f, 1):
                            if rx.search(line):
                                hits.append(f"{fp}:{i}:{line.rstrip()[:_CODENAV_MAX_LINE]}")
                                if len(hits) >= max_hits:
                                    break
                except (UnicodeDecodeError, OSError):
                    continue
            return hits, None

        lines, err = await asyncio.to_thread(_grep)
        if err:
            return {"error": err, "exit_code": 1}
        if not lines:
            return {"output": f"No matches for {pattern!r} under {root}", "exit_code": 0}
        out = "\n".join(ln[:_CODENAV_MAX_LINE] for ln in lines)
        if len(lines) >= max_hits:
            out += f"\n... [capped at {max_hits} matches]"
        return {"output": _truncate(out), "exit_code": 0}

class GetWorkspaceTool:
    """Report the active workspace folder (no args). File tools are confined to
    it; the shell starts there (cwd) but is NOT sandboxed."""
    async def execute(self, content: str, ctx: dict) -> dict:
        from src.tool_execution import get_active_workspace
        ws = get_active_workspace()
        if ws:
            return {
                "output": f"{ws}\n(File tools are confined to this folder; the shell starts "
                          f"here but is not sandboxed and can reach outside it.)",
                "exit_code": 0,
            }
        return {
            "output": "No workspace is set. File tools use the default allowed roots; "
                      "resolve paths from the user or use absolute paths.",
            "exit_code": 0,
        }
