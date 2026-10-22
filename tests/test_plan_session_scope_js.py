"""Run the actual plan helpers/submit guard without browser or model inference."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_plan_buttons_and_pending_send_are_bound_to_the_displayed_session():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/chat.js').read_text(encoding='utf-8')
    helpers = source[source.index('  const PLAN_STORAGE_KEY'):source.index('  function _escapeQueueText')]
    guard = source[source.index('if (_pendingApprovedPlan?.session !== streamSessionId)'):source.index('if (el(\'web-toggle\').checked)', source.index('if (_pendingApprovedPlan?.session !== streamSessionId)'))]
    script = r'''
import assert from 'node:assert/strict';
let current='A', sent=[];
const sessionModule={getCurrentSessionId:()=>current};
const values=new Map([['odysseus-active-plan','- [ ] legacy wrong plan']]);
const localStorage={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
const window={};
const document={createElement:()=>({buttons:new Map(),querySelector(s){if(!this.buttons.has(s))this.buttons.set(s,{addEventListener:(_,fn)=>this.buttons.get(s).click=fn});return this.buttons.get(s)},remove(){this.removed=true}})};
function _setComposerAndSend(text){sent.push(text)}
function target(){return {isConnected:true,actions:null,querySelector(){return null},appendChild(e){this.actions=e}}}
HELPERS
assert.equal(_getStoredPlan('A'),'');
_setStoredPlan('- [ ] A plan','A');_setStoredPlan('- [ ] B plan','B');
assert.equal(_getStoredPlan('A'),'- [ ] A plan');assert.equal(_getStoredPlan('B'),'- [ ] B plan');
const a=target();_attachPlanActions(a,'- [ ] visible A','A');
current='B';a.actions.querySelector('.plan-inline-execute').click();assert.equal(sent.length,0);
current='A';a.actions.querySelector('.plan-inline-execute').click();
assert.deepEqual(_pendingApprovedPlan,{session:'A',plan:'- [ ] visible A'});
assert.equal(sent.length,1);
// The real submit guard drops preparation from another conversation.
let streamSessionId='B',isPlanMode=false,isAgentMode=false,isIncognito=false,workspaceAgentIntent=false;
const documentModule=null,activeDocIdForSend=null,fields=new Map(),fd={append:(k,v)=>fields.set(k,v)};
GUARD
assert.equal(_pendingApprovedPlan,null);assert.equal(fields.has('approved_plan'),false);
a.isConnected=false;a.actions.querySelector('.plan-inline-execute').click();assert.equal(sent.length,1);
a.isConnected=true;a.actions.querySelector('.plan-inline-execute').click();
streamSessionId='A';fields.clear();
GUARD
assert.equal(fields.get('approved_plan'),'- [ ] visible A');assert.equal(_pendingApprovedPlan,null);
// Clearing an old proposal cannot clear a newer plan or another session.
a.actions.querySelector('.plan-inline-clear').click();assert.equal(_getStoredPlan('A'),'- [ ] A plan');
_setStoredPlan('- [ ] visible A','A');a.actions.querySelector('.plan-inline-clear').click();
assert.equal(_getStoredPlan('A'),'');assert.equal(_getStoredPlan('B'),'- [ ] B plan');
localStorage.setItem=()=>{throw new Error('disabled')};assert.doesNotThrow(()=>_setStoredPlan('plan','A'));
console.log('Session-bound storage, displayed-plan selection, stale buttons and submit guard verified');
'''.replace('HELPERS', helpers).replace('GUARD', guard)
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_plan_send_timer_does_not_submit_after_switching_conversations():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/chat.js').read_text(encoding='utf-8')
    helper = source[source.index('  function _setComposerAndSend('):source.index('  function _sendQueuedWhenIdle(')]
    script = r'''
import assert from 'node:assert/strict';
let current='A', callback, submits=0, _pendingApprovedPlan={session:'A',plan:'plan'};
const sessionModule={getCurrentSessionId:()=>current};
const input={value:'',dispatchEvent(){}};
const uiModule={el:()=>input};
const setTimeout=fn=>callback=fn;
const handleChatSubmit=()=>{submits++;return Promise.resolve()};
HELPER
assert.equal(_setComposerAndSend('execute','A'),true);
current='B';input.value='new draft';callback();
assert.equal(submits,0);assert.equal(_pendingApprovedPlan,null);assert.equal(input.value,'new draft');
assert.equal(_setComposerAndSend('wrong','A'),false);assert.equal(input.value,'new draft');
current='A';_setComposerAndSend('execute','A');callback();assert.equal(submits,1);
'''.replace('HELPER', helper)
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
