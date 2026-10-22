from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
STYLE = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
CHAT = (ROOT / "static" / "js" / "chat.js").read_text(encoding="utf-8")
THEME = (ROOT / "static" / "js" / "theme.js").read_text(encoding="utf-8")


def test_product_shell_keeps_primary_project_and_engineering_actions():
    assert '<body class="product-shell-v1">' in INDEX
    assert 'id="product-workspace-btn"' in INDEX
    assert 'id="mobs-toggle-btn"' in INDEX
    assert '>Engineering<' in INDEX
    assert "action: 'propose'" in CHAT


def test_normal_shell_does_not_require_engineering_or_mode_selection():
    engineering = INDEX[INDEX.index('id="mobs-toggle-btn"'):INDEX.index('id="mobs-toggle-btn"') + 500]
    assert "data-product-secondary" in engineering
    for identifier in ('mode-agent-btn', 'mode-chat-btn'):
        snippet = INDEX[INDEX.index(f'id="{identifier}"'):INDEX.index(f'id="{identifier}"') + 300]
        assert "data-product-secondary" in snippet


def test_secondary_surfaces_are_hidden_without_removing_their_capabilities():
    assert 'body.product-shell-v1:not(.product-shell-advanced) [data-product-secondary]' in STYLE
    for identifier in ('rail-memory', 'rail-cookbook', 'rail-research', 'rail-email', 'rail-settings'):
        assert f'id="{identifier}"' in INDEX
        start = INDEX.index(f'id="{identifier}"')
        assert 'data-product-secondary' in INDEX[start:start + 500]
    assert 'id="product-advanced-btn"' in INDEX


def test_product_shell_reuses_existing_workspace_and_mobs_paths():
    assert "const workspaceBtn = el('overflow-workspace-btn');" in APP
    assert "document.body.classList.toggle('product-shell-advanced', isOpen);" in APP
    assert "MOBS workspace-first mode ready" in CHAT
    assert "function setProductActivity(state, label)" in CHAT


def test_activity_is_derived_from_existing_stream_events():
    for event in ('tool_start', 'agent_step', 'mobs_mandate_proposal', 'mobs_promotion_applied', 'institutional_verified'):
        assert event in CHAT
    assert "setProductActivity('executing', 'Executando ferramenta')" in CHAT
    assert "setProductActivity('awaiting-decision', 'Aguardando revisão MOBS')" in CHAT


def test_memory_and_skills_remain_available_and_graphite_is_default():
    assert 'id="tool-memory-btn"' in INDEX
    assert 'Skills' in INDEX
    assert "DEFAULT_THEME = 'studio'" in THEME
    assert 'graphite:' in THEME  # Existing palette remains selectable.
