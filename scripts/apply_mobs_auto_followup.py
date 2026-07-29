from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: str, old: str, new: str, expected: int) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} matches, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Preserve symbolic identity and the resolved execution model separately.
replace_once(
    "routes/chat_routes.py",
    """    execution.model = route.model\n    execution.endpoint_url = route.endpoint_url\n    execution.headers = route.headers\n""",
    """    execution.model = route.model\n    execution.endpoint_url = route.endpoint_url\n    execution.headers = route.headers\n    execution.requested_model = route.requested_model\n    execution.display_name = route.display_name\n    execution.disable_thinking = route.disable_thinking\n""",
)
replace_once(
    "routes/chat_routes.py",
    """            _model_info = {\"type\": \"model_info\", \"model\": sess.model}\n""",
    """            _model_info = {\n                \"type\": \"model_info\",\n                \"model\": sess.model,\n                \"requested_model\": getattr(sess, \"requested_model\", sess.model),\n            }\n""",
)
replace_all(
    "routes/chat_routes.py",
    """                _requested_model = sess.model\n""",
    """                _requested_model = getattr(sess, \"requested_model\", sess.model)\n""",
    expected=2,
)

# Ollama's /v1 compatibility surface accepts `think: false`; do not depend on
# model-name heuristics because deployed tags may include suffixes/aliases.
replace_all(
    "src/llm_core.py",
    """        if _is_ollama_openai_compat_url(url) and _supports_thinking(model):\n            payload[\"think\"] = False\n""",
    """        if _is_ollama_openai_compat_url(url):\n            payload[\"think\"] = False\n""",
    expected=2,
)

# Public identity is MOBS Auto; the concrete model remains available in the
# popup and metrics as the actual model.
replace_once(
    "static/js/chatRenderer.js",
    """export function shortModel(name) {\n  if (!name) return '...';\n  if (typeof name !== 'string') name = String(name);\n""",
    """export function shortModel(name) {\n  if (!name) return '...';\n  if (typeof name !== 'string') name = String(name);\n  if (name === '__mobs_auto__') return 'MOBS Auto';\n""",
)
replace_once(
    "static/js/chatRenderer.js",
    """export function modelRouteLabel(requestedModel, actualModel) {\n  const requested = modelValue(requestedModel);\n  const actual = modelValue(actualModel) || requested;\n  if (!requested || sameModelName(requested, actual)) return shortModel(actual || requested);\n  return shortModel(requested) + ' -> ' + shortModel(actual);\n}\n""",
    """export function modelRouteLabel(requestedModel, actualModel) {\n  const requested = modelValue(requestedModel);\n  const actual = modelValue(actualModel) || requested;\n  if (requested === '__mobs_auto__') return 'MOBS Auto';\n  if (!requested || sameModelName(requested, actual)) return shortModel(actual || requested);\n  return shortModel(requested) + ' -> ' + shortModel(actual);\n}\n""",
)
replace_once(
    "static/js/chatRenderer.js",
    """export function applyModelColor(roleEl, modelName) {\n  if (!modelName) return;\n  const color = modelColor(modelName);\n""",
    """export function applyModelColor(roleEl, modelName) {\n  if (!modelName) return;\n  roleEl.dataset.actualModel = modelName;\n  const color = modelColor(modelName);\n""",
)
replace_once(
    "static/js/chatRenderer.js",
    """      const info = getModelInfo(modelName);\n      const short = shortModel(modelName);\n      const logoHtml = providerLogo(modelName);\n""",
    """      const activeModelName = roleEl.dataset.actualModel || modelName;\n      const info = getModelInfo(activeModelName);\n      const short = shortModel(activeModelName);\n      const logoHtml = providerLogo(activeModelName);\n""",
)
replace_all(
    "static/js/chatRenderer.js",
    """uiModule.esc(modelName.split('/').pop())""",
    """uiModule.esc(activeModelName.split('/').pop())""",
    expected=1,
)
replace_all(
    "static/js/chatRenderer.js",
    """window._realContextLengths[modelName]""",
    """window._realContextLengths[activeModelName]""",
    expected=2,
)

print("MOBS Auto follow-up patch applied")
