from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Route MOBS Auto through Ollama native /api/chat and mark only these calls.
replace_once(
    "src/mobs_auto_router.py",
    '''def _openai_compatible_chat_url(base: str) -> str:\n    """Use Ollama's OpenAI-compatible chat endpoint for MOBS Auto.\n\n    Odysseus already sends ``think: false`` for thinking-capable models on this\n    endpoint. Keeping this decision inside the MOBS route avoids changing the\n    behavior of manually selected Ollama models.\n    """\n    parsed = urlparse(normalize_base(base))\n    path = (parsed.path or "").rstrip("/")\n    if path.endswith("/v1"):\n        target_path = f"{path}/chat/completions"\n    elif path:\n        target_path = f"{path}/v1/chat/completions"\n    else:\n        target_path = "/v1/chat/completions"\n    return urlunparse(parsed._replace(path=target_path, query="", fragment=""))\n''',
    '''def _ollama_native_chat_url(base: str) -> str:\n    """Return Ollama's native /api/chat endpoint for MOBS Auto."""\n    parsed = urlparse(normalize_base(base))\n    path = (parsed.path or "").rstrip("/")\n    for suffix in ("/v1/chat/completions", "/v1", "/api/chat", "/api"):\n        if path.endswith(suffix):\n            path = path[: -len(suffix)]\n            break\n    target_path = (path.rstrip("/") + "/api/chat") if path else "/api/chat"\n    return urlunparse(parsed._replace(path=target_path, query="", fragment=""))\n''',
)
replace_once(
    "src/mobs_auto_router.py",
    '''                endpoint_url=_openai_compatible_chat_url(base),\n                model=candidate,\n                headers=build_headers(endpoint.api_key or "", endpoint.base_url or "") if endpoint.api_key else {},\n''',
    '''                endpoint_url=_ollama_native_chat_url(base),\n                model=candidate,\n                headers={\n                    **(build_headers(endpoint.api_key or "", endpoint.base_url or "") if endpoint.api_key else {}),\n                    "X-MOBS-Auto": "1",\n                },\n''',
)

# Keep the tests aligned with the intentional endpoint change.
replace_once(
    "tests/test_mobs_auto_router.py",
    "    _openai_compatible_chat_url,\n",
    "    _ollama_native_chat_url,\n",
)
replace_once(
    "tests/test_mobs_auto_router.py",
    '''def test_mobs_auto_uses_ollama_openai_compatible_endpoint():\n    assert _openai_compatible_chat_url("http://host.docker.internal:11434") == (\n        "http://host.docker.internal:11434/v1/chat/completions"\n    )\n    assert _openai_compatible_chat_url("http://localhost:11434/v1") == (\n        "http://localhost:11434/v1/chat/completions"\n    )\n''',
    '''def test_mobs_auto_uses_ollama_native_endpoint():\n    assert _ollama_native_chat_url("http://host.docker.internal:11434") == (\n        "http://host.docker.internal:11434/api/chat"\n    )\n    assert _ollama_native_chat_url("http://localhost:11434/v1") == (\n        "http://localhost:11434/api/chat"\n    )\n    assert _ollama_native_chat_url("http://localhost:11434/v1/chat/completions") == (\n        "http://localhost:11434/api/chat"\n    )\n''',
)

# 2) Consume the internal marker before the upstream request and disable thinking
# only for MOBS Auto on both sync/async streaming paths.
replace_once(
    "src/llm_core.py",
    '''    elif provider == "ollama":\n        target_url = _normalize_ollama_url(url)\n        h = {"Content-Type": "application/json"}\n        if headers:\n            h.update(headers)\n        payload = _build_ollama_payload(\n            model, messages_copy, temperature, max_tokens,\n            stream=False, num_ctx=get_context_length(url, model),\n        )\n''',
    '''    elif provider == "ollama":\n        target_url = _normalize_ollama_url(url)\n        h = {"Content-Type": "application/json"}\n        if headers:\n            h.update(headers)\n        mobs_auto_request = h.pop("X-MOBS-Auto", None) == "1"\n        payload = _build_ollama_payload(\n            model, messages_copy, temperature, max_tokens,\n            stream=False, num_ctx=get_context_length(url, model),\n        )\n        if mobs_auto_request:\n            payload["think"] = False\n''',
)
replace_once(
    "src/llm_core.py",
    '''    elif provider == "ollama":\n        target_url = _normalize_ollama_url(url)\n        h = {"Content-Type": "application/json"}\n        if headers:\n            h.update(headers)\n        payload = _build_ollama_payload(\n            model, messages_copy, temperature, max_tokens,\n            stream=True, tools=tools, num_ctx=get_context_length(url, model),\n        )\n''',
    '''    elif provider == "ollama":\n        target_url = _normalize_ollama_url(url)\n        h = {"Content-Type": "application/json"}\n        if headers:\n            h.update(headers)\n        mobs_auto_request = h.pop("X-MOBS-Auto", None) == "1"\n        payload = _build_ollama_payload(\n            model, messages_copy, temperature, max_tokens,\n            stream=True, tools=tools, num_ctx=get_context_length(url, model),\n        )\n        if mobs_auto_request:\n            payload["think"] = False\n''',
)

# 3) Prevent the symbolic alias from leaking through any visible text node while
# MOBS Auto is selected. Attributes and form values remain untouched.
replace_once(
    "static/js/modelPicker.js",
    '''function _applyMobsAutoRolePresentation() {\n  if (!_mobsAutoPresentationActive) return;\n  const history = document.getElementById('chat-history');\n  if (!history) return;\n  history.querySelectorAll('.msg-ai .role, .agent-thread .role').forEach(_presentMobsAutoRole);\n}\n''',
    '''function _sanitizeMobsAutoVisibleText(root = document.body) {\n  if (!root) return;\n  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);\n  const nodes = [];\n  while (walker.nextNode()) nodes.push(walker.currentNode);\n  nodes.forEach(node => {\n    const parent = node.parentElement;\n    if (!parent || ['SCRIPT', 'STYLE', 'TEXTAREA'].includes(parent.tagName)) return;\n    if ((node.nodeValue || '').includes(MOBS_AUTO_MODEL_ID)) {\n      node.nodeValue = node.nodeValue.split(MOBS_AUTO_MODEL_ID).join(MOBS_AUTO_DISPLAY);\n    }\n  });\n}\n\nfunction _applyMobsAutoRolePresentation() {\n  if (!_mobsAutoPresentationActive) return;\n  const history = document.getElementById('chat-history');\n  if (history) history.querySelectorAll('.msg-ai .role, .agent-thread .role').forEach(_presentMobsAutoRole);\n  _sanitizeMobsAutoVisibleText();\n}\n''',
)

print("Applied final MOBS Auto alias and thinking fixes")
