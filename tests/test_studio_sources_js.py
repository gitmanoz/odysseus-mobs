import json
from pathlib import Path
from tests.test_studio_development_workbench_js import run_js

MODULE = (Path(__file__).resolve().parents[1]/'static/js/studioSources.js').as_uri()


def test_pagination_controls_conflicts_and_literal_ranges_never_submit():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
globalThis.fetch=()=>{throw Error('must not send')};
const history=new E(),panel=new E(),node=tool(history,'read_file','');
const event={tool:'read_file',exit_code:0,workspace:'C:/A',source_reference:{path:'src/a.py',start_line:10,workspace:'C:/A'},source_pagination:{has_more:true,next_offset:13,partial_line:false,lines_read:3},output:'a\nb\nc\n'};
S.recordSourceSnapshot(node,event);S.renderSources(panel,history,'one','C:/A');const state=panel._studioSources;
state.tree.querySelector('button').onclick();assert.match(state.viewer.textContent,/Leitura paginada.*13/);
let buttons=state.viewer.querySelectorAll('button');await buttons.find(b=>b.textContent==='Copiar pedido de continuação').onclick();assert.match(copied[0],/linha 13/);
const inputs=state.viewer.querySelectorAll('input');inputs[0].value=11;inputs[1].value=12;
await buttons.find(b=>b.textContent==='Copiar intervalo com referência').onclick();assert.match(copied[1],/src\/a.py:11-12/);assert.match(copied[1],/b\nc$/);
buttons.find(b=>b.textContent==='Ir ao evento de leitura').onclick();assert.equal(node.scrolled,true);
const second=tool(history,'read_file','');S.recordSourceSnapshot(second,{...event,output:'x\nb\nc\n'});S.renderSources(panel,history,'one','C:/A');assert.match(panel.textContent,/Trechos observados divergem/);
const a=S.loadedSources(history);assert.equal(S.groupSourcePages(a).length,1);assert.equal(S.sourceConflicts(a).conflicts.length,1);
S.renderSources(panel,history,'two','C:/B');await buttons.find(b=>b.textContent==='Copiar pedido de continuação').onclick();assert.equal(copied.length,2);
''')


def test_malformed_old_snapshots_unknown_completeness_and_diagnostics_are_bounded():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const history=new E();for(const raw of ['{broken','null','[]','{"path":"bad","text":"secret","start":-1}']){const n=tool(history,'read_file','');n.dataset.studioSource=raw;}
assert.equal(S.loadedSources(history).length,0);assert.match(S.sourceReadStatus({}),/não registrada/);
assert.match(S.sourceReadStatus({partial_line:true}),/parcialmente/);
assert.equal(S.diagnosticLocations(Array(120).fill('src/a.py:12: fail').join('\n')).length,100);
const panel=new E(),source=tool(history,'read_file','');S.recordSourceSnapshot(source,{tool:'read_file',exit_code:0,source_reference:{path:'src/a.py',start_line:1,workspace:'C:/A'},output:'known\nline\n'});
S.renderSources(panel,history,'one','C:/A');const fail=tool(history,'python','error');S.recordSourceSnapshot(fail,{tool:'python',workspace:'C:/A',output:'src/a.py:2: known failure'});
S.renderSources(panel,history,'one','C:/A');assert.match(panel.textContent,/Referência na saída: src\/a.py:2/);
panel._studioSources.pathFilter.value='other';panel._studioSources.pathFilter.oninput();assert.doesNotMatch(panel.textContent,/Referência na saída/);
''')


def test_sources_search_lines_and_stale_controls_stay_inside_loaded_session():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
globalThis.fetch=()=>{throw Error('no network')};
const history=new E(),panel=new E(),node=tool(history,'read_file','');
S.recordSourceSnapshot(node,{tool:'read_file',exit_code:0,source_reference:{path:'src/<script>.py',start_line:20},output:'first\nneedle\nthird'});
S.renderSources(panel,history,'A');let state=panel._studioSources;
assert.match(state.tree.textContent,/src/);assert.equal(panel.querySelector('script'),null);
state.search.value='NEEDLE';state.search.oninput();assert.match(state.matches.textContent,/:21/);
state.matches.querySelector('button').onclick();assert.match(state.viewer.textContent,/20  first\n21  needle/);
const jump=state.matches.querySelector('button'),search=state.search;
S.renderSources(panel,history,'B');jump.onclick();search.oninput();
assert.equal(panel._studioSources.session,'B');assert.equal(panel._studioSources.viewer.textContent,'');
node.remove();S.renderSources(panel,history,'B');assert.match(panel.textContent,/Nenhuma leitura/);
''')


def test_failed_reads_have_no_source_and_search_is_bounded_and_literal():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const node=new E();S.recordSourceSnapshot(node,{tool:'read_file',exit_code:1,source_reference:{path:'secret',start_line:1},output:'hidden'});
assert.equal(node.dataset.studioSource,undefined);
const sources=[{path:'a',start:1,text:Array(120).fill('.*').join('\n')}];
const result=S.searchSources(sources,'.*');assert.equal(result.hits.length,100);assert.equal(result.truncated,true);
assert.equal(S.searchSources(sources,'missing').hits.length,0);
''')


def test_pair_comparison_preserves_exact_copy_and_blocks_stale_reference():
    run_js(r'''
let current=true;
const files=[{path:'src/a.py',effect:'write',before:'a\r\n',after:'b\r\n',diff:'@@ -1 +1 @@\n-a\n+b'},
{path:'tests/test_a.py',effect:'create',before:'',after:'assert True\n',diff:'@@ -0,0 +1 @@\n+assert True'}];
const pair=P.sealedArtifactPreview(files,'digest',()=>current);
assert.match(pair.textContent,/2 arquivo/);assert.match(pair.textContent,/digest/);
const selects=pair.querySelectorAll('select');selects[1].value='selected';selects[0].value='1';selects[0].onchange();
const content=pair.children[4];assert.equal(content.children[0].hidden,true);assert.equal(content.children[1].hidden,false);
await content.children[0].children[3].children[2].onclick();assert.equal(copied[0],'b\r\n');
current=false;await content.children[1].children[3].children[2].onclick();assert.equal(copied.length,1);
''')


def test_identical_path_in_other_project_does_not_reuse_visible_snapshot():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const history=new E(),target=new E(),node=tool(history,'read_file','');
S.recordSourceSnapshot(node,{tool:'read_file',exit_code:0,source_reference:{path:'src/a.py',start_line:1},output:'A-private'});
S.renderSources(target,history,'A');const old=target._studioSources;old.tree.querySelector('button').onclick();
assert.match(old.viewer.textContent,/A-private/);history.replaceChildren();
const other=tool(history,'read_file','');S.recordSourceSnapshot(other,{tool:'read_file',exit_code:0,source_reference:{path:'src/a.py',start_line:1},output:'B-private'});
S.renderSources(target,history,'B');assert.doesNotMatch(target.textContent,/A-private/);
old.tree.querySelector('button').onclick();assert.doesNotMatch(target.textContent,/A-private/);
''')


def test_switching_workspace_in_same_conversation_filters_old_project():
    run_js('const S=await import('+json.dumps(MODULE)+');\n'+r'''
const history=new E(),target=new E();
for(const name of ['A','B']){
 const node=tool(history,'read_file','');S.recordSourceSnapshot(node,{tool:'read_file',exit_code:0,source_reference:{path:'src/a.py',start_line:1,workspace:`C:\\${name}`},output:name+'-private'});
}
S.renderSources(target,history,'same','c:/A');const old=target._studioSources;assert.equal(old.nodes.length,1);
old.tree.querySelector('button').onclick();assert.match(old.viewer.textContent,/A-private/);
S.renderSources(target,history,'same','C:/B');old.tree.querySelector('button').onclick();
target._studioSources.tree.querySelector('button').onclick();
assert.match(target.textContent,/B-private/);assert.doesNotMatch(target.textContent,/A-private/);
''')
