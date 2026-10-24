"""No inference: reserve a follow-up without dropping approved sources or results."""
from copy import deepcopy
import hashlib
import json

import pytest

from src.agent_loop import _governed_result_feedback, _GOVERNED_FEEDBACK_RESERVE
from src.context_compactor import trim_for_context
from src.model_context import estimate_tokens
from src.prompt_security import untrusted_context_message


@pytest.mark.parametrize('exit_code,output', [(0, '1 passed'), (1, 'FAILED test_probe'), (2, 'ERROR collecting')])
def test_model_feedback_references_complete_ledger_without_mutating_evidence(exit_code, output):
    receipt = {'command': 'python -m pytest -q tests/test_probe.py', 'exit_code': exit_code,
               'boundary': {'adapter': 'windows_appcontainer_job_v1', 'effects': [],
                            'acl_rules': [{'path': f'tests/{i}.py', 'permission': 'RX'} for i in range(100)]}}
    result = {'output': output, 'exit_code': exit_code, 'trusted_execution': receipt['boundary'],
              'command_capability': {'recipe': 'pytest', 'permitted': True}}
    before = deepcopy((receipt, result))
    feedback = _governed_result_feedback('bash: pytest', result, receipt)
    assert output in feedback
    assert f'"exit_code": {exit_code}' in feedback
    expected = hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',', ':'),ensure_ascii=False).encode()).hexdigest()
    assert expected in feedback
    assert 'acl_rules' not in feedback
    assert estimate_tokens([untrusted_context_message('tool execution results', feedback)]) < _GOVERNED_FEEDBACK_RESERVE - 32
    assert (receipt, result) == before


def test_optional_preset_yields_to_exact_approved_request_and_followup_reserve():
    sources = {'role': 'system', 'content': 'authority ' * 9400, '_protected': True}
    current = {'role': 'user', 'content': 'Execute python -m pytest -q tests/test_probe.py.'}
    preset = {'role': 'system', 'content': 'Optional response style. ' * 700}
    messages = [preset, sources, {'role':'user','content':'old history '*500}, current]
    before = deepcopy(messages)
    reserve = 2048 + _GOVERNED_FEEDBACK_RESERVE
    capacity = estimate_tokens([sources, current]) + reserve + 256
    reduced = trim_for_context(messages, capacity, reserve_tokens=reserve, preserve_current=True)
    assert sources in reduced and current == reduced[-1]
    assert estimate_tokens(reduced) + reserve <= capacity
    assert 'Odysseus kept the beginning and end.' in reduced[0]['content']
    feedback = _governed_result_feedback('bash: pytest', {'output':'1 passed','exit_code':0},
                                         {'exit_code':0,'boundary':{'adapter':'windows_appcontainer_job_v1'}})
    second = reduced + [{'role':'assistant','content':'```bash\npython -m pytest -q tests/test_probe.py\n```'},
                         untrusted_context_message('tool execution results', feedback)]
    assert estimate_tokens(second) + 2048 <= capacity
    assert messages == before


def test_impossible_governed_sources_remain_intact_for_fail_closed_guard():
    source = {'role':'system','content':'A'*5000,'_protected':True}
    current = {'role':'user','content':'required request '*400}
    result = trim_for_context([source,current], 1600, reserve_tokens=1024, preserve_current=True)
    assert source in result
    assert result[-1]['content'] != current['content'] or estimate_tokens(result) > 576
