"""Exercise the actual presentation controller with an isolated DOM test double."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_context_lifecycle_staging_and_out_of_order_responses():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    module = (Path(__file__).resolve().parents[1] / 'static/js/studioShell.js').as_uri()
    script = r'''
import assert from 'node:assert/strict';
const nodes = new Map(), listeners = new Map();
class Element {
  constructor(tag='div') { this.tagName=tag; this.children=[]; this.style={}; this.dataset={}; this.hidden=false; this.attrs={}; this.textContent=''; this.value=''; this.isConnected=true; this.handlers={}; this.classList={add(){},remove(){},toggle(){}}; }
  set innerHTML(text) { for(const match of text.matchAll(/<([a-z]+)[^>]*id="([^"]+)"[^>]*>/g)) { const e=new Element(match[1]); e.id=match[2]; nodes.set(e.id,e); e.parentNode=this; } }
  setAttribute(k,v){this.attrs[k]=v;}
  removeAttribute(k){delete this.attrs[k];}
  replaceChildren(...es){this.children=es;}
  appendChild(e){this.children.push(e);e.parentNode=this;if(e.id)nodes.set(e.id,e);}
  insertBefore(e){this.appendChild(e);}
  after(e){this.parentNode.appendChild(e);}
  addEventListener(type,fn){this.handlers[type]=fn;}
  async click(){await (this.onclick||this.handlers.click)?.({target:this});}
  focus(){document.activeElement=this;}
  scrollIntoView(){}
  contains(node){while(node){if(node===this)return true;node=node.parentNode;}return false;}
  querySelectorAll(){return [];}
  querySelector(){return null;}
}
const body=new Element();
globalThis.document={body,activeElement:null,createElement:t=>new Element(t),getElementById:id=>nodes.get(id),querySelector:s=>nodes.get(s==='.sidebar-header'?'test-sidebar-header':s==='.sidebar-inner'?'test-sidebar-inner':''),querySelectorAll:()=>[],
 addEventListener:(t,f)=>{if(!listeners.has(t))listeners.set(t,[]);listeners.get(t).push(f)},
 dispatchEvent:e=>{for(const f of listeners.get(e.type)||[])f(e)}};
globalThis.window={innerWidth:1280,confirm:()=>true,addEventListener(){}};
globalThis.MutationObserver=class{observe(){}};
for(const id of ['chat-container','chat-history','message','product-workspace-btn','product-agent-activity','product-agent-activity-label','studio-home','studio-projects','studio-capabilities','studio-help','product-advanced-btn','overflow-preset-btn','studio-conversations','hamburger-btn','icon-rail','user-bar-avatar','user-bar-profile','test-sidebar-header','test-sidebar-inner']) {const e=new Element();e.id=id;e.parentNode=body;nodes.set(id,e);}
nodes.get('product-agent-activity').dataset.state='ready';
let profileClicks=0, navigationClicks=0;
nodes.get('user-bar-profile').onclick=()=>profileClicks++;
nodes.get('hamburger-btn').onclick=()=>navigationClicks++;
let sid='a', staged=null, next, conversationName='qwen2.5-coder:7b 01:51:49';
const fixture=(id,digest='one')=>({session_id:id,validity:'valid',active:false,continuity:'recorded',proposal:{proposal_id:'p',proposal_digest:digest,authority_snapshot:'snap',status:'pending'},reviewed:false,actions:['review','cancel'],promotions:[]});
next=fixture('a');
globalThis.fetch=async url=>({ok:true,json:async()=>url.includes('/api/prefs/')?{value:true}:next});
const chat={clearPreparedMobsAction(){staged=null;document.dispatchEvent(new CustomEvent('studio-action-prepared',{detail:null}))},
 stageMobsAction(a){staged={...a,session:sid};document.dispatchEvent(new CustomEvent('studio-action-prepared',{detail:staged}));return true},
 hasTextlessMobsAction(){return !!staged&&['review','approve','cancel','promote'].includes(staged.action)}};
const {initStudioShell}=await import(MODULE);
const shell=initStudioShell({chat,sessions:{getCurrentSessionId:()=>sid,getSessions:()=>[{id:sid,name:conversationName,model:'qwen2.5-coder:7b'},{id:'background'}]},workspace:{getWorkspace:()=>'/same',openWorkspaceBrowser(){}},storage:{}});
assert.equal(nodes.get('studio-title').textContent,'Nova conversa');
conversationName='Minha conversa';
document.dispatchEvent(new CustomEvent('studio-session-metadata-changed'));
assert.equal(nodes.get('studio-title').textContent,'Minha conversa');
assert.equal(nodes.get('product-agent-activity').parentNode,nodes.get('studio-header-actions'));
assert.match(nodes.get('product-agent-activity').attrs['aria-label'],/autoriza/);
await nodes.get('product-agent-activity').click();
assert.equal(nodes.get('studio-view-options').open,true);
assert.equal(staged,null);
assert.equal(nodes.get('test-sidebar-header').children[0].textContent,'Conversas');
assert.equal(nodes.get('user-bar-avatar').parentNode,nodes.get('studio-profile'));
assert.equal(nodes.get('studio-capabilities').parentNode.className,'studio-navigation-menu');
assert.equal(nodes.get('product-advanced-btn').parentNode.className,'studio-navigation-menu');
await nodes.get('studio-profile').click();assert.equal(profileClicks,1);
await nodes.get('studio-list-collapse').click();assert.equal(navigationClicks,1);
await shell.refresh(true);
await nodes.get('studio-refresh').click();
assert.equal(staged,null,'refresh only queries the current state');
assert.match(nodes.get('studio-pending').textContent,/Pendência/);
// Presentation and copying expose the complete backend record without
// staging/submitting a decision. The banner only opens the same panel.
const proposalParts=nodes.get('studio-detail').children;
assert.equal(proposalParts[0].className,'studio-proposal-summary');
let copied='';
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async text=>{copied=text;}}}});
await proposalParts[2].click();
assert.deepEqual(JSON.parse(copied),next.proposal);
assert.equal(staged,null);
// New engineering views only present already-fetched data. Opening them
// must neither issue requests nor prepare an institutional action.
const savedFetch=globalThis.fetch;
globalThis.fetch=()=>{throw Error('opening an engineering view must not fetch')};
nodes.get('studio-selection').onchange({target:{value:'project'}});
assert.equal(nodes.get('studio-detail').children[0].textContent,'Projeto e escopo');
assert.equal(nodes.get('studio-controls').children.length,0);
nodes.get('studio-selection').onchange({target:{value:'review'}});
assert.equal(nodes.get('studio-detail').children[0].textContent,'Revisão da tarefa');
assert.equal(nodes.get('studio-controls').children.length,0);assert.equal(staged,null);
nodes.get('studio-selection').onchange({target:{value:'task'}});
assert.equal(nodes.get('studio-detail').children[0].textContent,'Preparar tarefa');
assert.equal(nodes.get('studio-controls').children.length,0);assert.equal(staged,null);
nodes.get('studio-selection').onchange({target:{value:'proposal'}});
globalThis.fetch=savedFetch;
// Identical activity notifications must not replace the displayed evidence,
// reset an expanded disclosure, or rebuild the selection under keyboard focus.
const selectorBefore=nodes.get('studio-selection').children;
document.dispatchEvent(new CustomEvent('studio-activity',{detail:{state:'understanding'}}));
const evidenceBefore=nodes.get('studio-detail').children;
document.dispatchEvent(new CustomEvent('studio-activity',{detail:{state:'understanding'}}));
assert.equal(nodes.get('studio-detail').children,evidenceBefore);
assert.equal(nodes.get('studio-selection').children,selectorBefore);
document.dispatchEvent(new CustomEvent('studio-activity',{detail:{state:'idle'}}));
await nodes.get('studio-pending').children.at(-1).click();
assert.equal(nodes.get('studio-context').hidden,false);
assert.equal(nodes.get('chat-container').inert,false);
nodes.get('chat-history').scrollTop=123;
nodes.get('message').value='Rascunho preservado';
await nodes.get('studio-expand').click();
assert.equal(nodes.get('studio-expand').attrs['aria-pressed'],'true');
assert.equal(nodes.get('studio-context').attrs['aria-modal'],'true');
assert.equal(nodes.get('chat-container').inert,true);
await nodes.get('studio-expand').click();
assert.equal(nodes.get('chat-container').inert,false);
assert.equal(nodes.get('chat-history').scrollTop,123);
assert.equal(nodes.get('message').value,'Rascunho preservado');
await nodes.get('studio-pin').click();
document.dispatchEvent({type:'pointerdown',target:nodes.get('message')});
assert.equal(nodes.get('studio-context').hidden,false,'pinned overlay stays open');
await nodes.get('studio-pin').click();
document.dispatchEvent({type:'pointerdown',target:nodes.get('message')});
assert.equal(nodes.get('studio-context').hidden,true,'outside click closes unpinned overlay');
window.innerWidth=640;
await nodes.get('studio-context-open').click();
assert.equal(nodes.get('studio-context').attrs['aria-modal'],'true');
assert.equal(nodes.get('chat-container').inert,true);
document.dispatchEvent({type:'keydown',key:'Escape',preventDefault(){}});
assert.equal(nodes.get('studio-context').hidden,true);
assert.equal(nodes.get('chat-container').inert,false);
assert.equal(nodes.get('chat-history').scrollTop,123);
window.innerWidth=1280;
await nodes.get('studio-context-open').click();
await nodes.get('studio-close').click();
assert.equal(nodes.get('studio-context').hidden,true);
assert.match(nodes.get('studio-pending').textContent,/Pendência/);
assert.equal(shell.canStageMobsAction({action:'review',proposalId:'p',proposalDigest:'stale',authoritySnapshot:'snap'}),false);
await nodes.get('studio-controls').children[0].click();
assert.equal(staged.action,'review');
assert.match(nodes.get('studio-prepared-label').textContent,/Ainda não enviada/);
assert.equal(nodes.get('message').required,false);
await nodes.get('studio-discard').click();
assert.equal(staged,null); assert.equal(nodes.get('message').required,true);
await nodes.get('studio-controls').children[0].click();
next=fixture('a','replaced'); await shell.refresh(); assert.equal(staged,null);
next={...fixture('a'),active:true};await shell.refresh();
assert.equal(shell.canChangeWorkspace('/other'),false); assert.equal(shell.canChangeModel(),false);
assert.equal(shell.canChangeWorkspace('/same'),true);
next={...fixture('a'),proposal:{...fixture('a').proposal,status:'approved'},continuity:'unconfirmed',actions:[]};await shell.refresh();
assert.match(nodes.get('studio-validity').textContent,/não confirmada/);assert.equal(shell.canChangeWorkspace('/other'),false);
assert.equal(shell.canChangeModel(),false);
let resolves=[]; globalThis.fetch=()=>new Promise(resolve=>resolves.push(resolve));
sid='old';const old=shell.refresh(true);sid='new';const fresh=shell.refresh(true);
resolves[1]({ok:true,json:async()=>fixture('new','new-digest')});await fresh;
resolves[0]({ok:true,json:async()=>fixture('old','old-digest')});await old;
assert.equal(shell.canStageMobsAction({action:'review',proposalId:'p',proposalDigest:'new-digest',authoritySnapshot:'snap'}),true);
assert.equal(shell.canStageMobsAction({action:'review',proposalId:'p',proposalDigest:'old-digest',authoritySnapshot:'snap'}),false);
// A two-file candidate stays observational until an explicit action is staged.
next={...fixture('new'),promotions:[{id:'pair',status:'human_approval_required',validity:'valid',validated:true,
  artifact_digest:'pair-digest',actions:['promote'],effects:[{effect:'write',path:'src/app.py'},{effect:'create',path:'tests/test_app.py'}]}]};
globalThis.fetch=async()=>({ok:true,json:async()=>next});await shell.refresh();
chat.clearPreparedMobsAction();
nodes.get('studio-selection').onchange({target:{value:'pair'}});
const pair=nodes.get('studio-detail').children[0];
assert.equal(pair.className,'studio-promotion-summary');
assert.match(pair.children[2].textContent,/Validação registrada/);
assert.equal(pair.children[3].children.length,2);
assert.equal(pair.children[3].children[0].children[0].textContent,'src/app.py');
assert.equal(pair.children[3].children[1].children[1].textContent,' · Criar');
assert.match(pair.children[4].textContent,/não mostra as diferenças/);
assert.equal(staged,null,'inspecting a candidate must not stage approval');
const previewData={...next,preview:{validity:'valid',session_id:'new',promotion_id:'pair',artifact_digest:'pair-digest',files:[
 {path:'src/app.py',effect:'write',before:'pass\n',after:'<script>literal text</script>\n',diff:'-pass\n+<script>literal text</script>'},
 {path:'tests/test_app.py',effect:'create',before:'',after:'assert True\n',diff:'+assert True'}]}};
globalThis.fetch=async()=>({ok:true,json:async()=>previewData});
await pair.children[6].click();
assert.equal(pair.children[7].children.length,2);
assert.equal(pair.children[7].children[0].children[1].textContent,'-pass\n+<script>literal text</script>');
assert.equal(staged,null,'reading sealed bytes must never stage a decision');
let refreshPreview;
globalThis.fetch=url=>url.includes('promotion_id=') ? new Promise(resolve=>refreshPreview=resolve) :
  Promise.resolve({ok:true,json:async()=>next});
const whileRefreshing=pair.children[6].click();
await shell.refresh();
refreshPreview({ok:true,json:async()=>previewData});await whileRefreshing;
assert.equal(pair.children[6].disabled,false,'state refresh must not permanently disable comparison');
assert.match(pair.children[7].textContent,/estado foi atualizado/);
let cancelledPreview,cancelledSignal;
globalThis.fetch=(url,options)=>{cancelledSignal=options.signal;return new Promise(resolve=>cancelledPreview=resolve)};
const closingPreview=pair.children[6].click();
await nodes.get('studio-close').click();assert.equal(cancelledSignal.aborted,true);
cancelledPreview({ok:true,json:async()=>previewData});await closingPreview;
assert.match(pair.children[7].textContent,/Consulta cancelada/);
assert.equal(pair.children[6].disabled,false);
let finishPreview;
globalThis.fetch=()=>new Promise(resolve=>finishPreview=resolve);
const latePreview=pair.children[6].click();
nodes.get('studio-selection').onchange({target:{value:'proposal'}});
const afterSelection=nodes.get('studio-detail').children;
finishPreview({ok:true,json:async()=>previewData});await latePreview;
assert.equal(nodes.get('studio-detail').children,afterSelection,'late preview cannot replace another selection');
globalThis.fetch=async()=>({ok:false});await shell.refresh();
assert.match(nodes.get('studio-validity').textContent,/bloqueadas/);
assert.equal(nodes.get('studio-controls').children.length,0);
nodes.get('studio-selection').onchange({target:{value:'activity'}});
assert.equal(nodes.get('studio-detail').children[0].textContent,'Atividade e arquivos');
assert.match(nodes.get('studio-detail')._studioWorkUI.list.textContent,/Nenhuma atividade/);
assert.equal(nodes.get('studio-controls').children.length,0,'activity inspection cannot authorize or stage execution');
let sharedFinish,sharedQueries=0;
globalThis.fetch=()=>{sharedQueries++;return new Promise(resolve=>sharedFinish=resolve)};
const sharedFirst=shell.refresh(),sharedSecond=shell.refresh();
assert.equal(sharedQueries,1,'overlapping observations of the same session share one request');
sharedFinish({ok:true,json:async()=>fixture('new')});await sharedFirst;await sharedSecond;
globalThis.fetch=async()=>({ok:true,json:async()=>fixture('new')});
// Desktop reload works explicitly, without losing a draft/preparation or
// disconnecting an active stream, including one in another conversation.
let reloads=0, streamSession=null;
window.location={reload(){reloads++}};
chat.hasActiveStream=id=>id===streamSession;
const reload=()=>document.dispatchEvent({type:'keydown',key:'r',ctrlKey:true,preventDefault(){}});
nodes.get('message').value='';reload();assert.equal(reloads,1);
nodes.get('message').value='draft';reload();assert.equal(reloads,1);
nodes.get('message').value='';
chat.stageMobsAction({action:'review',proposalId:'p'});reload();assert.equal(reloads,1);
chat.clearPreparedMobsAction();
streamSession=sid;reload();assert.equal(reloads,1);
streamSession='background';reload();assert.equal(reloads,1);
streamSession=null;reload();assert.equal(reloads,2);
document.dispatchEvent(new CustomEvent('studio-session-selected',{detail:{session:sid}}));
nodes.get('studio-selection').onchange({target:{value:'activity'}});
assert.match(nodes.get('studio-detail').children[0].textContent,/Aguardando o histórico/);
document.dispatchEvent(new CustomEvent('studio-history-ready',{detail:{session:'different',loaded:true}}));
assert.match(nodes.get('studio-detail').children[0].textContent,/Aguardando o histórico/);
document.dispatchEvent(new CustomEvent('studio-history-ready',{detail:{session:sid,loaded:false}}));
assert.match(nodes.get('studio-detail').children[0].textContent,/Histórico indisponível/);
document.dispatchEvent(new CustomEvent('studio-history-ready',{detail:{session:sid,loaded:true}}));
assert.equal(nodes.get('studio-detail').children[0].textContent,'Atividade e arquivos');
console.log('lifecycle assertions complete');
'''.replace('MODULE', repr(module))
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_compact_sidebar_width_preserves_legacy_preference_and_remains_resizable():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static/js/init.js').read_text(encoding='utf-8')
    restore = source[source.index('  const studioSidebar ='):source.index('  let startX, startWidth')]
    script = r'''
import assert from 'node:assert/strict';
const {KEYS}=await import(STORAGE);
for(const [studio,preferred,expected] of [[true,null,200],[true,'280',280],[false,null,600]]) {
 const values={[KEYS.SIDEBAR_WIDTH]:'600'};
 if(preferred)values[KEYS.STUDIO_SIDEBAR_WIDTH]=preferred;
 const document={getElementById:()=>studio?{}:null};
 const sidebar={style:{}};
 const Storage={KEYS,get:(key,fallback)=>values[key]??fallback};
'''+restore+r'''
 assert.equal(getSavedWidth(),expected);
 assert.equal(values[KEYS.SIDEBAR_WIDTH],'600');
 if(preferred||!studio)assert.equal(sidebar.style.width,expected+'px');
 else assert.equal(sidebar.style.width,undefined);
}
'''
    script = script.replace('import(STORAGE)', 'import(' + repr((root / 'static/js/storage.js').as_uri()) + ')')
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_model_switch_does_not_change_route_when_blocked_rejected_or_pending():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/modelPicker.js').read_text(encoding='utf-8')
    pick = source[source.index('  async function _pick(m) {'):source.index("  btn.addEventListener('pointerdown'")]
    script = r'''
const assert = require('node:assert/strict');
let _defaultPendingSeq=0, calls=0, events=0, canChange=false;
const current={id:'s',model:'old',endpoint_url:'old-url',endpoint_id:'old-id'};
const _deps={getCurrentSessionId:()=> 's',getPendingChat:()=>null,getSessions:()=>[current]};
const window={innerWidth:400,studioShell:{canChangeModel:()=>canChange},__odysseusLastPickedRoute:{model:'old'}};
const document={activeElement:null,dispatchEvent(){events++}};
const API_BASE=''; const _pushRecent=()=>{},_pickerModelKey=m=>m.mid,_close=()=>{},updateModelPicker=()=>{};
const uiModule={showError(){},showToast(){}};
let fetch=async()=>{calls++;return {ok:false}};
'''+pick+r'''
(async()=>{
const next={mid:'new',url:'new-url',endpointId:'new-id',display:'New'};
await _pick(next);
assert.equal(calls,0);assert.equal(events,0);assert.equal(_defaultPendingSeq,0);
assert.equal(current.model,'old');assert.equal(window.__odysseusLastPickedRoute.model,'old');
canChange=true;await _pick(next);
assert.equal(current.model,'old');assert.equal(window.__odysseusLastPickedRoute.model,'old');assert.equal(events,0);
let resolve;fetch=()=>new Promise(r=>resolve=r);
const pending=_pick(next);
assert.equal(current.model,'old');assert.equal(window.__odysseusLastPickedRoute.model,'old');
resolve({ok:true});await pending;
assert.equal(current.model,'new');assert.equal(window.__odysseusLastPickedRoute.model,'new');assert.equal(events,1);
})();
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_inspected_response_tracks_content_without_spinner_or_repeated_replacement():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/studioShell.js').read_text(encoding='utf-8')
    function = source[source.index('  function responseDetail() {'):source.index('  function render() {')]
    script = r"""
import assert from 'node:assert/strict';
let responseSignature=null, replacements=0, removed=0, streaming=true, active=true;
let historyState='ready';const historyAvailable=()=>historyState==='ready';
const chat={hasActiveStream:()=>active}, session=()=> 'synthetic';
const detail={children:[],replaceChildren(...children){this.children=children;replacements++;}};
const validity={textContent:''};
const el=id=>id==='studio-detail'?detail:validity;
function detailText(text){detail.replaceChildren({textContent:text});}
let content='', transient='Processando solicitação';
const body={cloneNode(){return {
  get innerHTML(){return content;},get textContent(){return content;},
  querySelectorAll(selector){
    if(selector==='.censored-item') return [];
    assert.match(selector,/\.ai-spinner/); assert.match(selector,/script,style/);
    return [{remove(){removed++;}}];
  }
};}};
let inspectedMessage={isConnected:true,querySelector(){return body;},classList:{contains(){return streaming;}}};
const history={contains:node=>node===inspectedMessage};
"""+function+r"""
responseDetail();
assert.match(detail.children[0].textContent,/Aguardando conteúdo/);
assert.doesNotMatch(detail.children[0].textContent,/Processando solicitação/);
const initial=replacements;
responseDetail();assert.equal(replacements,initial);
content='<p>Resposta <strong>real</strong></p><pre><code>return 2</code></pre>';
responseDetail();assert.equal(detail.children[0].className,'studio-response-body');
assert.match(detail.children[0].innerHTML,/<strong>real<\/strong>/);
const partial=replacements;
responseDetail();assert.equal(replacements,partial);
active=false;responseDetail();assert.match(validity.textContent,/Não representa aprovação/);
streaming=false;responseDetail();assert.match(validity.textContent,/Não representa aprovação/);
assert.ok(removed>0);
inspectedMessage.isConnected=false;responseDetail();
assert.match(detail.children[0].textContent,/indisponível nesta conversa/);
const missing=replacements;responseDetail();assert.equal(replacements,missing);
"""
    result = subprocess.run(['node','--input-type=module','-e',script],capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_inspection_rejects_previous_conversation_while_history_is_loading():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'static/js/studioShell.js').read_text(encoding='utf-8')
    begin = source.index('      b.onclick = () => {', source.index("b.textContent = 'Inspecionar resultado'"))
    guard = source[begin + len('      b.onclick = () => {'):source.index('        inspectedMessage = msg;',begin)]
    script = r"""
const assert=require('node:assert/strict');
let current='new', notices=0;
const session=()=>current, messageSession='old';
const msg={isConnected:true},history={contains:()=>true};
function notice(text){assert.match(text,/carregamento/);notices++;}
function attempt(){
"""+guard+r"""
throw new Error('Stale message was inspected');
}
attempt();assert.equal(notices,1);
current='old';msg.isConnected=false;attempt();assert.equal(notices,2);
"""
    result = subprocess.run(['node','-e',script],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
