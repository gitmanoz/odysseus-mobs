"""Factual activity presentation and plain waiting timers, without inference."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_activity_preserves_tool_nodes_and_measured_timing_and_cleans_wait_timer():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    root = Path(__file__).resolve().parents[1]
    script = r'''
import assert from 'node:assert/strict';
class E {
 constructor(tag='div',cls=''){this.tagName=tag;this.className=cls;this.dataset={};this.children=[];this.style={};this.attrs={};this.textContent='';this.classList={contains:c=>this.className.split(' ').includes(c),add:c=>{if(!this.className.split(' ').includes(c))this.className+=' '+c}};}
 replaceChildren(...es){for(const c of this.children)c.parentNode=null;this.children=[];this.append(...es);}
 focus(){this.focused=true;}
 scrollIntoView(){this.scrolled=true;}
 remove(){if(this.parentNode)this.parentNode.children.splice(this.parentNode.children.indexOf(this),1);this.parentNode=null;}
 closest(selector){let node=this;while(node){if(node.classList.contains(selector.slice(1)))return node;node=node.parentNode;}return null;}
 setAttribute(k,v){this.attrs[k]=v;}
 append(...es){for(const e of es)this.appendChild(e);}
 appendChild(e){if(e.parentNode)e.parentNode.children.splice(e.parentNode.children.indexOf(e),1);this.children.push(e);e.parentNode=this;}
 insertBefore(e,ref){this.children.splice(this.children.indexOf(ref),0,e);e.parentNode=this;}
 before(e){this.parentNode.insertBefore(e,this);}
 querySelector(selector){const direct=selector.startsWith(':scope > ');selector=selector.replace(':scope > ','');for(const c of this.children){if(selector.split(',').some(s=>s.trim().startsWith('.')?c.classList.contains(s.trim().slice(1)):c.tagName===s.trim()))return c;if(!direct){const found=c.querySelector(selector);if(found)return found;}}return null;}
}
let studio=true,clock=1000,tick=null,cleared=0;
Date.now=()=>clock;
globalThis.document={body:{classList:{contains:()=>studio}},createElement:tag=>new E(tag)};
globalThis.setInterval=fn=>{tick=fn;return 7};globalThis.clearInterval=()=>cleared++;
const {formatElapsed,refreshStudioActivity,renderStudioPlan,planFromToolEvent,renderStudioWorkSummary,toolResultPresentation}=await import(ACTIVITY);
assert.deepEqual(toolResultPresentation({exit_code:0}),{failed:false,icon:'✓',label:'retorno sem erro'});
assert.equal(toolResultPresentation({exit_code:2}).failed,true);
for(const value of [null,undefined,'0',NaN])assert.equal(toolResultPresentation({exit_code:value}).label,'retorno recebido');
assert.equal(formatElapsed(65),'1 min 5 s');
const {create}=await import(SPINNER);
const waiting=create('Preparando resposta','right','wave');
const row=waiting.createElement();waiting.start();clock+=65000;tick();
assert.equal(row.className,'ai-spinner studio-wait');
assert.equal(row.children[1].textContent,'· 1 min 5 s');
waiting.updateMessage('Aguardando resposta do modelo');
assert.equal(row.children[0].textContent,'Aguardando resposta do modelo');
waiting.destroy();assert.equal(cleared,1);assert.equal(waiting.intervalId,null);
studio=false;const legacy=create('Old','right','wave').createElement();assert.match(legacy.innerHTML,/Old/);
const msg=new E('div','msg-ai streaming'),body=new E('div','body');msg.appendChild(body);
const thread=new E('div','agent-thread'),node=new E('div','agent-thread-node running');thread.appendChild(node);
const history={querySelectorAll:s=>s==='.msg-ai'?[msg]:[thread]};
refreshStudioActivity(history,1000);
assert.equal(msg.querySelector('.studio-response-time').textContent,'Em andamento · 0 s');
const group=thread.children[0];assert.equal(group.tagName,'details');
assert.equal(group.children[1].children[0],node);
assert.match(group.children[0].textContent,/em andamento/);
group.open=true;node.className='agent-thread-node error';
msg.className='msg-ai';msg.dataset.studioResponseSeconds='65';
refreshStudioActivity(history,90000);
assert.equal(msg.querySelector('.studio-response-time').textContent,'Trabalhou por 1 min 5 s');
assert.equal(group.open,true);assert.match(group.children[0].textContent,/com falha/);
assert.doesNotMatch(group.children[0].textContent,/concluída|editou|executou/i);
delete msg.dataset.studioResponseSeconds;msg.className='msg-ai streaming';
refreshStudioActivity(history,95000,false);
assert.doesNotMatch(msg.querySelector('.studio-response-time').textContent,/Em andamento/);
studio=true;
assert.equal(planFromToolEvent({tool:'update_plan',exit_code:0,command:JSON.stringify({plan:'- [x] saved'})}),'- [x] saved');
assert.equal(planFromToolEvent({tool:'update_plan',exit_code:1,command:'- [x] rejected'}),'');
assert.equal(planFromToolEvent({tool:'bash',exit_code:0,command:'- [x] not plan'}),'');
assert.equal(planFromToolEvent({tool:'update_plan',exit_code:0,command:'- [ ] plain'}),'- [ ] plain');
renderStudioPlan(msg,'- [ ] Read file\n- [x] <script>unsafe()</script>\nordinary prose');
const plan=msg.querySelector('.studio-plan');assert.equal(plan.children[0].textContent,'Plano informado pelo agente · 1/2');
assert.equal(plan.children[2].children[1].textContent,'✓ <script>unsafe()</script>');
plan.open=true;renderStudioPlan(msg,'- [x] Read file\n- [x] done');assert.equal(plan.open,true);
assert.equal(plan.children[0].textContent,'Plano informado pelo agente · 2/2');
assert.match(plan.children[1].textContent,/Não concede autorização/);
const count=msg.children.length;renderStudioPlan(msg,'Not a checklist');assert.equal(msg.children.length,count-1);
assert.equal(msg.querySelector('.studio-plan'),null,'a replaced plan must not leave stale progress visible');
const diff=new E('details','agent-tool-diff');node.appendChild(diff);node.dataset.studioDiffFile='<img src=x>.py';
refreshStudioActivity(history,95000,false);
const index=group.querySelector('.studio-file-index');assert.equal(index.children[1].textContent,'<img src=x>.py · ferramenta com falha');
index.children[1].onclick();assert.equal(diff.open,true);assert.equal(diff.focused,true);assert.equal(diff.scrolled,true);
assert.equal(group.open,true);assert.equal(node.classList.contains('open'),true);
const button=index.children[1];refreshStudioActivity(history,95000,false);assert.equal(index.children[1],button);
const overview=new E();let toolNodes=[node];const workHistory={querySelectorAll:()=>toolNodes,contains:n=>toolNodes.includes(n)};
renderStudioWorkSummary(overview,workHistory);assert.match(overview._studioWorkUI.list.children[0].textContent,/com falha/);
assert.match(overview.children[1].textContent,/não comprova/);
overview._studioWorkUI.list.children[0].onclick();assert.equal(node.focused,true);
const same=overview._studioWorkUI.list;renderStudioWorkSummary(overview,workHistory);assert.equal(overview._studioWorkUI.list,same);
const replacement=new E('div','agent-thread-node running');replacement.dataset.studioDiffFile=node.dataset.studioDiffFile;toolNodes=[replacement];
renderStudioWorkSummary(overview,workHistory);assert.match(overview._studioWorkUI.list.children[0].textContent,/em andamento/);
thread.dataset.docWriting='true';toolNodes=[node];renderStudioWorkSummary(overview,workHistory);
assert.match(overview._studioWorkUI.list.textContent,/Nenhuma atividade/);
studio=false;const unrelated=new E();renderStudioPlan(unrelated,'- [x] hidden');assert.equal(unrelated.children.length,0);
console.log('timing, cleanup, legacy mode, original tool nodes, expansion and honest status verified');
'''.replace('ACTIVITY', json.dumps((root / 'static/js/studioActivity.js').as_uri())).replace('SPINNER', json.dumps((root / 'static/js/spinner.js').as_uri()))
    result = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
