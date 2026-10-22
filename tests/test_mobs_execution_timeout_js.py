"""An approval from chat must allow the existing finite agent first-token wait."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def test_governed_execution_uses_agent_timeout_after_preparation_is_cleared():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = Path('static/js/chat.js').read_text(encoding='utf-8')
    helper = re.search(r'export function chatResponseTimeoutMs\([^)]*\) \{.*?\n  \}', source, re.S).group()
    constants = '\n'.join(re.findall(r'const (?:RESEARCH_TIMEOUT_MS|DEFAULT_TIMEOUT_MS) = \d+;', source))
    decision = "const timeoutMs = chatResponseTimeoutMs(el('research-toggle').checked, _isAgent, fd.get('mobs_action'));"
    assert source.index('clearPreparedMobsAction();', source.index("fd.append('mobs_action'")) < source.index(decision)
    script = constants + '\n' + helper.replace('export ', '') + '''
const assert = require('node:assert/strict');
assert.equal(chatResponseTimeoutMs(false, false, 'approve'), 360000);
assert.equal(chatResponseTimeoutMs(false, false, 'validate_promotion'), 360000);
for (const action of [null, '', 'propose', 'review', 'cancel', 'promote']) {
  assert.equal(chatResponseTimeoutMs(false, false, action), 120000);
}
assert.equal(chatResponseTimeoutMs(false, true, null), 360000);
assert.equal(chatResponseTimeoutMs(true, false, null), 360000);
'''
    # Exercise the actual timer selection using the already serialized action.
    script += '\nconst fd = new Map([["mobs_action", "approve"]]);\n'
    script += 'const _isAgent = false; const el = () => ({checked:false});\n'
    script += decision + '\nassert.equal(timeoutMs, 360000);\n'
    result = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
