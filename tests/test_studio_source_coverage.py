import json
from pathlib import Path
from tests.test_studio_development_workbench_js import run_js
from tests.test_studio_engineering_js import run

MODULE = (Path(__file__).resolve().parents[1] / 'static/js/studioSources.js').as_uri()


def test_coverage_reports_only_complete_observed_intervals_and_internal_gaps():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const p=(start,text,extra={})=>({path:'a.py',start,text,...extra});
const sources=[p(10,'a\nb\n'),p(15,'c\nd',{has_more:false}),p(11,'b\nc\n'),p(20,'tail',{partial_line:true})];
assert.deepEqual(S.sourceCoverage(sources),{intervals:[[10,12],[15,16]],gaps:[[13,14]]});
assert.deepEqual(S.sourceCoverage([p(1,'')]),{intervals:[],gaps:[]});
assert.deepEqual(S.sourceCoverage([p(1,'unconfirmed tail')]),{intervals:[],gaps:[]});
assert.equal(sources[1].text,'c\nd');
''')


def test_terminal_conflicts_are_checked_only_when_complete_and_comparison_is_bounded():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const p=(text,extra={})=>({path:'a',start:1,text,...extra});
assert.equal(S.sourceConflicts([p('one',{has_more:false}),p('two',{has_more:false})]).conflicts.length,1);
assert.equal(S.sourceConflicts([p('one'),p('two')]).conflicts.length,0);
assert.equal(S.sourceConflicts([p('one\n'),p('two\n')]).conflicts.length,1);
assert.equal(S.sourceConflicts([p('one',{partial_line:true,has_more:false}),p('two',{has_more:false})]).conflicts.length,0);
const large=p('same\n'.repeat(15000));
assert.equal(S.sourceConflicts(Array(10).fill(large)).limited,true);
''')


def test_empty_crlf_and_clipped_source_controls_keep_content_factual():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
globalThis.fetch=()=>{throw Error('no read or send')};
const h=new E(),target=new E(),node=tool(h,'read_file','');
const event={tool:'read_file',exit_code:0,source_reference:{path:'a.py',start_line:1,workspace:'C:/A'},source_pagination:{has_more:false},output:''};
S.recordSourceSnapshot(node,event);S.renderSources(target,h,'one','C:/A');
let state=target._studioSources;state.tree.querySelector('button').onclick();
assert.match(state.viewer.textContent,/Trecho vazio/);
let copy=state.viewer.querySelectorAll('button').find(x=>x.textContent==='Copiar intervalo com referência');
assert.equal(copy.disabled,true);await copy.onclick();assert.equal(copied.length,0);
S.recordSourceSnapshot(node,{...event,output:'one\r\ntwo\r\n'});S.renderSources(target,h,'one','C:/A');
state.tree.querySelector('button').onclick();
assert.equal(state.viewer.querySelector('pre').textContent,'1  one\n2  two');
let inputs=state.viewer.querySelectorAll('input');inputs[0].value=1;inputs[1].value=2;
await state.viewer.querySelectorAll('button').find(x=>x.textContent==='Copiar intervalo com referência').onclick();
assert.match(copied[0],/one\r\ntwo\r$/);
S.recordSourceSnapshot(node,{...event,output:'clipped',source_pagination:{has_more:true,next_offset:20,presentation_truncated:true}});
S.renderSources(target,h,'one','C:/A');state.tree.querySelector('button').onclick();
assert.equal(state.viewer.querySelectorAll('button').some(x=>x.textContent==='Copiar pedido de continuação'),false);
''')


def test_persisted_provenance_rejects_malformed_hashes_and_shows_gaps():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const h=new E(),target=new E();
for(const start of [1,5]){const n=tool(h,'read_file','');n.dataset.studioSource=JSON.stringify({path:'a.py',text:'known\n',start,head:'invented',baseline:'bad',workspace:'C:/A'});}
assert.equal(S.loadedSources(h)[0].head,'');assert.equal(S.loadedSources(h)[0].baseline,'');
S.renderSources(target,h,'one','C:/A');assert.match(target.textContent,/lacunas internas: 2–4/);
assert.match(target.textContent,/Não certifica leitura integral/);
''')


def test_explicit_clear_and_pending_requests_never_replace_local_draft():
    run(r'''
const target=new E();G.renderTaskPreparation(target,{session_id:'one',workspace:'C:/A'});
const objective=target.querySelectorAll('textarea')[0];objective.value='keep local';objective.oninput();
const buttons=target.querySelectorAll('button'),save=buttons.find(b=>b.textContent==='Salvar rascunho'),restore=buttons.find(b=>b.textContent==='Restaurar rascunho salvo'),clear=buttons.find(b=>b.textContent==='Limpar rascunho salvo');
let release,calls=[];globalThis.fetch=async(url,options)=>{calls.push({url,options});return await new Promise(resolve=>release=()=>resolve({ok:true,json:async()=>({value:null})}));};
const pending=clear.onclick();for(let i=0;i<100&&!release;i++)await new Promise(resolve=>setTimeout(resolve,1));
assert.equal(calls.length,1);assert.equal(JSON.parse(calls[0].options.body).value,null);
assert.equal(save.disabled,true);await save.onclick();await restore.onclick();assert.equal(calls.length,1);
release();await pending;assert.equal(objective.value,'keep local');assert.equal(save.disabled,false);
assert.match(target.textContent,/O texto local foi preservado/);
''')


def test_reduced_export_includes_only_finite_known_phase_totals():
    run_js(r'''
const h=new E(),a=tool(h,'secret command',''),b=tool(h,'secret2','');
a.dataset.studioToolPhases=JSON.stringify({dispatch_seconds:0.1,execution_seconds:2,path:'PRIVATE',command:'SECRET'});
b.dataset.studioToolPhases=JSON.stringify({dispatch_seconds:0.2,execution_seconds:-1});
const result=A.reducedDiagnostics(h);
assert.equal(result.tool_timings.dispatch_seconds.records,2);
assert.ok(Math.abs(result.tool_timings.dispatch_seconds.total_seconds-0.3)<1e-12);
assert.deepEqual(result.tool_timings.execution_seconds,{records:1,total_seconds:2});
assert.doesNotMatch(JSON.stringify(result),/PRIVATE|SECRET|secret command/);
a.dataset.studioToolPhases='malformed';b.dataset.studioToolPhases=JSON.stringify({dispatch_seconds:'1'});
assert.deepEqual(A.reducedDiagnostics(h).tool_timings,{});
''')
