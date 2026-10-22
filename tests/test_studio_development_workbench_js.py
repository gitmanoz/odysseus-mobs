"""Offline UI behavior for long development sessions; no provider/DB/tool calls."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


DOM = r'''
import assert from 'node:assert/strict';
class E {
 constructor(tag='div',cls=''){this.tagName=tag;this.className=cls;this.children=[];this.dataset={};this.attrs={};this.value='';this._text='';this.classList={contains:c=>this.className.split(' ').includes(c),add:c=>{if(!this.className.split(' ').includes(c))this.className+=' '+c}};}
 set textContent(v){this._text=String(v);for(const child of this.children)child.parentNode=null;this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 appendChild(e){e.remove();this.children.push(e);e.parentNode=this;return e;}
 replaceChildren(...es){this.textContent='';for(const e of es)this.appendChild(e);}
 remove(){if(this.parentNode)this.parentNode.children.splice(this.parentNode.children.indexOf(this),1);this.parentNode=null;}
 setAttribute(k,v){this.attrs[k]=v;}
 contains(e){while(e){if(e===this)return true;e=e.parentNode;}return false;}
 closest(s){let n=this;while(n){if(n.matches(s))return n;n=n.parentNode;}return null;}
 matches(s){return s.startsWith('.')?this.classList.contains(s.slice(1)):this.tagName===s;}
 querySelectorAll(s){let result=[];for(const child of this.children){if(child.matches(s))result.push(child);result.push(...child.querySelectorAll(s));}return result;}
 querySelector(s){if(s.startsWith(':scope > '))return this.children.find(c=>c.matches(s.slice(9)))||null;return this.querySelectorAll(s)[0]||null;}
 focus(){this.focused=true;globalThis.document.activeElement=this;}
 scrollIntoView(){this.scrolled=true;}
}
globalThis.document={body:{classList:{contains:()=>true}},createElement:tag=>new E(tag)};
let copied=[];
Object.defineProperty(globalThis,'navigator',{value:{clipboard:{writeText:async text=>copied.push(text)}},configurable:true});
const A=await import(ACTIVITY),P=await import(PREVIEW);
function tool(history,name,status,file=''){
 const thread=new E('div','agent-thread'),node=new E('div',`agent-thread-node ${status}`),label=new E('span','agent-thread-tool');label.textContent=name;
 node.dataset.studioDiffFile=file;node.appendChild(label);thread.appendChild(node);history.appendChild(thread);return node;
}
'''


def run_js(script):
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    root = Path(__file__).resolve().parents[1] / 'static/js'
    prelude = DOM.replace('ACTIVITY', json.dumps((root / 'studioActivity.js').as_uri())).replace('PREVIEW', json.dumps((root / 'studioArtifactPreview.js').as_uri()))
    result = subprocess.run(['node', '--input-type=module', '-e', prelude + script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_workbench_filters_search_revision_counts_and_input_identity():
    run_js(r'''
const history=new E(),panel=new E();
tool(history,'read_file','running');const failed=tool(history,'write_file','error','src/a.py');tool(history,'edit_file','','src/a.py');
A.renderStudioWorkSummary(panel,history,'A');let state=panel._studioWorkUI;
assert.match(state.count.textContent,/3\/3 registros.*1 em andamento.*1 com falha.*1 arquivos/);
assert.match(state.files.textContent,/src\/a.py · 2 revisão/);
state.filter.value='failed';state.filter.onchange();assert.equal(state.list.children.length,1);assert.match(state.list.textContent,/write_file/);
state.search.value='SRC/A.PY';state.search.oninput();assert.equal(state.list.children.length,1);
state.search.focus();failed.className='agent-thread-node';A.renderStudioWorkSummary(panel,history,'A');
assert.equal(panel._studioWorkUI.search,state.search);assert.equal(document.activeElement,state.search);assert.match(state.list.textContent,/Nenhum registro/);
state.filter.value='files';state.filter.onchange();assert.equal(state.list.children.length,2);
state.list.children[0].focus();failed.className='agent-thread-node running';A.renderStudioWorkSummary(panel,history,'A');
assert.equal(document.activeElement,state.list.children[0],'status updates preserve keyboard navigation focus');
A.renderStudioWorkSummary(panel,history,'B');assert.notEqual(panel._studioWorkUI,state);assert.equal(panel._studioWorkUI.search.value,'');
''')


def test_workbench_copy_omits_raw_output_and_stale_navigation_is_inert():
    run_js(r'''
const history=new E(),panel=new E(),node=tool(history,'bash','','src/a.py');
const secret=new E('pre');secret.textContent='PRIVATE_RAW_OUTPUT';node.appendChild(secret);
A.renderStudioWorkSummary(panel,history,'session-A');const state=panel._studioWorkUI;
await state.search.parentNode.children[2].onclick();assert.equal(copied.length,1);assert.match(copied[0],/session-A/);assert.doesNotMatch(copied[0],/PRIVATE_RAW_OUTPUT/);
const jump=state.list.children[0];node.remove();jump.onclick();assert.equal(node.focused,undefined);
navigator.clipboard.writeText=async()=>{throw new Error('denied')};await state.search.parentNode.children[2].onclick();assert.match(state.feedback.textContent,/Cópia indisponível/);
''')


def test_plan_parser_ignores_examples_and_index_preserves_literal_steps():
    run_js(r'''
const text='- [x] done\n```md\n- [x] example only\n```\n- [-] <script>current</script>\n~~~\n- [ ] another example\n~~~\n- [ ] pending';
const steps=A.parseStudioPlan(text);assert.equal(steps.length,3);assert.equal(steps[1].current,true);
const history=new E(),message=new E(),panel=new E();history.appendChild(message);A.renderStudioPlan(message,text);
assert.equal(message.children[0].querySelector('ul').children[1].attrs['aria-current'],'step');
A.renderStudioPlanIndex(panel,history);assert.match(panel.textContent,/<script>current<\/script>/);assert.doesNotMatch(panel.textContent,/example only/);
const original=message.children[0],jump=panel.querySelector('.studio-file-index').querySelector('button');original.remove();jump.onclick();assert.equal(original.focused,undefined);
''')


def test_sealed_preview_copy_exact_bytes_display_modes_and_empty_create():
    run_js(r'''
const file={path:'<img>.py',effect:'create',before:'',after:'print("<script>")\n',diff:'--- antes/a\n+++ depois/a\n@@ -0,0 +1 @@\n+print("<script>")'};
const item=P.sealedFilePreview(file);assert.equal(item.children[0].textContent,'<img>.py');assert.match(item.children[2].textContent,/ainda inexistente/);
await item.children[3].children[2].onclick();assert.equal(copied[0],file.after);
await item.children[2].children[2].onclick();assert.equal(copied[1],'');
const select=item.children[6];select.value='after';select.onchange();assert.equal(item.children[1].hidden,true);assert.equal(item.children[2].hidden,true);assert.equal(item.children[3].open,true);
select.value='diff';select.onchange();assert.equal(item.children[1].hidden,false);assert.equal(item.children[3].hidden,true);
const empty=P.sealedFilePreview({...file,effect:'write',before:'',after:''});assert.match(empty.children[2].textContent,/arquivo vazio/);assert.doesNotMatch(empty.children[2].textContent,/inexistente/);
navigator.clipboard.writeText=async()=>{throw new Error('denied')};await item.children[5].onclick();assert.match(item.children[7].textContent,/Cópia indisponível/);
''')


def test_diff_statistics_count_literal_plus_lines_inside_hunk():
    run_js(r'''
assert.deepEqual(P.diffLineStats('--- antes/a\n+++ depois/a\n@@ -1 +1,2 @@\n-old\n+new\n++++literal'),{added:2,removed:1});
assert.deepEqual(P.diffLineStats(''),{added:0,removed:0});
''')


def test_diagnostics_keep_only_observation_fields_and_never_expose_raw_content():
    run_js(r'''
const history=new E(),message=new E('div','msg-ai'),panel=new E();history.appendChild(message);
A.recordStudioDiagnostics(message,{response_time:12,context_length:32768,agent_prep_breakdown:{prompt_build:1.5,invalid:'private'},messages:['PRIVATE_REQUEST'],tool_events:[{output:'PRIVATE_OUTPUT'}],
 initial_context_profile:{estimate_only:true,message_tokens_estimated:100,categories:{protected_context:{estimated_tokens:60,messages:1,raw:'PRIVATE_AUTHORITY'}},duplicate_system_messages:0,tool_schema_count:0,tool_schema_tokens_estimated:0}});
assert.doesNotMatch(message.dataset.studioDiagnostics,/PRIVATE_|private/);
A.renderStudioDiagnostics(panel,history);assert.match(panel.textContent,/32768 tokens/);assert.match(panel.textContent,/Contexto protegido: 60/);assert.match(panel.textContent,/não.*comprovam/);
const unchanged=panel.children[2];A.renderStudioDiagnostics(panel,history);assert.equal(panel.children[2],unchanged);
A.recordStudioDiagnostics(message,{response_time:13});A.renderStudioDiagnostics(panel,history);assert.match(panel.textContent,/13 s/);assert.match(panel.textContent,/60 tokens/);
message.remove();A.renderStudioDiagnostics(panel,history);assert.match(panel.textContent,/Sem medidas/);
''')
