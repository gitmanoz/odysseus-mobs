from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"anchor not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Preserve symbolic/public identity while retaining the concrete routed model.
replace_once(
    "routes/chat_routes.py",
    """    execution.model = route.model
    execution.endpoint_url = route.endpoint_url
    execution.headers = route.headers
""",
    """    execution.model = route.model
    execution.endpoint_url = route.endpoint_url
    execution.headers = route.headers
    execution.mobs_auto_requested_model = route.requested_model
    execution.mobs_auto_display_name = route.display_name
    execution.mobs_auto_actual_model = route.model
""",
)
replace_once(
    "routes/chat_routes.py",
    """            _model_info = {"type": "model_info", "model": sess.model}
""",
    """            _public_model = getattr(sess, "mobs_auto_display_name", None) or sess.model
            _model_info = {"type": "model_info", "model": _public_model}
            if getattr(sess, "mobs_auto_actual_model", None):
                _model_info["actual_model"] = sess.mobs_auto_actual_model
                _model_info["requested_model"] = getattr(sess, "mobs_auto_requested_model", "__mobs_auto__")
""",
)

p = Path("routes/chat_routes.py")
text = p.read_text(encoding="utf-8")
old = """                _requested_model = sess.model
                _actual_model = None
"""
new = """                _requested_model = getattr(sess, "mobs_auto_requested_model", None) or sess.model
                _actual_model = getattr(sess, "mobs_auto_actual_model", None)
"""
if old in text:
    text = text.replace(old, new)
elif new not in text:
    raise SystemExit("requested/actual model anchors not found")
p.write_text(text, encoding="utf-8")

# Native Ollama requests must disable reasoning too; /v1 already receives this.
replace_once(
    "src/llm_core.py",
    """    if tools:
        payload["tools"] = tools
    return payload
""",
    """    if tools:
        payload["tools"] = tools
    if _supports_thinking(model):
        payload["think"] = False
    return payload
""",
)

# Ensure alias never leaks and route details remain available on click.
replace_once(
    "static/js/chatRenderer.js",
    """const CHECK_ICON =""",
    """const MOBS_AUTO_MODEL_ID = '__mobs_auto__';
const MOBS_AUTO_DISPLAY = 'MOBS Auto';
const CHECK_ICON =""",
)
replace_once(
    "static/js/chatRenderer.js",
    """export function shortModel(name) {
  if (!name) return '...';
  if (typeof name !== 'string') name = String(name);
""",
    """export function shortModel(name) {
  if (!name) return '...';
  if (typeof name !== 'string') name = String(name);
  if (name.trim() === MOBS_AUTO_MODEL_ID || name.trim() === MOBS_AUTO_DISPLAY) return MOBS_AUTO_DISPLAY;
""",
)
replace_once(
    "static/js/chatRenderer.js",
    """  if (!requested || sameModelName(requested, actual)) return shortModel(actual || requested);
  return shortModel(requested) + ' -> ' + shortModel(actual);
""",
    """  if (requested === MOBS_AUTO_MODEL_ID || requested === MOBS_AUTO_DISPLAY) return MOBS_AUTO_DISPLAY;
  if (!requested || sameModelName(requested, actual)) return shortModel(actual || requested);
  return shortModel(requested) + ' -> ' + shortModel(actual);
""",
)
replace_once(
    "static/js/chatRenderer.js",
    """      const info = getModelInfo(modelName);
      const short = shortModel(modelName);
      const logoHtml = providerLogo(modelName);
""",
    """      const popupModel = roleEl.dataset.mobsActualModel || modelName;
      const info = getModelInfo(popupModel);
      const short = shortModel(popupModel);
      const logoHtml = providerLogo(popupModel);
""",
)
replace_once(
    "static/js/chatRenderer.js",
    """      html += '<div><span class="ctx-label">Model</span> ' + uiModule.esc(modelName.split('/').pop()) + '</div>';
""",
    """      html += '<div><span class="ctx-label">Model</span> ' + uiModule.esc(popupModel.split('/').pop()) + '</div>';
""",
)

# Streaming metadata should consistently preserve concrete model for the popup.
replace_once(
    "static/js/chat.js",
    """                    holder._requestedModel = json.requested_model || json.model || holder._requestedModel;
                    holder._actualModel = json.model || holder._actualModel || holder._requestedModel;
""",
    """                    holder._requestedModel = json.requested_model || json.model || holder._requestedModel;
                    holder._actualModel = json.actual_model || json.model || holder._actualModel || holder._requestedModel;
                    if (json.actual_model) roleEl.dataset.mobsActualModel = json.actual_model;
""",
)

# Strengthen the existing presentation observer: retain actual model and scrub alias globally.
p = Path("static/js/modelPicker.js")
text = p.read_text(encoding="utf-8")
old = """  const hasProviderLogo = !!roleEl.querySelector('.role-provider-logo');
  if (visibleText === MOBS_AUTO_DISPLAY && !hasProviderLogo) return;

  [...roleEl.childNodes].forEach(node => {
"""
new = """  const holder = roleEl.closest('.msg-ai, .agent-thread');
  const actualModel = (holder && holder._actualModel) || roleEl.dataset.mobsActualModel || '';
  if (actualModel && actualModel !== MOBS_AUTO_MODEL_ID && actualModel !== MOBS_AUTO_DISPLAY) {
    roleEl.dataset.mobsActualModel = actualModel;
  } else if (visibleText && visibleText !== MOBS_AUTO_MODEL_ID && visibleText !== MOBS_AUTO_DISPLAY) {
    roleEl.dataset.mobsActualModel = visibleText;
  }
  const hasProviderLogo = !!roleEl.querySelector('.role-provider-logo');
  if (visibleText === MOBS_AUTO_DISPLAY && !hasProviderLogo) return;

  [...roleEl.childNodes].forEach(node => {
"""
if old not in text:
    if new not in text:
        raise SystemExit("modelPicker role anchor not found")
else:
    text = text.replace(old, new, 1)
old2 = """  history.querySelectorAll('.msg-ai .role, .agent-thread .role').forEach(_presentMobsAutoRole);
"""
new2 = """  history.querySelectorAll('.msg-ai .role, .agent-thread .role').forEach(_presentMobsAutoRole);
  document.querySelectorAll('[data-model], .chat-header, .session-header, .chat-meta').forEach(el => {
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.includes(MOBS_AUTO_MODEL_ID)) {
        node.textContent = node.textContent.replaceAll(MOBS_AUTO_MODEL_ID, MOBS_AUTO_DISPLAY);
      }
    }
  });
"""
if old2 not in text:
    if new2 not in text:
        raise SystemExit("modelPicker presentation anchor not found")
else:
    text = text.replace(old2, new2, 1)
p.write_text(text, encoding="utf-8")
