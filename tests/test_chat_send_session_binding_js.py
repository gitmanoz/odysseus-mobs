"""Drive actual model-preparation code across a delayed conversation change."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('switch_session', [False, True])
def test_pending_model_switch_cannot_retarget_the_message(switch_session):
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/chat.js').read_text(encoding='utf-8')
    start = source.index('    const sendSessionId = sessionModule.getCurrentSessionId();')
    end = source.index('    // Acquire Web Lock', start)
    script = r'''
import assert from 'node:assert/strict';
let current='A',resolveSwitch,released=0,_sendInFlight=true,activity=[],touched=[],notices=[],buttons=[];
let _streamSessionId=null;
let _pendingApprovedPlan={session:'A',plan:'explicit plan'};
const msg='message for A',input={value:'message for A',disabled:true},submitBtn={innerHTML:'Send',classList:{remove(){}}};
const el=()=>input,sessionModule={getCurrentSessionId:()=>current};
const window={__odysseusModelSwitchPromise:new Promise(resolve=>resolveSwitch=resolve)};
const _releaseSendFlag=()=>{_sendInFlight=false;released++;input.disabled=false};
const uiModule={showToast:message=>notices.push(message)};
const updateSubmitButton=state=>buttons.push(state),setProductActivity=state=>activity.push(state),_touchStreamActivity=sid=>touched.push(sid);
async function prepare(){ SOURCE return streamSessionId; }
const pending=prepare();assert.equal(_sendInFlight,true,'the re-click latch must remain held during model preparation');
if(SWITCH){current='B';input.value='new conversation draft';}
resolveSwitch();const result=await pending;
if(SWITCH){assert.equal(result,undefined);assert.equal(released,1);assert.equal(buttons.length,0);assert.equal(touched.length,0);assert.equal(input.value,'new conversation draft');assert.match(notices[0],/Nenhuma solicitação/);assert.equal(_pendingApprovedPlan,null);}
else {assert.equal(result,'A');assert.deepEqual(touched,['A']);assert.deepEqual(buttons,['streaming']);assert.equal(_sendInFlight,false);}
'''.replace('SOURCE', source[start:end]).replace('SWITCH', str(switch_session).lower())
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'uploadPending({ sessionId: streamSessionId })' in source


def test_prepared_authority_is_compared_to_request_session_not_current_view():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/chat.js').read_text(encoding='utf-8')
    start = source.index('        if (_mobsAction.session && _mobsAction.session !== streamSessionId)')
    end = source.index("        fd.append('mobs_action'", start)
    script = r'''
import assert from 'node:assert/strict';
let _mobsAction={session:'B',action:'approve'};const streamSessionId='A';
const sessionModule={getCurrentSessionId:()=> 'B'};
function guard(){ SOURCE }
assert.throws(guard,/another session/);assert.equal(_mobsAction,null);
_mobsAction={session:'A',action:'review'};assert.doesNotThrow(guard);
'''.replace('SOURCE', source[start:end])
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('current,draft,expected', [('A', '', 'original request'), ('A', 'newer draft', 'newer draft'), ('B', 'other conversation', 'other conversation')])
def test_failed_upload_restores_only_its_empty_composer(current, draft, expected):
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/chat.js').read_text(encoding='utf-8')
    begin = source.index('      if (_pendingAttachInfo && !ids.length')
    end = source.index('      if (sessionModule.getCurrentSessionId() !== streamSessionId) throw', begin)
    import json
    script = r'''
import assert from 'node:assert/strict';
const _pendingAttachInfo=[{}],ids=[],_pendingRegenAttachments=null,streamSessionId='A',msg='original request';
let removed=0,released=0,states=[];
let _pendingApprovedPlan={session:'A',plan:'explicit plan'};
const _userMsgEl={parentNode:{},remove(){removed++}},messageInput={value:DRAFT,dispatchEvent(){}};
const sessionModule={getCurrentSessionId:()=>CURRENT},fileHandlerModule={wasLastUploadCancelled:()=>false};
const uiModule={showError(){},autoResize(){}};
const setProductActivity=state=>states.push(state),updateSubmitButton=()=>{},_releaseSendFlag=()=>released++,submitBtn={};
function fail(){ SOURCE }
fail();assert.equal(messageInput.value,EXPECTED);assert.equal(removed,1);assert.equal(released,1);assert.equal(_pendingApprovedPlan,null);
assert.equal(states.length,CURRENT==='A'?1:0);
'''.replace('SOURCE', source[begin:end]).replace('DRAFT', json.dumps(draft)).replace('CURRENT', json.dumps(current)).replace('EXPECTED', json.dumps(expected))
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
