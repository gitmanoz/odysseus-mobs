import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_public_desktop_identity_does_not_migrate_installation_identifiers(tmp_path):
    from src import desktop_host
    assert desktop_host.DISPLAY_NAME == 'MOBS Studio'
    assert desktop_host.APP_NAME == 'Odysseus'
    assert desktop_host.POLICY_ID == 'odysseus.desktop.junior'
    assert desktop_host.desktop_paths(local_app_data=str(tmp_path)).root == (tmp_path / 'Odysseus').resolve()
    spec = (ROOT / 'Odysseus.spec').read_text(encoding='utf-8')
    assert 'name="MOBS Studio"' in spec
    assert 'desktop/version-info.txt' in spec


def test_stream_errors_preserve_provider_string_and_object_details():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    function = re.search(r'export (function streamErrorMessage\(payload\) \{.*?\n\})', source, re.S).group(1)
    script = function + "\nconsole.log(JSON.stringify([" + ','.join([
        "streamErrorMessage({status:503,error:'Cannot reach http://127.0.0.1:11434'})",
        "streamErrorMessage({status:400,error:{message:'bad request'}})",
        "streamErrorMessage({status:504,text:'Read timeout'})",
        "streamErrorMessage({status:502})",
        "streamErrorMessage({status:400,detail:'Configured endpoint unavailable'})",
    ]) + "]));"
    result = subprocess.run([node, '-e', script], capture_output=True, text=True, encoding='utf-8', check=True)
    messages = json.loads(result.stdout)
    assert 'Modelo indisponível' in messages[0]
    assert 'Cannot reach http://127.0.0.1:11434' in messages[0]
    assert 'bad request' in messages[1]
    assert 'Read timeout' in messages[2]
    assert 'HTTP 502' in messages[3]
    assert 'Configured endpoint unavailable' in messages[4]


def test_public_assets_exist_and_manifest_uses_current_product():
    manifest = json.loads((ROOT / 'static/manifest.json').read_text(encoding='utf-8'))
    assert manifest['name'] == manifest['short_name'] == 'MOBS Studio'
    from PIL import Image
    for icon in manifest['icons']:
        path = ROOT / 'static' / icon['src']
        with Image.open(path) as image:
            assert f'{image.width}x{image.height}' == icon['sizes']
    for path in ['brand/studio-ms.svg', 'brand/studio-wordmark.svg', 'brand/woven-light.png', 'icon.ico']:
        assert (ROOT / 'static' / path).is_file()


def test_stateful_chat_session_picker_imports_have_one_canonical_identity():
    # A query string is a distinct ES module instance, even for identical code.
    # The entry point and nested dependencies must share these state owners.
    for path in (ROOT / 'static').rglob('*.js'):
        source = path.read_text(encoding='utf-8')
        assert not re.search(r'(?:sessions|chat|modelPicker)\.js\?v=', source), path


def test_studio_login_uses_product_palette_without_random_neon_pattern():
    source = (ROOT / 'static/login.html').read_text(encoding='utf-8')
    assert '<html lang="pt-BR">' in source
    assert '--bg: #101113' in source
    assert '--red: #c8b68a' in source
    assert "name === 'studio' || name === 'graphite' ? 'none'" in source


def test_first_token_timer_shares_controller_scope_and_stops_after_abort():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    outer = source[source.index("    let accumulated = '';"):source.index('    // Reset tracking variables at start')]
    assert 'let abortCtrl = null;' in outer
    assert 'let _isAgent = false;' in outer
    assert 'let streamingTTS = false;' in outer
    assert 'const abortCtrl = new AbortController();' not in source
    assert 'const streamingTTS =' not in source
    timer = outer[outer.index('    let firstTokenWaitTimers = [];'):outer.index('    const clearProcessingProbe')]
    script = """
const assert = require('node:assert/strict');
let abortCtrl=null, accumulated='', callbacks=[], updates=[];
const spinner={element:{},updateMessage:t=>updates.push(t)};
const setTimeout=f=>{callbacks.push(f);return callbacks.length;};
const clearTimeout=()=>{};
""" + timer + """
try { abortCtrl=new AbortController(); } catch (_) {}
scheduleFirstTokenWaitMessages();
callbacks[0](); assert.equal(updates.length,1);
abortCtrl.abort(); callbacks[1](); assert.equal(updates.length,1);
accumulated='token'; callbacks[2](); assert.equal(updates.length,1);
clearFirstTokenWaitTimers();
"""
    subprocess.run([node, '-e', script], capture_output=True, text=True, check=True)


def test_session_loading_guard_survives_out_of_order_navigation_failure():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    sessions = (ROOT / 'static/js/sessions.js').read_text(encoding='utf-8')
    select = sessions[sessions.index('export async function selectSession('):sessions.index('// Pending session —')].replace('export ', '', 1)
    getter = re.search(r'export (function isSessionLoading\(\).*?\})', sessions).group(1)
    chat = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    submit_guard = chat[chat.index('  export async function handleChatSubmit('):chat.index('    // Cancel research clarification timeout')].replace('export ', '', 1) + '\n}'
    script = """
const assert=require('node:assert/strict');
let _sessionNavToken=0,_sessionLoadingToken=null,currentSessionId='start',_pendingChat=null,_sessionListFocused=true;
const sessions=[],errors=[],rejects=[];
const window={innerWidth:1280,presetsModule:{onSessionSwitch(){}}};
const document={dispatchEvent(){},querySelector(){return null},querySelectorAll(){return []},getElementById(){return null}};
const Storage={set(){}};
const uiModule={el(){return null},showError:m=>errors.push(m)};
const chatRenderer={};
const _clearHistoryPager=()=>{},_checkPeekCleanup=()=>{},updateModelPicker=()=>{};
const _historyPageLimit=()=>24,_historyUrl=id=>id;
const fetch=()=>new Promise((resolve,reject)=>rejects.push(reject));
""" + select + getter + submit_guard + """
const sessionModule={isSessionLoading};
(async()=>{
 const a=selectSession('first'); assert.equal(isSessionLoading(),true);
 const b=selectSession('second');
 rejects[0](new Error('first read unavailable')); await a;
 assert.equal(isSessionLoading(),true);
 let prevented=0; await handleChatSubmit({preventDefault(){prevented++}});
 assert.equal(prevented,1); assert.match(errors.at(-1),/seu texto foi preservado/);
 rejects[1](new Error('second read unavailable')); await b;
 assert.equal(isSessionLoading(),false);
})();
"""
    result = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_structured_provider_error_is_terminal_and_does_not_trigger_recovery():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    error_branch = source[source.index('              if (_nextIsError || json.status >= 400) {'):source.index('              if (json.delta || json.type')]
    error_message = re.search(r'export (function streamErrorMessage\(payload\) \{.*?\n\})', source, re.S).group(1)
    script = """
const assert=require('node:assert/strict');
const states=[],messages=[],cleared=[];
let cancelled=0,completed=0,destroyed=0;
const streamSessionId='background-session';
const _backgroundStreams=new Map([[streamSessionId,{status:'running'}]]);
const sessionModule={clearStreaming:id=>cleared.push(id)};
const setProductActivity=s=>states.push(s),typewriterInto=(el,text)=>messages.push(text);
const spinner={element:{},destroy(){destroyed++}};
const roundHolder={querySelector(){return {}}};
const reader={async cancel(){cancelled++}};
""" + error_message + "\nasync function consumeError(_isBg) { let _nextIsError=true; const json={status:503,error:'Cannot reach local provider'};\n" + error_branch + """
completed++;
}
(async()=>{
 await consumeError(false); await consumeError(true);
 assert.equal(cancelled,2);assert.equal(completed,0);assert.equal(destroyed,1);
 assert.deepEqual(states,['failed']);assert.match(messages[0],/Cannot reach local provider/);
 assert.equal(messages.length,1);assert.equal(_backgroundStreams.get(streamSessionId).status,'error');
 assert.deepEqual(cleared,[streamSessionId]);
})();
"""
    result = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

def test_streaming_persona_initial_tracks_real_label_and_clears_for_models():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    function = source[source.index('  function _setRoleModelLabel('):source.index('  function _bestKnownStreamModel(')]
    script = """
const assert=require('node:assert/strict');
const _modelRouteLabel=(requested,actual)=>actual;
const _sameModelName=(a,b)=>a===b;
const _applyModelColor=()=>{};
const role={dataset:{},querySelector(){return null},removeAttribute(){}};
""" + function + """
_setRoleModelLabel(role,'__mobs_auto__','qwen2.5-coder:7b',{characterName:'Ayla'});
assert.equal(role.dataset.personaInitial,'A');
assert.equal(role.textContent,'Ayla ');
_setRoleModelLabel(role,'qwen2.5-coder:7b','qwen2.5-coder:7b',{});
assert.equal(role.dataset.personaInitial,undefined);
assert.equal(role.textContent,'qwen2.5-coder:7b ');
"""
    subprocess.run([node,'-e',script],capture_output=True,text=True,check=True)

def test_mobs_clarification_replaces_only_empty_stream_placeholder():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
    block = source.split("} else if (json.type === 'mobs_clarification_required') {", 1)[1].split("} else if (json.type === 'mobs_authority_reviewed') {", 1)[0]
    script = """
const assert=require('node:assert/strict');
for (const accumulated of ['', 'existing answer']) {
 let removed=0,replies=[];
 const holder={remove(){removed++}};
 const _isBg=false;
 const json={data:{message:'Select the target workspace'}};
 const setProductActivity=()=>{};
 const addMessage=(role,text)=>replies.push(text);
 for (const event of [1]) {
""" + block + """
 }
 assert.equal(removed,accumulated?0:1);
 assert.equal(replies.length,1);
 assert.match(replies[0],/Select the target workspace/);
}
"""
    subprocess.run([node,'-e',script],capture_output=True,text=True,check=True)

def test_studio_idle_composer_keeps_send_icon_instead_of_new_chat():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/app.js').read_text(encoding='utf-8')
    start = source.index('  function _updateSendBtnIcon() {')
    function = source[start:source.index('\n  if (sendBtn) {', start)]
    script = """
const assert=require('node:assert/strict');
const document={body:{classList:{contains:name=>name==='studio-shell'}}};
const sendBtn={dataset:{mode:'newchat'},classList:{add(){},remove(){},contains(){return false}},setAttribute(k,v){this[k]=v}};
const messageInput={value:''},chatModule={hasTextlessMobsAction:()=>false},groupModule={isActive:()=>false};
const _hasAttachments=()=>false,_isSttEnabled=()=>false,_updateStreamingSubmitButton=()=>false;
const _sendIcon='paper-plane',_micIcon='microphone',_newChatIcon='plus';
""" + function + """
_updateSendBtnIcon();
assert.equal(sendBtn.dataset.mode,'idle');assert.equal(sendBtn.innerHTML,'paper-plane');
assert.equal(sendBtn['aria-label'],'Enviar mensagem');
messageInput.value='hello';_updateSendBtnIcon();
assert.equal(sendBtn.dataset.mode,'send');assert.equal(sendBtn.innerHTML,'paper-plane');
messageInput.value='';_updateSendBtnIcon();
assert.equal(sendBtn.dataset.mode,'idle');assert.equal(sendBtn.innerHTML,'paper-plane');
"""
    subprocess.run([node,'-e',script],capture_output=True,text=True,check=True)
