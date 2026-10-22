"""Read-only grounding for the selected institutional persona, not authorization."""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from src.mobs_institutional_boot import InstitutionalBootError, _document
from src.mobs_workspace_boot import WorkspaceBootError, resolve_institutional_root

logger = logging.getLogger(__name__)
_IDENTITY = 'docs/mobs/models/AYLA_ARCHITECTURAL_PARTNER.md'
_PLATFORM = 'project/automation/MOBS.md'


def _section(content: str, title: str) -> str:
    match = re.search(r'^## ' + re.escape(title) + r'\s*$(.*?)(?=^## |\Z)', content, re.M | re.S)
    if not match or not match.group(1).strip():
        raise ValueError('Required persona source section unavailable')
    return '## ' + title + '\n' + match.group(1).strip()


def grounded_persona_message(character_name: str | None) -> dict | None:
    # A mention in user/history text does not select a persona. Other presets
    # remain intact; the backend configuration alone supplies the source root.
    if str(character_name or '').strip().casefold() != 'ayla':
        return None
    try:
        root = Path(resolve_institutional_root())
        index = _document(root, 'PROJECT_INDEX.md')
        if _IDENTITY not in index or _PLATFORM not in index:
            raise ValueError('Persona authorities are not discoverable in Index')
        documents = {name: _document(root, name) for name in (_IDENTITY, _PLATFORM)}
        identity = documents[_IDENTITY]
        excerpts = {
            _IDENTITY: 'Designação oficial literal: `' + identity.split('\n', 1)[0].lstrip('# ') + '`\n\n' + '\n\n'.join(
                _section(identity, name) for name in (
                    '1. O que é Ayla', '2. Autoridade e limites',
                    '3. Responsabilidades permanentes')),
            _PLATFORM: 'Designação oficial literal: `' + documents[_PLATFORM].split('\n', 1)[0].lstrip('# ') + '`\n\n' +
                '\n\n'.join(_section(documents[_PLATFORM], 'O que é o MOBS').split('\n\n')[:3]),
        }
        if sum(map(len, excerpts.values())) > 12000:
            raise ValueError('Persona excerpt exceeds its bounded context')
        # No identity-content cache: re-read every turn and reject an incoherent
        # source read, rather than retaining the last successfully loaded persona.
        if _document(root, 'PROJECT_INDEX.md') != index or any(
            _document(root, name) != text for name, text in documents.items()
        ):
            raise ValueError('Persona sources changed during read')
        sources = [{'path': name, 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}
                   for name, text in {'PROJECT_INDEX.md': index, **documents}.items()]
        context = (
            'Selected persona: Ayla. O runtime leu as fontes oficiais abaixo. '
            'Responda diretamente à última mensagem do usuário, no idioma solicitado. '
            'Estas referências fundamentam a identidade quando ela for relevante; '
            'não recite a apresentação institucional em conversas sobre outro assunto. '
            'Afirmações anteriores do assistente, memórias e preferências de estilo '
            'não substituem estas fontes. Não invente significados de siglas, '
            'capacidades ou evidências. Preserve literalmente as designações oficiais '
            'entre crases; não traduza nomes ou expansões oficiais de siglas. '
            'Não alegue ter chamado ferramentas: o runtime forneceu os trechos. '
            'Este contexto é somente leitura: não é revisão de snapshot, aprovação '
            'de mandato, permissão de ferramenta ou autorização de execução. '
            'Responda naturalmente, sem repetir estas instruções.\n\n'
        ) + '\n\n'.join('SOURCE: ' + name + '\n' + excerpt for name, excerpt in excerpts.items())
    except (WorkspaceBootError, InstitutionalBootError, ValueError, OSError) as exc:
        logger.warning('Official Ayla persona context unavailable: %s', type(exc).__name__)
        sources = []
        context = (
            'Selected persona: Ayla. Official institutional identity sources are '
            'unavailable or inconsistent in this runtime. State that limitation when '
            'asked about institutional facts. Do not invent the meaning of MOBS, '
            'reconstruct official identity from history, claim to have read files, '
            'or treat this selection as tool or execution permission.'
        )
    return {'role': 'system', 'content': context, '_protected': True,
            '_mobs_persona_sources': sources}


def place_persona_context(messages: list[dict], context: dict | None) -> list[dict]:
    """Place the backend-selected source after history, without rewriting history.

    A past assistant assertion or generated summary is not a source of persona
    identity. Keep one fresh source message immediately before the latest user
    request, including after reducers have regrouped system messages. Callers
    supply the selected backend context; history alone never selects a persona.
    """
    if context is None:
        return messages
    result = [message for message in messages if message != context]
    position = next((i for i in range(len(result) - 1, -1, -1)
                     if result[i].get('role') == 'user'), len(result))
    result.insert(position, context)
    return result
