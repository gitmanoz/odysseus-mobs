import json
from pathlib import Path
from tests.test_studio_development_workbench_js import run_js

MODULE = (Path(__file__).resolve().parents[1]/'static/js/studioSources.js').as_uri()


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
