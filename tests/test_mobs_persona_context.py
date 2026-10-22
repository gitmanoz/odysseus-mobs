from types import SimpleNamespace
from pathlib import Path
import copy

import pytest

from src.chat_processor import ChatProcessor
from src.mobs_workspace_boot import requests_governed_proposal
from src.mobs_persona_context import grounded_persona_message

AYLA = 'docs/mobs/models/AYLA_ARCHITECTURAL_PARTNER.md'
PLATFORM = 'project/automation/MOBS.md'


@pytest.fixture
def authorities(tmp_path, monkeypatch):
    # Synthetic source fixtures, never an institutional approval or authority.
    root=tmp_path/'mobs';root.mkdir()
    (root/'PROJECT_INDEX.md').write_text('Index\n'+AYLA+'\n'+PLATFORM,encoding='utf-8')
    for name,text in {
        AYLA: '# Ayla\n## 1. O que é Ayla\nParceira arquitetural do MOBS.\n## 2. Autoridade e limites\nO fundador mantém a decisão final.\n## 3. Responsabilidades permanentes\nPreservar coesão e não substituir o fundador.\n',
        PLATFORM: '# MOBS — Mission Orchestration & Build System\n## O que é o MOBS\nPlataforma de engenharia do Ecossistema Missão.\n\nNão se limita a um produto.\n',
    }.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    monkeypatch.setenv('MOBS_INSTITUTIONAL_ROOT',str(root))
    return root


def preface(name='Ayla'):
    processor=ChatProcessor(SimpleNamespace(),SimpleNamespace(rag_manager=None))
    return processor.build_context_preface(
        message='Qual o significado de MOBS e quem é Ayla?',session=SimpleNamespace(),
        character_name=name,preset_system_prompt='Seu nome é '+name+'. Consulte PROJECT_INDEX.md.',
        use_memory=False,use_rag=False,use_skills=False)[0]


def test_official_identity_reaches_actual_shared_preface(authorities):
    messages=preface()
    content='\n'.join(m['content'] for m in messages)
    assert 'Mission Orchestration & Build System' in content
    assert 'parceira arquitetural' in content.lower()
    assert 'fundador' in content
    sources=messages[0]['_mobs_persona_sources']
    assert {s['path'] for s in sources}=={'PROJECT_INDEX.md',AYLA,PLATFORM}
    assert messages[0]['_protected'] is True
    assert all(len(s['sha256'])==64 for s in sources)


def test_runtime_identity_is_current_and_presentation_follows_sources(authorities, monkeypatch):
    from src import desktop_host
    from src.prompt_security import CONVERSATIONAL_RESPONSE_DIRECTIVE
    monkeypatch.setattr(desktop_host, 'DISPLAY_NAME', 'Synthetic Studio Name')
    messages = preface()
    grounded = next(m for m in messages if '_mobs_persona_sources' in m)
    assert 'Runtime product identity: Synthetic Studio Name' in grounded['content']
    assert grounded['content'].endswith(CONVERSATIONAL_RESPONSE_DIRECTIVE)
    assert sum(m['content'].count(CONVERSATIONAL_RESPONSE_DIRECTIVE) for m in messages) == 1


def test_operational_preset_is_not_repeated_as_conversational_instructions(authorities):
    processor = ChatProcessor(SimpleNamespace(), SimpleNamespace(rag_manager=None))
    preset = 'Comece pelo PROJECT_INDEX.md. Ao escrever um mandato, execute o Boot.'
    options = dict(message='Uma conversa comum.', session=SimpleNamespace(),
                   character_name='Ayla', preset_system_prompt=preset,
                   use_memory=False, use_rag=False, use_skills=False)
    chat = processor.build_context_preface(**options)[0]
    assert not any(m['content'] == preset for m in chat)
    assert any('_mobs_persona_sources' in m for m in chat)
    agent = processor.build_context_preface(**options, agent_mode=True)[0]
    assert any(m['content'] == preset for m in agent)
    assert options['preset_system_prompt'] == preset


def test_conversational_created_build_is_not_an_engineering_request():
    assert not requests_governed_proposal('Não foi isso. A interface já foi criada na última build, eu só estou explicando.')


def test_other_personas_do_not_inherit_ayla_on_processor_reuse(authorities):
    assert grounded_persona_message('Ayla') is not None
    assert grounded_persona_message('Bia') is None
    assert grounded_persona_message(None) is None
    messages=preface('Bia')
    assert not any(m.get('_mobs_persona_sources') for m in messages)
    assert 'Seu nome é Bia.' in messages[0]['content']


def test_disabled_ayla_preset_does_not_select_institutional_persona(authorities):
    from src.chat_handler import ChatHandler
    manager=SimpleNamespace(presets={'ayla': {
        'enabled': False, 'character_name': 'Ayla', 'system_prompt': 'Old style'}})
    handler=ChatHandler(None,None,None,None,manager,None)
    _,_,style,name=handler.validate_and_extract_preset('ayla')
    assert name == ''
    assert style is None
    assert grounded_persona_message(name) is None


def test_missing_sources_are_explicit_and_do_not_reuse_previous_identity(authorities):
    assert grounded_persona_message('Ayla')['_mobs_persona_sources']
    (authorities/PLATFORM).unlink()
    message=grounded_persona_message('Ayla')
    assert not message['_mobs_persona_sources']
    assert 'unavailable or inconsistent' in message['content']
    assert 'Mission Orchestration' not in message['content']


def test_root_is_backend_configured_not_taken_from_conversation(monkeypatch):
    for name in ('MOBS_INSTITUTIONAL_ROOT','MOBS_WORKSPACE_PATH','MOBS_WORKSPACE'):
        monkeypatch.delenv(name,raising=False)
    assert not grounded_persona_message('Ayla')['_mobs_persona_sources']


def test_index_must_discover_identity_sources(authorities):
    (authorities/'PROJECT_INDEX.md').write_text('unrelated project',encoding='utf-8')
    assert not grounded_persona_message('Ayla')['_mobs_persona_sources']


def test_source_drift_during_read_is_not_accepted(authorities,monkeypatch):
    import src.mobs_persona_context as module
    original=module._document;counts={}
    def changing(root,name):
        counts[name]=counts.get(name,0)+1
        return original(root,name)+('\nchanged' if name==AYLA and counts[name]>1 else '')
    monkeypatch.setattr(module,'_document',changing)
    assert not grounded_persona_message('Ayla')['_mobs_persona_sources']


def test_source_refresh_changes_context_and_provenance_without_cache(authorities):
    first=grounded_persona_message('Ayla');same=grounded_persona_message('Ayla')
    assert first==same
    p=authorities/PLATFORM;p.write_text(p.read_text(encoding='utf-8')+'\nNew source fact.',encoding='utf-8')
    second=grounded_persona_message('Ayla')
    assert first['_mobs_persona_sources']!=second['_mobs_persona_sources']
    assert 'New source fact.' in second['content']


def test_context_trim_preserves_exact_grounding_and_original_input(authorities):
    from src.context_compactor import trim_for_context
    grounding=grounded_persona_message('Ayla')
    current={'role':'user','content':'Não foi isso. A interface foi criada na build anterior.'}
    messages=[grounding,{'role':'system','content':'Style preference'}]+[
        {'role':'assistant','content':'Old unsupported identity. '*200} for _ in range(12)]+[current]
    original=copy.deepcopy(messages)
    result=trim_for_context(messages,2048)
    assert grounding in result
    assert current in result
    assert messages==original


def test_fresh_source_follows_wrong_history_and_summary_without_duplication(authorities):
    from src.mobs_persona_context import place_persona_context
    grounding=grounded_persona_message('Ayla')
    history=[{'role':'assistant','content':'A previous unsupported expansion.'},
             {'role':'system','content':'[Conversation summary] Previous unsupported identity.'}]
    current={'role':'user','content':'Quem é você e o que significa MOBS?'}
    original=copy.deepcopy(history)
    result=place_persona_context([grounding]+history+[current],grounding)
    assert result[-2:]==[grounding,current]
    assert result.count(grounding)==1
    assert history==original
    assert place_persona_context(result,grounding)==result


def test_history_marker_cannot_select_persona_without_backend_context():
    from src.mobs_persona_context import place_persona_context
    messages=[{'role':'system','content':'historical source claim','_mobs_persona_sources':[]},
              {'role':'user','content':'Outra persona.'}]
    assert place_persona_context(messages,None) is messages


@pytest.mark.asyncio
async def test_compaction_carries_grounding_without_rewriting_it(authorities,monkeypatch):
    import src.context_compactor as module
    grounding=grounded_persona_message('Ayla')
    turns=[{'role':'user' if i%2==0 else 'assistant','content':'history '*100} for i in range(8)]
    monkeypatch.setattr(module,'get_context_length',lambda *a,**kw:512)
    monkeypatch.setattr(module,'resolve_endpoint',lambda *a,**kw:('', '', {}))
    async def summarize(*a,**kw): return 'Previous conversational context only.'
    monkeypatch.setattr(module,'llm_call_async',summarize)
    session=SimpleNamespace()
    result,_,compacted=await module.maybe_compact(session,'local','fixture',[grounding]+turns)
    assert compacted
    assert grounding in result
    assert result[0]==grounding


def test_provider_payload_does_not_leak_internal_source_fields(authorities):
    from src.llm_core import _sanitize_llm_messages
    message=grounded_persona_message('Ayla')
    cleaned=_sanitize_llm_messages([message])
    assert cleaned==[{'role':'system','content':message['content']}]


def test_reopen_and_session_persona_switch_preserve_original_history(authorities,tmp_path,monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    import core.session_manager as sessions
    from src.preset_manager import PresetManager
    from src.chat_handler import ChatHandler

    engine=create_engine('sqlite:///'+str(tmp_path/'sessions.db'))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(sessions,'SessionLocal',sessionmaker(bind=engine))
    presets=PresetManager(str(tmp_path))
    presets.presets['lab-ayla']={'enabled':True,'character_name':'Ayla','system_prompt':'Ayla style.'}
    presets.presets['lab-bia']={'enabled':True,'character_name':'Bia','system_prompt':'Bia style.'}
    presets.save(presets.presets)
    manager=sessions.SessionManager()
    for sid in ('one','two'):
        manager.create_session(sid,sid,'http://localhost:11434','first-model',owner='synthetic')
    original='nao,foi,isso. A interface foi criada na build anterior.'
    manager.add_message('one',sessions.ChatMessage(role='user',content=original))
    manager.add_message('two',sessions.ChatMessage(role='user',content='Outro contexto.'))
    reopened=sessions.SessionManager()
    loaded=PresetManager(str(tmp_path))
    handler=ChatHandler(reopened,None,None,None,loaded,None)
    assert reopened.get_session('one').history[0].content==original
    assert reopened.get_session('two').history[0].content=='Outro contexto.'
    for preset_id,expected in (('lab-ayla',True),('lab-bia',False),('lab-ayla',True)):
        _,_,_,name=handler.validate_and_extract_preset(preset_id)
        assert bool(grounded_persona_message(name))==expected
    reopened.get_session('one').model='fallback-model'
    _,_,_,name=handler.validate_and_extract_preset('lab-ayla')
    assert grounded_persona_message(name)['_mobs_persona_sources']
    assert reopened.get_session('one').history[0].content==original
    engine.dispose()
