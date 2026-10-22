"""Exercise actual navigation code, persistence failures and session boundaries."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_js(source):
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    result = subprocess.run(['node', '--input-type=module', '-e', source], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_groups_are_disjoint_recent_and_preserve_pinned_project_membership():
    source = (ROOT / 'static/js/sessions.js').read_text(encoding='utf-8')
    group = source[source.index('function studioSessionGroups('):source.index('function enableStudioRowDrag(')]
    run_js("import assert from 'node:assert/strict';\n" + group + r'''
const input=[{id:'a',is_important:true,folder:'MOBS',last_message_at:'2026-10-14'},
 {id:'b',folder:'MOBS',last_message_at:'2026-10-15'},
 {id:'c',last_message_at:'2026-10-12'}, {id:'d',last_message_at:'2026-10-15'}];
const snapshot=JSON.stringify(input), groups=studioSessionGroups(input,['Empty','__proto__']);
assert.equal(JSON.stringify(input),snapshot);
assert.deepEqual(groups.pinned.map(s=>s.id),['a']);
assert.deepEqual(groups.recent.map(s=>s.id),['d','c']);
assert.deepEqual(groups.projects.find(p=>p.name==='MOBS').sessions.map(s=>s.id),['b']);
assert.equal(groups.projects.find(p=>p.name==='Empty').sessions.length,0);
assert.equal(input[0].folder,'MOBS');
const ids=[...groups.pinned,...groups.recent,...groups.projects.flatMap(p=>p.sessions)].map(s=>s.id);
assert.equal(new Set(ids).size,input.length);
''')


def test_metadata_mutations_require_server_success_and_do_not_change_workspace():
    source = (ROOT / 'static/js/sessions.js').read_text(encoding='utf-8')
    functions = source[source.index('async function moveToFolder('):source.index('async function loadStudioNavigation(')]
    run_js(r'''
import assert from 'node:assert/strict';
let ok=false, renders=0, errors=[],requests=[];
const _studioMovingSessions=new Set();
const sessions=[{id:'a',name:'First message',folder:'MOBS',is_important:false,workspace:'C:/approved-target'}];
const API_BASE='http://localhost';
const uiModule={showError:e=>errors.push(e),showToast(){}};
const renderSessionList=()=>renders++;
const fetch=async(url,options)=>{requests.push({url,options});return {ok}};
''' + functions + r'''
const session=sessions[0];
assert.equal(await moveToFolder('a','New project'),false);
assert.equal(await renameSession(session,'Renamed'),false);
assert.equal(await setSessionPinned(session,true),false);
assert.equal(session.folder,'MOBS');assert.equal(session.name,'First message');
assert.equal(session.is_important,false);assert.equal(renders,0);assert.equal(errors.length,3);
ok=true;
assert.equal(await moveToFolder('a','New project'),true);
assert.equal(await renameSession(session,'Renamed'),true);
assert.equal(await setSessionPinned(session,true),true);
assert.equal(session.folder,'New project');assert.equal(session.name,'Renamed');
assert.equal(session.is_important,true);assert.equal(session.workspace,'C:/approved-target');
assert.deepEqual(requests.slice(-3).map(r=>[...r.options.body.keys()]),[['folder'],['name'],['important']]);
''')


def test_drag_requires_owned_row_destination_and_release_and_preserves_touch_scroll():
    source = (ROOT / 'static/js/sessions.js').read_text(encoding='utf-8')
    function = source[source.index('function enableStudioRowDrag('):source.index('function renderStudioSessionGroups(')]
    run_js(r'''
import assert from 'node:assert/strict';
let _studioDraggingSession=null, moves=[];
const sessions=[{id:'own'}], handlers={},docHandlers={};
const classes={add(){},remove(){}};
const destination={classList:classes,dataset:{folderName:'MOBS'}};
const row={addEventListener:(name,fn)=>handlers[name]=fn,classList:classes};
globalThis.document={body:{classList:classes},elementFromPoint:()=>({closest:()=>destination}),
 addEventListener:(k,f)=>docHandlers[k]=f,removeEventListener:k=>delete docHandlers[k]};
const moveToFolder=async(...args)=>moves.push(args);
''' + function + r'''
enableStudioRowDrag(row,'own');
const start={button:0,pointerType:'mouse',pointerId:1,clientX:10,clientY:10,target:{closest:()=>null}};
handlers.pointerdown({...start,pointerType:'touch'});assert.equal(docHandlers.pointermove,undefined);
handlers.pointerdown(start);await docHandlers.pointerup({pointerId:1,type:'pointerup'});assert.equal(moves.length,0);
handlers.pointerdown(start);docHandlers.pointermove({pointerId:1,clientX:90,clientY:90,preventDefault(){}});
await docHandlers.pointercancel({pointerId:1,type:'pointercancel'});assert.equal(moves.length,0);
handlers.pointerdown(start);docHandlers.pointermove({pointerId:1,clientX:90,clientY:90,preventDefault(){}});
await docHandlers.pointerup({pointerId:1,type:'pointerup'});assert.deepEqual(moves,[['own','MOBS']]);
assert.equal(_studioDraggingSession,null);assert.equal(docHandlers.pointermove,undefined);
sessions.length=0;
handlers.pointerdown(start);docHandlers.pointermove({pointerId:1,clientX:90,clientY:90,preventDefault(){}});
await docHandlers.pointerup({pointerId:1,type:'pointerup'});assert.equal(moves.length,1);
''')


def test_project_preferences_persist_per_user_without_institutional_state(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes import prefs_routes
    monkeypatch.setattr(prefs_routes, 'PREFS_FILE', str(tmp_path / 'prefs.json'))
    monkeypatch.setattr(prefs_routes, 'get_current_user', lambda request: request.headers['x-test-user'])
    app = FastAPI()
    app.include_router(prefs_routes.setup_prefs_routes())
    value = {'names': ['MOBS', 'Last Sentinel'], 'collapsed': {'MOBS': True}}
    with TestClient(app) as client:
        assert client.put('/api/prefs/studio-project-navigation', headers={'x-test-user': 'alice'}, json={'value': value}).status_code == 200
    with TestClient(app) as reopened:
        assert reopened.get('/api/prefs/studio-project-navigation', headers={'x-test-user': 'alice'}).json()['value'] == value
        assert reopened.get('/api/prefs/studio-project-navigation', headers={'x-test-user': 'bob'}).json()['value'] is None
    assert list(json.loads((tmp_path / 'prefs.json').read_text())['_users']['alice']) == ['studio-project-navigation']


def test_embedded_actions_and_title_editors_do_not_trigger_session_navigation():
    source = (ROOT / 'static/js/sessions.js').read_text(encoding='utf-8')
    function = source[source.index('async function _onSessionListKeydown('):source.index('export function initDragSort(')]
    run_js("import assert from 'node:assert/strict'; let selected=[]; const selectSession=id=>selected.push(id);\n" + function + r'''
for(const key of ['Enter','Delete','Backspace','ArrowDown']) {
 await _onSessionListKeydown({key,target:{closest:()=>({})},preventDefault(){throw new Error('Embedded control intercepted');}});
}
assert.equal(selected.length,0);
await _onSessionListKeydown({key:'Enter',target:{closest:selector=>selector.startsWith('button')?null:{dataset:{sessionId:'chosen'}}},preventDefault(){}});
assert.deepEqual(selected,['chosen']);
''')


def test_message_navigation_rebuilds_and_rejects_stale_session_actions():
    module = (ROOT / 'static/js/studioMessageNavigation.js').as_uri()
    run_js(r'''
import assert from 'node:assert/strict';
let frames=[],listeners={},session='a',loading=false,scrolls=0,focused=0;
class Element {
 constructor(){this.children=[];this.attrs={};this.handlers={};this.style={};this.hidden=false;this.isConnected=true;this.textContent='';this.classList={add(){},remove(){}};}
 appendChild(e){this.children.push(e);e.parentNode=this;return e;}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attrs[k]=v;}removeAttribute(k){delete this.attrs[k];}
 addEventListener(k,v){this.handlers[k]=v;}
 getBoundingClientRect(){return {top:100,right:300};}
 focus(){focused++;}scrollIntoView(){scrolls++;}
}
const history=new Element(),container=new Element();
const makeMessage=text=>{const m=new Element(); const body={cloneNode:()=>({textContent:text,querySelectorAll:()=>[]})};m.querySelector=()=>body; m.closest=()=>null;return m;};
let messages=[makeMessage('First prompt <literal>'),makeMessage('Second prompt')];
history.querySelectorAll=()=>messages;history.contains=n=>messages.includes(n);
globalThis.document={createElement:()=>new Element(),addEventListener:(k,f)=>listeners[k]=f};
globalThis.window={innerWidth:1200,innerHeight:800,requestAnimationFrame:f=>{frames.push(f);return frames.length},addEventListener(){},matchMedia:()=>({matches:true})};
const flush=()=>{const batch=frames;frames=[];batch.forEach(f=>f());};
globalThis.MutationObserver=class {constructor(f){this.fn=f;}observe(){}};
''' + 'const {initMessageNavigation}=await import(' + repr(module) + ');\n' + r'''
const nav=initMessageNavigation({history,container,getSession:()=>session,isLoading:()=>loading,jumpToMessage:()=>{scrolls++;return true;}});flush();
const rail=container.children[0],tooltip=container.children[1];
assert.equal(rail.children.length,2);
const stale=rail.children[0];stale.handlers.focus();assert.equal(tooltip.hidden,false);
assert.equal(tooltip.children[1].textContent,'First prompt <literal>');
loading=true;stale.handlers.click();assert.equal(scrolls,0);loading=false;
stale.handlers.click();assert.equal(scrolls,1);
session='b';loading=true;listeners['studio-session-selected']({detail:{session:'b'}});
stale.handlers.click();assert.equal(scrolls,1);assert.equal(rail.hidden,true);
messages=[makeMessage('New session')];loading=false;
listeners['studio-history-ready']({detail:{session:'a',loaded:true}});flush();assert.equal(rail.hidden,true);
listeners['studio-history-ready']({detail:{session:'b',loaded:true}});flush();assert.equal(rail.children.length,1);
stale.handlers.click();assert.equal(scrolls,1);
rail.children[0].handlers.click();assert.equal(scrolls,2);
messages=[];nav.refresh();flush();assert.equal(rail.hidden,true);
''')
