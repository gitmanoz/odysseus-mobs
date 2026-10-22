"""Context telemetry is observational, content-free and additive."""
from copy import deepcopy
import json

from src.context_diagnostics import context_profile
from src.model_context import estimate_tokens


def test_classification_keeps_protected_authority_and_never_returns_source_text():
    messages = [
        {"role": "system", "content": "SECRET_AUTHORITY", "_protected": True},
        {"role": "system", "content": "SECRET_PERSONA", "_protected": True, "_mobs_persona_sources": ["private/path"]},
        {"role": "system", "content": "PROTOCOL", "_protected": True, "_governed_tool_protocol": True},
        {"role": "system", "content": "ACTION", "_protected": True, "_governed_action_instruction": True},
        {"role": "user", "content": "PRIVATE_USER_REQUEST"},
        {"role": "tool", "content": "PRIVATE_TOOL_OUTPUT"},
    ]
    original = deepcopy(messages)
    profile = context_profile(messages)
    assert messages == original
    assert profile["message_tokens_estimated"] == estimate_tokens(messages)
    assert sum(bucket["estimated_tokens"] for bucket in profile["categories"].values()) == estimate_tokens(messages)
    assert set(profile["categories"]) == {"protected_context", "persona", "tool_protocol", "action_instruction", "user", "tool"}
    text = json.dumps(profile)
    for secret in ["SECRET_AUTHORITY", "SECRET_PERSONA", "private/path", "PRIVATE_USER_REQUEST", "PRIVATE_TOOL_OUTPUT"]:
        assert secret not in text


def test_schema_cost_and_literal_duplicates_are_observed_without_deduplication():
    messages = [{"role": "system", "content": "same"}, {"role": "system", "content": "same"}]
    schemas = [{"function": {"name": "read_file", "parameters": {"type": "object"}}}]
    profile = context_profile(messages, schemas)
    assert profile["duplicate_system_messages"] == 1
    assert profile["messages"] == 2
    assert profile["tool_schema_count"] == 1
    assert profile["tool_schema_tokens_estimated"] > 0
    assert "read_file" not in json.dumps(profile)
    assert profile["image_tokens_included"] is False


def test_duplicate_cost_is_observational_and_protected_copies_remain():
    messages = [{'role': 'system', 'content': 'protected', '_protected': True}] * 3
    before = deepcopy(messages)
    profile = context_profile(messages)
    assert messages == before
    assert profile['duplicate_system_messages'] == 2
    assert profile['duplicate_protected_messages'] == 2
    assert profile['duplicate_system_tokens_estimated'] == 2 * estimate_tokens([messages[0]])
    assert 'protected' not in json.dumps(profile['categories'].get('system', {}))


def test_multimodal_and_native_tool_call_shapes_use_existing_estimator():
    messages = [{"role": "user", "content": [{"type": "text", "text": "request"}, {"type": "image_url", "image_url": {"url": "private"}}]},
                {"role": "assistant", "content": None, "tool_calls": [{"function": {"name": "read_file", "arguments": '{"path":"private"}'}}]}]
    assert context_profile(messages)["message_tokens_estimated"] == estimate_tokens(messages)
    assert "private" not in json.dumps(context_profile(messages))


def test_reproducible_history_comparison_keeps_protected_cost_and_sources():
    protected = {'role':'system','content':'PRIVATE_AUTHORITY '*20,'_protected':True}
    schema = {'function':{'name':'read_file','parameters':{'type':'object'}}}
    observations = []
    for turns in (1, 5, 20):
        messages = [deepcopy(protected)] + [{'role':'user' if i%2==0 else 'assistant','content':'PRIVATE_HISTORY '*10} for i in range(turns)]
        before = deepcopy(messages)
        profile = context_profile(messages, [schema])
        observations.append(profile)
        assert messages == before
        assert profile['categories']['protected_context'] == observations[0]['categories']['protected_context']
        assert profile['tool_schema_tokens_estimated'] == observations[0]['tool_schema_tokens_estimated']
        assert 'PRIVATE_' not in json.dumps(profile)
    assert observations[0]['message_tokens_estimated'] < observations[1]['message_tokens_estimated'] < observations[2]['message_tokens_estimated']


def test_actual_agent_loop_emits_and_persists_profiles_with_fake_transport(monkeypatch):
    from tests.test_fenced_example_not_executed_for_native_models import _patch_common, _run_loop
    calls = []
    _patch_common(monkeypatch, calls)
    events = _run_loop(monkeypatch, 'gpt-4o', ['Here is an explanation only.'])
    preparation = next(event for event in events if event.get('type') == 'agent_prep')
    metrics = next(event['data'] for event in events if event.get('type') == 'metrics')
    assert preparation['context_profile']['estimate_only'] is True
    assert metrics['initial_context_profile'] == preparation['context_profile']
    assert metrics['last_round_context_profile']['tool_schema_count'] > 0
    assert calls == []


def test_schema_family_audit_preserves_input_and_keeps_unknown_names_private():
    schemas=[{'function':{'name':name,'parameters':{'type':'object'}}} for name in ['read_file','write_file','bash','update_plan','PRIVATE_PLUGIN']]
    before=deepcopy(schemas)
    profile=context_profile([],schemas)
    assert sum(g['count'] for g in profile['tool_schema_groups'].values())==5
    assert set(profile['tool_schema_groups'])=={'navigation','editing','execution','coordination','other'}
    assert schemas==before
    assert 'PRIVATE_PLUGIN' not in json.dumps(profile)


def test_unknown_schema_shapes_do_not_break_observation():
    profile=context_profile([],[None,{'function':None},{'function':{'name':[]}}])
    assert profile['tool_schema_groups']['other']['count']==3
