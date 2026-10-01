from pathlib import Path

import pytest

from src.mobs_workspace_boot import (
    WorkspaceBootError, classify_request, derive_execution_profile,
    detect_project_profile, resolve_institutional_root, workspace_boot_inputs,
)


INDEX = """# Decision Tree
```
Qual é a tarefa?
├─ Código
│    → AI_CONTEXT.md
├─ Arquitetura
│    → AI_CONTEXT.md
└─ Documentação
     → AI_CONTEXT.md
```
"""


def test_workspace_first_reads_index_before_classification(tmp_path, monkeypatch):
    source = tmp_path / "mobs"; source.mkdir(); (source / "PROJECT_INDEX.md").write_text(INDEX, encoding="utf-8")
    target = tmp_path / "target"; target.mkdir(); (target / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("MOBS_INSTITUTIONAL_ROOT", str(source))
    observed = []
    import src.mobs_workspace_boot as boot
    original = boot._document
    monkeypatch.setattr(boot, "_document", lambda root, name: observed.append(name) or original(root, name))
    result = workspace_boot_inputs("Ayla, analise este projeto.", str(target))
    assert observed == ["PROJECT_INDEX.md"]
    assert result == {"authority_workspace": str(source.resolve()), "category": "Código",
                      "profile": "read_only", "project_profile": "python"}


def test_bug_fix_derives_development_without_granting_category_from_persona():
    assert classify_request("Ayla, corrija este bug no código.", INDEX) == "Código"
    assert derive_execution_profile("Ayla, corrija este bug.") == "development"


def test_ambiguous_or_unclassified_request_fails_closed():
    with pytest.raises(WorkspaceBootError, match="needs clarification"):
        classify_request("Ayla, melhore arquitetura e documentação.", INDEX)
    with pytest.raises(WorkspaceBootError, match="needs clarification"):
        classify_request("Ayla, faça isso.", INDEX)


def test_institutional_root_uses_trusted_runtime_configuration(tmp_path, monkeypatch):
    source = tmp_path / "mobs"; source.mkdir(); (source / "PROJECT_INDEX.md").write_text(INDEX, encoding="utf-8")
    monkeypatch.delenv("MOBS_INSTITUTIONAL_ROOT", raising=False)
    monkeypatch.setenv("MOBS_WORKSPACE_PATH", str(source))
    assert resolve_institutional_root() == str(source.resolve())


def test_project_profile_detection_is_conservative(tmp_path):
    generic = tmp_path / "generic"; generic.mkdir()
    godot = tmp_path / "godot"; godot.mkdir(); (godot / "project.godot").write_text("", encoding="utf-8")
    assert detect_project_profile(str(generic)) == "generic"
    assert detect_project_profile(str(godot)) == "godot"


def test_normal_ui_has_no_manual_category_prompt():
    script = (Path(__file__).resolve().parents[1] / "static/js/chat.js").read_text(encoding="utf-8")
    normal_block = script.split("if (!event.shiftKey)", 1)[1].split("const category", 1)[0]
    assert "window.prompt" not in normal_block
    assert "action: 'propose'" in normal_block
    assert "mobs_authority_workspace" not in script
    assert "authorityWorkspace" not in script
