"""Apply the small MOBS Auto integration patch to an Odysseus checkout.

Run once from the repository root:
    python scripts/install_mobs_auto.py

The script is idempotent and aborts if expected anchors are missing.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"already patched: {path.relative_to(ROOT)}")
        return
    if old not in text:
        raise SystemExit(f"anchor not found in {path.relative_to(ROOT)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched: {path.relative_to(ROOT)}")


def patch_model_picker() -> None:
    path = ROOT / "static/js/modelPicker.js"
    replace_once(
        path,
        "const API_BASE = window.location.origin;\n",
        "const API_BASE = window.location.origin;\n"
        "const MOBS_AUTO_MODEL_ID = '__mobs_auto__';\n"
        "const MOBS_GENERAL_MODEL = 'qwen3:8b';\n"
        "const MOBS_CODER_MODEL = 'qwen2.5-coder:7b';\n",
    )
    replace_once(
        path,
        "    return sortModelObjects(result);\n",
        "    const general = result.find(m => m.mid === MOBS_GENERAL_MODEL && !m.stale);\n"
        "    const coder = result.find(m => m.mid === MOBS_CODER_MODEL && !m.stale);\n"
        "    if (general && coder) {\n"
        "      result.unshift({\n"
        "        key: MOBS_AUTO_MODEL_ID,\n"
        "        mid: MOBS_AUTO_MODEL_ID,\n"
        "        display: 'MOBS Auto',\n"
        "        url: general.url,\n"
        "        endpointId: general.endpointId,\n"
        "        epName: 'Automatic routing',\n"
        "        category: 'local',\n"
        "        providerText: 'MOBS Auto automatic routing qwen3 coder',\n"
        "        stale: false,\n"
        "        offline: false,\n"
        "      });\n"
        "    }\n"
        "    return sortModelObjects(result);\n",
    )
    replace_once(
        path,
        "      const _mlogo = providerLogo(m.mid);\n",
        "      const _mlogo = m.mid === MOBS_AUTO_MODEL_ID ? '' : providerLogo(m.mid);\n",
    )
    replace_once(
        path,
        "      const favDot = document.createElement('button');\n",
        "      const favDot = document.createElement('button');\n"
        "      if (m.mid === MOBS_AUTO_MODEL_ID) favDot.style.visibility = 'hidden';\n",
    )


def patch_session_routes() -> None:
    path = ROOT / "routes/session_routes.py"
    replace_once(
        path,
        "from src.request_models import SessionResponse\n",
        "from src.request_models import SessionResponse\n"
        "from src.mobs_auto_router import MOBS_AUTO_MODEL_ID, is_mobs_auto\n",
    )
    replace_once(
        path,
        "        if skip_val:\n"
        "            # skip_validation = trust the caller and do NOT probe /v1/models.\n",
        "        if is_mobs_auto(model_to_use):\n"
        "            # MOBS Auto is a strategy sentinel, not a provider model.\n"
        "            # The concrete route is resolved for each turn in chat_routes.\n"
        "            pass\n"
        "        elif skip_val:\n"
        "            # skip_validation = trust the caller and do NOT probe /v1/models.\n",
    )


def patch_chat_routes() -> None:
    path = ROOT / "routes/chat_routes.py"
    replace_once(
        path,
        "import asyncio\n",
        "import asyncio\nimport copy\n",
    )
    replace_once(
        path,
        "from src.image_model_ids import looks_like_image_generation_model\n",
        "from src.image_model_ids import looks_like_image_generation_model\n"
        "from src.mobs_auto_router import is_mobs_auto, resolve_mobs_auto_route\n",
    )

    helper_anchor = "logger = logging.getLogger(__name__)\n"
    helper = '''logger = logging.getLogger(__name__)\n\n\ndef _resolved_mobs_auto_session(\n    sess,\n    message: str,\n    *,\n    owner: str | None = None,\n    chat_mode: str = "chat",\n    tool_intent=None,\n    workspace: str = "",\n    plan_mode: bool = False,\n):\n    """Return a shallow execution copy when the session uses MOBS Auto.\n\n    The manager/DB session keeps the symbolic strategy while the request-local\n    copy carries the concrete model and endpoint selected for this turn. History\n    remains shared, so existing persistence and post-response behavior continue.\n    """\n    if not is_mobs_auto(getattr(sess, "model", "")):\n        return sess\n    route = resolve_mobs_auto_route(\n        message,\n        owner=owner,\n        chat_mode=chat_mode,\n        tool_intent=tool_intent,\n        workspace=workspace,\n        plan_mode=plan_mode,\n    )\n    execution = copy.copy(sess)\n    execution.model = route.model\n    execution.endpoint_url = route.endpoint_url\n    execution.headers = route.headers\n    logger.info(\n        "MOBS Auto resolved session=%s model=%s reason=%s fallback=%s",\n        getattr(sess, "id", ""), route.model, route.reason, route.used_fallback,\n    )\n    return execution\n'''
    replace_once(path, helper_anchor, helper)

    replace_once(
        path,
        "        _recover_empty_session_model(sess, session, owner=owner)\n"
        "        if not getattr(sess, \"model\", \"\").strip():\n",
        "        _recover_empty_session_model(sess, session, owner=owner)\n"
        "        try:\n"
        "            sess = _resolved_mobs_auto_session(sess, message, owner=owner)\n"
        "        except RuntimeError as exc:\n"
        "            raise HTTPException(503, str(exc))\n"
        "        if not getattr(sess, \"model\", \"\").strip():\n",
    )

    stream_old = (
        "            _recover_empty_session_model(sess, session, owner=owner)\n"
        "            if not getattr(sess, \"model\", \"\").strip():\n"
    )
    stream_new = (
        "            _recover_empty_session_model(sess, session, owner=owner)\n"
        "            try:\n"
        "                sess = _resolved_mobs_auto_session(\n"
        "                    sess, message, owner=owner, chat_mode=chat_mode,\n"
        "                    tool_intent=_tool_intent, workspace=workspace, plan_mode=plan_mode,\n"
        "                )\n"
        "            except RuntimeError as exc:\n"
        "                raise HTTPException(503, str(exc))\n"
        "            if not getattr(sess, \"model\", \"\").strip():\n"
    )
    replace_once(path, stream_old, stream_new)


def main() -> None:
    patch_model_picker()
    patch_session_routes()
    patch_chat_routes()
    print("MOBS Auto integration applied. Review git diff, then run targeted tests.")


if __name__ == "__main__":
    main()
