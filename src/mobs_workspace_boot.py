"""Workspace-first preparation for the existing governed MOBS proposal flow."""
from __future__ import annotations

import os
import re
from pathlib import Path

from src.mobs_institutional_boot import InstitutionalBootError, _document
from src.tool_execution import vet_workspace


class WorkspaceBootError(ValueError):
    pass


_ROOT_ENV_KEYS = ("MOBS_INSTITUTIONAL_ROOT", "MOBS_WORKSPACE_PATH", "MOBS_WORKSPACE")

# Intent-first is deliberately narrower than the Decision Tree classifier. It
# decides only whether a human request should enter the governed *proposal*
# path; the Index remains the authority that classifies that proposal.
# Closed request forms rather than stems ("criada" is not "crie").
_GOVERNED_ACTION_RE = re.compile(
    r"\b(?:analise|analisar|inspecione|inspecionar|revise|revisar|"
    r"corrija|corrige|corrigir|conserte|conserta|consertar|implemente|implementar|"
    r"adicione|adiciona|adicionar|atualize|atualiza|atualizar|remova|remover|"
    r"refatore|refatora|refatorar|edite|edita|editar|crie|cria|criar|"
    r"teste|testa|testar|valide|validar|execute|executar|roda|rode|rodar|"
    r"faça|faca|faz|fazer|build|fix|implement|add|remove|refactor)\b",
    re.IGNORECASE,
)
_REQUEST_PREFIX_RE = re.compile(
    r"^(?:(?:por favor|por gentileza|please|então|entao|agora)\s+)*"
    r"(?:(?:ser[aá] que\s+)?(?:voc[eê]|voce|vc|tu)\s+)?"
    r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?|"
    r"(?:pode|poderia|consegue|conseguiria)\s+(?:me\s+)?"
    r"(?:(?:ajudar|ajuda)\s+(?:a\s+)?)?|"
    r"(?:quero|queria|preciso|gostaria)\s+(?:(?:que\s+)(?:(?:voc[eê]|vc)\s+)?|de\s+)?|"
    r"(?:me\s+)?(?:ajude|ajuda)\s+(?:a\s+)?|(?:vamos|bora)\s+)?",
    re.IGNORECASE,
)
_GOVERNED_SUBJECT_RE = re.compile(
    r"\b(?:bug|c[oó]digo|code|teste|tests?|lint|build|arquivo|m[oó]dulo|"
    r"fun[cç][aã]o|classe|reposit[oó]rio|repo|projeto|project|workspace|"
    r"arquitetura|architect\w*|documenta[cç][aã]o|document\w*)\b",
    re.IGNORECASE,
)


def resolve_institutional_root() -> str:
    """Resolve the institutional root only from trusted runtime configuration."""
    for key in _ROOT_ENV_KEYS:
        value = str(os.getenv(key, "")).strip()
        if value:
            resolved = vet_workspace(value)
            if resolved and (Path(resolved) / "PROJECT_INDEX.md").is_file():
                return resolved
            raise WorkspaceBootError(f"Configured institutionalRoot from {key} is invalid")
    raise WorkspaceBootError("MOBS institutionalRoot is not configured")


def decision_tree_categories(index: str) -> list[str]:
    """Extract canonical category labels from the Index rather than duplicating them."""
    section = index.split("# Decision Tree", 1)
    if len(section) != 2:
        raise WorkspaceBootError("Index has no Decision Tree")
    fences = section[1].split("```")
    if len(fences) < 3:
        raise WorkspaceBootError("Unsupported Decision Tree format")
    categories = re.findall(r"(?m)^[├└]─\s*([^\r\n]+?)\s*$", fences[1])
    if not categories or len(categories) != len(set(categories)):
        raise WorkspaceBootError("Decision Tree categories are missing or ambiguous")
    return categories


def requests_governed_proposal(user_request: str) -> bool:
    """Return true only for an explicit engineering request, never for chat.

    This does not infer authorization, capabilities, a Decision Tree category,
    or an execution mode. It merely enters the existing workspace-first
    proposal path, where those values are derived and verified independently.
    """
    text = str(user_request or '')
    # Quoted examples and code are evidence, not requests to execute them.
    text = re.sub(r"""```.*?```|"[^"\n]*"|“[^”\n]*”|'[^'\n]*'""", ' ', text, flags=re.S)
    for clause in re.split(r'[.;!?\n]+', text):
        clause = re.sub(r'[,\s]+', ' ', clause).strip()
        # Optional vocative/short conversational lead-in; it never changes persona.
        clause = re.sub(r'^(?:ayla|assistente|por favor|por gentileza)\b\s*', '', clause, flags=re.I)
        clause = re.sub(r'^(?:tarefa|objetivo|faz o seguinte|faça o seguinte)\s*:\s*', '', clause, flags=re.I)
        prefix = _REQUEST_PREFIX_RE.match(clause)
        candidate = clause[prefix.end():] if prefix else clause
        action = _GOVERNED_ACTION_RE.match(candidate)
        # Nouns at the start of a statement can share an imperative spelling:
        # "teste do código" / "build do projeto". A nominal complement is not
        # evidence of a request (the adverbial "de novo" is different).
        if action and re.match(r"\s+(?:de|do|da|dos|das)\b(?!\s+novo\b)", candidate[action.end():], re.I):
            continue
        if action and any(subject.start() >= action.end()
                          for subject in _GOVERNED_SUBJECT_RE.finditer(candidate)):
            return True
    return False



def classify_request(user_request: str, index: str) -> str:
    """Conservatively classify common execution intents into an Index category."""
    text = " ".join(str(user_request or "").lower().split())
    if not text:
        raise WorkspaceBootError("MOBS proposal needs a user request")
    categories = set(decision_tree_categories(index))
    rules = {
        "Código": (
            r"\b(bug|c[oó]digo|code|teste|tests?|lint|build|refator|implement|corrij|"
            r"arquivo|m[oó]dulo|fun[cç][aã]o|classe|reposit[oó]rio|repo)\w*\b",
            r"\b(analise|analisar|inspecione|revise)\b.*\b(projeto|workspace|reposit[oó]rio|repo)\b",
        ),
        "Arquitetura": (r"\b(arquitetura|arquitetural|architecture|design\s+de\s+sistema)\w*\b",),
        "Documentação": (r"\b(documenta[cç][aã]o|documento|readme|changelog|history|manual)\w*\b",),
        "Produto": (r"\b(produto|prd|roadmap|jornada\s+do\s+usu[aá]rio|business\s+model)\b",),
        "Branding": (r"\b(branding|marca|logo|identidade\s+visual)\b",),
        "Assets": (r"\b(asset|sprite|textura|[ií]cone)\w*\b",),
        "Gamificação": (r"\b(gamifica[cç][aã]o|xp|ranking|conquista)\w*\b",),
        "Landing Page": (r"\b(landing\s+page|p[aá]gina\s+de\s+vendas)\b",),
    }
    matched = []
    for category, patterns in rules.items():
        if category in categories and any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            matched.append(category)
    if len(matched) != 1:
        detail = "no safe category matched" if not matched else f"ambiguous categories: {', '.join(sorted(matched))}"
        raise WorkspaceBootError(f"Task classification needs clarification ({detail})")
    return matched[0]


def derive_execution_profile(user_request: str) -> str:
    text = str(user_request or "").lower()
    mutation = re.search(
        r"\b(corrij\w*|implemente?\w*|alter\w*|edite?\w*|crie?\w*|adicione?\w*|"
        r"remova?\w*|conserte?\w*|fix(?:e|ar)?\w*)\b", text, re.IGNORECASE)
    return "development" if mutation else "read_only"


def detect_project_profile(target_workspace: str) -> str:
    root_value = vet_workspace(target_workspace or "")
    if not root_value:
        raise WorkspaceBootError("Invalid target workspace")
    root = Path(root_value)
    if (root / "project.godot").is_file():
        return "godot"
    if any((root / name).is_file() for name in ("pyproject.toml", "setup.py", "setup.cfg", "tox.ini")) \
            or any(item.is_file() for item in root.glob("requirements*.txt")):
        return "python"
    return "generic"


def workspace_boot_inputs(
    user_request: str,
    target_workspace: str,
    *,
    category: str | None = None,
    profile: str | None = None,
    project_profile: str | None = None,
) -> dict[str, str]:
    """Read PROJECT_INDEX first, then derive or validate proposal inputs."""
    source = resolve_institutional_root()
    try:
        index = _document(Path(source), "PROJECT_INDEX.md")
    except InstitutionalBootError as exc:
        raise WorkspaceBootError(str(exc)) from exc
    selected_category = str(category or "").strip()
    if selected_category:
        if selected_category not in decision_tree_categories(index):
            raise WorkspaceBootError("Selected category is not present in the Decision Tree")
    else:
        selected_category = classify_request(user_request, index)
    return {
        "authority_workspace": source,
        "category": selected_category,
        "profile": str(profile or "").strip() or derive_execution_profile(user_request),
        "project_profile": str(project_profile or "").strip() or detect_project_profile(target_workspace),
    }
