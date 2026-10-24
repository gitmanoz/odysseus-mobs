"""Exercise the real prepared-action submission without inference or a browser."""
import shutil
import subprocess
from pathlib import Path

def test_textless_approval_defers_shell_admission_without_overriding_other_turns():
    node = shutil.which('node')
    assert node, 'Node is required for the frontend transport regression'
    source = (Path(__file__).resolve().parents[1] / 'static/js/chat.js').read_text(encoding='utf-8')
    start = source.index('      if (_mobsAction) {', source.index("fd.append('allow_bash'"))
    end = source.index('      if (presetsModule.getSelectedPreset())', start)
    block = source[start:end]
    script = r'''
import assert from 'node:assert/strict';
let _mobsAction, streamSessionId='A', cleared=0;
function clearPreparedMobsAction(){cleared++;_mobsAction=null}
function submit(action,session='A'){
  const fd=new FormData();fd.append('allow_bash','false');
  _mobsAction=action ? {action,session,proposalId:'p',proposalDigest:'d',authoritySnapshot:'s'} : null;
  BLOCK
  return fd;
}
const approved=submit('approve');
assert.equal(approved.has('allow_bash'),false);
assert.equal(approved.get('mobs_action'),'approve');
assert.equal(approved.get('mobs_proposal_id'),'p');
assert.equal(approved.get('mobs_proposal_digest'),'d');
assert.equal(approved.get('mobs_authority_snapshot'),'s');
assert.equal(_mobsAction,null);
for(const action of [null,'propose','review','cancel','promote','validate_promotion']){
  assert.equal(submit(action).get('allow_bash'),'false',String(action));
}
assert.throws(()=>submit('approve','B'),/another session/);
assert.equal(_mobsAction,null);
console.log('Textless approval admission and all non-approval denies preserved');
'''.replace('BLOCK', block)
    result = subprocess.run([node, '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
