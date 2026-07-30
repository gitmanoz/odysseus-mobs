"""Regression: stream_agent_loop emits `rounds_exhausted` only when the round
cap is hit while still working, and NOT on a normal finish.

The decision is a `for/else` in the loop: the `else` runs only if no `break`
fired (break = done / budget / error). A refactor that adds a stray break or
return, or moves the done-break, could silently flip this. See PR #1999 / #1997.
"""

import asyncio
import json

import src.agent_loop as al


def _collect(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


def _types(chunks):
    out = []
    for c in chunks:
        if c.startswith("data: ") and not c.startswith("data: [DONE]"):
            try:
                out.append(json.loads(c[6:]))
            except Exception:
                pass
    return out


def _patch_common(monkeypatch):
    # Skip RAG/tool-index, MCP, and settings lookups; keep the real loop body,
    # _resolve_tool_blocks, and parse_tool_blocks.
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)

    async def _fake_exec(block, *a, **k):
        return ("bash", {"output": "ok", "exit_code": 0})
    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)


def _run_loop(monkeypatch, round_text, max_rounds=2):
    async def _fake_stream(_candidates, messages, **kwargs):
        yield f'data: {json.dumps({"delta": round_text})}\n\n'
        yield "data: [DONE]\n\n"
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "http://x/v1", "m",
        [{"role": "user", "content": "do a long multi-step task"}],
        max_rounds=max_rounds,
        relevant_tools={"bash"},
    )
    return _types(_collect(gen))


def test_emits_rounds_exhausted_when_cap_hit_mid_task(monkeypatch):
    _patch_common(monkeypatch)
    # Every round returns a tool block -> never "done" -> loop exhausts the cap.
    events = _run_loop(monkeypatch, "```bash\necho hi\n```", max_rounds=2)
    assert any(e.get("type") == "rounds_exhausted" for e in events), events


def test_no_rounds_exhausted_on_normal_finish(monkeypatch):
    _patch_common(monkeypatch)
    # A plain answer (no tool block) -> done-break on round 1 -> no event.
    events = _run_loop(monkeypatch, "All done, here is your answer.", max_rounds=2)
    assert not any(e.get("type") == "rounds_exhausted" for e in events), events


def test_emits_intent_nudge_exhausted_when_cap_is_exhausted(monkeypatch):
    _patch_common(monkeypatch)

    events = _run_loop(monkeypatch, "Let me check the logs", max_rounds=5)

    guard = next((e for e in events if e.get("type") == "intent_nudge_exhausted"), None)
    assert guard is not None, events
    assert guard["reason"] == "intent_without_action_nudge_cap"
    assert guard["nudges"] == 2


def test_workspace_request_retries_text_transcript_and_executes_real_tool(monkeypatch):
    _patch_common(monkeypatch)
    calls = []
    rounds = 0

    async def _fake_exec(block, *args, **kwargs):
        calls.append((block.tool_type, kwargs.get("workspace")))
        return ("workspace", {"output": kwargs.get("workspace"), "exit_code": 0})

    async def _fake_stream(_candidates, messages, **kwargs):
        nonlocal rounds
        rounds += 1
        if rounds == 1:
            # Native models normally treat this as illustrative text, so the
            # chat would render a manual Run button instead of executing it.
            yield 'data: ' + json.dumps({
                "delta": "```bash\ncd /workspace/missao-mobs && pwd\n```\n/workspace/missao-mobs"
            }) + "\n\n"
        elif rounds == 2:
            yield 'data: ' + json.dumps({
                "type": "tool_calls",
                "calls": [{
                    "id": "call_workspace",
                    "name": "get_workspace",
                    "arguments": "{}",
                }],
            }) + "\n\n"
        else:
            yield 'data: ' + json.dumps({"delta": "Workspace verified."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "https://api.openai.com/v1",
        "gpt-test",
        [{
            "role": "user",
            "content": (
                "Execute exactly:\n"
                "cd /workspace/missao-mobs && pwd\n"
                "head -n 5 /workspace/missao-mobs/PROJECT_INDEX.md"
            ),
        }],
        max_rounds=4,
        relevant_tools={"get_workspace", "bash"},
        workspace="/workspace/missao-mobs",
    )
    events = _types(_collect(gen))

    assert calls == [("get_workspace", "/workspace/missao-mobs")]
    assert rounds == 3
    assert not any(
        "/workspace/missao-mobs" in str(e.get("delta") or "")
        for e in events
    )
    metrics = next(e["data"] for e in events if e.get("type") == "metrics")
    assert not any(
        "/workspace/missao-mobs" in str(text)
        for text in metrics.get("round_texts", [])
    )
    assert any(e.get("type") == "tool_start" and e.get("tool") == "get_workspace" for e in events)
    assert not any(
        e.get("reason") == "workspace_tool_evidence_required"
        for e in events
    )


def test_workspace_evidence_guard_reports_failure_instead_of_accepting_fake_output(monkeypatch):
    _patch_common(monkeypatch)

    async def _fake_stream(_candidates, messages, **kwargs):
        yield 'data: ' + json.dumps({
            "delta": (
                "```plaintext /workspace/missao-mobs /project_index.md /src /tests README.md\n"
                "# Missão Móveis Project Index\n"
                "This project is designed to manage mobile application development."
            )
        }) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)
    gen = al.stream_agent_loop(
        "https://api.openai.com/v1",
        "gpt-test",
        [{"role": "user", "content": "Run pwd in /workspace/missao-mobs"}],
        max_rounds=4,
        relevant_tools={"get_workspace", "bash"},
        workspace="/workspace/missao-mobs",
    )
    events = _types(_collect(gen))

    guard = next(
        (e for e in events if e.get("reason") == "workspace_tool_evidence_required"),
        None,
    )
    assert guard is not None, events
    assert guard["nudges"] == 2
    assert guard["workspace"] == "/workspace/missao-mobs"
    assert not any(
        "Missão Móveis" in str(e.get("delta") or "")
        for e in events
    )


def test_emits_loop_breaker_triggered_when_loop_breaker_trips(monkeypatch):
    _patch_common(monkeypatch)

    events = _run_loop(monkeypatch, "```bash\necho hi\n```", max_rounds=6)

    guard = next((e for e in events if e.get("type") == "loop_breaker_triggered"), None)
    assert guard is not None, events
    assert guard["reason"] == "loop_breaker_stall"
