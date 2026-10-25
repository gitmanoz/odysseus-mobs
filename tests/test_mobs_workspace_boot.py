from pathlib import Path

import pytest

from src.mobs_workspace_boot import (
    WorkspaceBootError, classify_request, derive_execution_profile,
    detect_project_profile, requests_governed_proposal, resolve_institutional_root, workspace_boot_inputs,
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


def test_intent_first_enters_proposal_only_for_clear_engineering_requests():
    assert not requests_governed_proposal("Ayla, corrija este bug no código.")
    assert not requests_governed_proposal("Analise este projeto e execute os testes.")
    assert not requests_governed_proposal("Corrija o bug no MOBS Studio.")
    assert requests_governed_proposal("Execute esta operação sob mandato MOBS.")
    assert requests_governed_proposal("Atualize o PROJECT_INDEX e a arquitetura MOBS.")
    assert requests_governed_proposal("Faça o deploy deste projeto.")
    assert not requests_governed_proposal("Explique o que é uma função Python.")
    assert not requests_governed_proposal("Olá, como você está?")


@pytest.mark.parametrize("message", [
    "Teste de estabilidade 01. Responda somente ESTAVEL-01.",
    "Teste de conversa em português.",
    "Os testes passaram.",
])
def test_descriptive_test_word_is_not_both_action_and_engineering_subject(message):
    assert not requests_governed_proposal(message)


@pytest.mark.parametrize("message", [
    "Teste este projeto.",
    "Ayla, teste o código.",
    "Execute os testes e revise este arquivo.",
    "Atualize a arquitetura e a documentação.",
])
def test_engineering_action_with_distinct_subject_still_reaches_classification(message):
    assert not requests_governed_proposal(message)


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


@pytest.mark.parametrize('message', [
    'A build já foi criada, eu só estava corrigindo sua explicação.',
    'Não foi isso. A interface já foi criada na última build, eu só estou explicando.',
    'Foi criada uma build nova?',
    'Você criou a build ou apenas descreveu o projeto?',
    'Como corrigir um bug no código?',
    'Pode me explicar como criar um build?',
    'Quero entender como atualizar este arquivo.',
    'Não crie arquivos nem execute os testes.',
    'Ayla, não corrija o código agora.',
    'Você disse: "Corrija o código do projeto". Isso foi só um exemplo.',
    'Ela pediu para atualizar a arquitetura e a documentação.',
    'Teste do código concluído.',
    'Build do projeto foi criada.',
    'A implementação corrigida já foi testada.',
    'Não, essa versão foi criada para build, não pedi uma tarefa.',
])
def test_conversation_questions_reports_and_negations_do_not_propose(message):
    assert not requests_governed_proposal(message)


@pytest.mark.parametrize('message', [
    'Ayla, pode corrigir este bug no código?',
    'Você consegue me ajudar a corrigir este bug?',
    'Quero que você atualize este arquivo.',
    'Preciso corrigir um bug no código.',
    'Me ajuda a revisar este projeto.',
    'Por favor, implemente a função e adicione os testes.',
    'corrige,o,bug,no,código',
    'faz o seguinte: teste este projeto',
    'A build foi criada. Agora corrija o bug no código.',
    'Não remova arquivos; corrija apenas este bug.',
    'Teste de novo o projeto.',
    'Build the project.',
    'Can you fix this code?',
    'Please implement the code.',
])
def test_explicit_informal_and_polite_requests_still_only_enter_proposal(message):
    assert not requests_governed_proposal(message)


@pytest.mark.parametrize('message', [
    'Execute os testes sob este mandato MOBS.',
    'Revise o snapshot institucional antes da execução governada.',
    'Publique o projeto em produção.',
    'Promova o candidato pela TEB e Controlled Promotion.',
    'Atualize a autoridade institucional PROJECT_INDEX.',
])
def test_explicit_institutional_or_high_impact_requests_enter_proposal(message):
    assert requests_governed_proposal(message)
