from tests.test_studio_engineering_js import run


def test_handoff_uses_only_scoped_references_and_never_extracts_private_content():
    run(r'''
globalThis.fetch=()=>{throw Error('no requests')};
const S=await import(new URL('./studioSources.js',new URL('studioEngineering.js', 'file:///'+process.cwd().replaceAll('\\','/')+'/static/js/')));
const h=new E(),a=tool(h,'PRIVATE_COMMAND','error'),b=tool(h,'FOREIGN_TOOL','');
S.recordSourceSnapshot(a,{tool:'read_file',exit_code:0,workspace:'C:/A',source_reference:{path:'src/a.py',start_line:3,workspace:'C:/A'},output:'PRIVATE_FILE_CONTENT\n'});
b.dataset.studioToolWorkspace='C:/B';b.dataset.studioSource=JSON.stringify({path:'FOREIGN_PATH',text:'FOREIGN_CONTENT',start:1,workspace:'C:/B'});
const raw=new E('pre');raw.textContent='PRIVATE_RAW_OUTPUT';a.appendChild(raw);
const message=new E();h.appendChild(message);A.renderStudioPlan(message,'- [x] PRIVATE_PLAN\n- [ ] pending');
const report=G.developmentHandoff({session_id:'one',workspace:'c:/A',validity:'valid',reviewed:true,proposal:{proposal_id:'p1',proposal_digest:'a'.repeat(64),authority_snapshot:'b'.repeat(64),status:'approved'},promotions:[{id:'c1',artifact_digest:'c'.repeat(64),validity:'valid',validated:true}]},h,{objective:'fix average',blockers:'need validation',next:'inspect source'});
assert.match(report,/Objetivo manual: fix average/);assert.match(report,/1 registros, 0 em andamento, 1 com falha/);
assert.match(report,/fora deste escopo ou sem workspace: 1/);assert.match(report,/1\/2 etapas marcadas/);
assert.match(report,/"src\/a.py": 3–3/);assert.match(report,/validação exata informada/);
assert.match(report,/não comprova promoção ou objetivo/);assert.match(report,/não é prova de execução/);
assert.doesNotMatch(report,/PRIVATE_COMMAND|FOREIGN_TOOL|FOREIGN_PATH|FOREIGN_CONTENT|PRIVATE_FILE_CONTENT|PRIVATE_RAW_OUTPUT|PRIVATE_PLAN/);
''')


def test_scope_mismatch_loading_and_invalid_digests_cannot_claim_authority():
    run(r'''
const view={session_id:'one',workspace:'C:/A',validity:'valid',reviewed:true,proposal:{status:'approved',proposal_digest:'invalid'},promotions:[{id:'x',validated:true,validity:'valid',artifact_digest:'bad'}]};
for(const safe of [G.handoffScopedView(view,'two','C:/A'),G.handoffScopedView(view,'one','C:/B'),G.handoffScopedView(view,'one','C:/A',true)]) {
 const report=G.developmentHandoff(safe,new E());
 assert.match(report,/Consulta institucional: não confirmada/);assert.match(report,/Autorização: não confirmada/);
 assert.doesNotMatch(report,/validação exata informada/);
}
const matching=G.handoffScopedView(view,'one','c:\\A');assert.equal(matching.validity,'valid');
const report=G.developmentHandoff(matching,new E());assert.match(report,/Digest: não registrada/);assert.match(report,/validação exata não confirmada/);assert.match(report,/Autorização: não confirmada/);
''')


def test_handoff_notes_survive_same_scope_refresh_and_stale_controls_are_inert():
    run(r'''
globalThis.fetch=()=>{throw Error('no requests')};
const target=new E(),h=new E(),view={session_id:'one',workspace:'C:/A',validity:'unavailable'};
G.renderDevelopmentHandoff(target,view,h);let state=target._studioHandoff;
state.fields.objective.value='keep objective';state.fields.objective.oninput();const old=state.copy;
G.renderDevelopmentHandoff(target,{...view,validity:'valid'},h);
assert.equal(target._studioHandoff,state);assert.equal(state.fields.objective.value,'keep objective');
await state.copy.onclick();assert.match(copied[0],/keep objective/);assert.match(target.textContent,/nenhuma tarefa foi enviada/);
G.renderDevelopmentHandoff(target,{...view,workspace:'C:/B'},h);
assert.equal(target._studioHandoff.fields.objective.value,'');await old.onclick();assert.equal(copied.length,1);
const last=target._studioHandoff;G.renderDevelopmentHandoff(target,{...view,session_id:'two'},h);
last.fields.objective.value='stale';last.fields.objective.oninput();assert.doesNotMatch(target.textContent,/stale/);
navigator.clipboard.writeText=async()=>{throw Error('denied')};await target._studioHandoff.copy.onclick();
assert.match(target.textContent,/Cópia indisponível/);
''')


def test_handoff_limits_and_malformed_records_remain_literal():
    run(r'''
const h=new E();
for(let i=0;i<120;i++) {const n=tool(h,'read_file','');n.dataset.studioSource=JSON.stringify({path:'src/'+i+'<script>.py',text:'PRIVATE\n',start:1,workspace:'C:/A'});}
for(const raw of ['null','{bad','[null]',JSON.stringify([{text:'secret plan',done:true}]),' '.repeat(70000)]){const plan=new E('details','studio-plan');plan.dataset.signature=raw;h.appendChild(plan);}
const report=G.developmentHandoff({session_id:'s',workspace:'C:/A',promotions:Array(30).fill(null)},h,{objective:'O'.repeat(10000),blockers:'B'.repeat(10000),next:'N'.repeat(10000)});
assert.ok(report.length<35000);assert.match(report,/referências limitada/);assert.doesNotMatch(report,/PRIVATE|secret plan/);
assert.equal((report.match(/- Candidato /g)||[]).length,10);
const target=new E();G.renderDevelopmentHandoff(target,{session_id:'s',workspace:'C:/A'},h);assert.equal(target.querySelector('script'),null);
''')


def test_handoff_refresh_observes_new_evidence_without_replacing_notes():
    run(r'''
const target=new E(),h=new E(),view={session_id:'s',workspace:'C:/A',validity:'valid'};
G.renderDevelopmentHandoff(target,view,h);const state=target._studioHandoff;state.fields.next.value='check receipt';state.fields.next.oninput();
const n=tool(h,'bash','running');n.dataset.studioToolWorkspace='C:/A';
G.renderDevelopmentHandoff(target,view,h);assert.equal(target._studioHandoff,state);assert.match(state.preview.textContent,/1 em andamento/);
n.className='agent-thread-node error';await state.copy.onclick();assert.match(copied[0],/0 em andamento, 1 com falha/);assert.match(copied[0],/check receipt/);
''')


def test_handoff_escapes_untrusted_paths_and_caps_the_entire_report():
    run(r'''
const h=new E();for(let i=0;i<22;i++) {
 const node=tool(h,'read_file','');node.dataset.studioSource=JSON.stringify({path:'\u0000'.repeat(500)+i,text:'known\n',start:1,workspace:'C:/A'});
}
const report=G.developmentHandoff({session_id:'s',workspace:'C:/A'},h,{objective:'O'.repeat(4000),blockers:'B'.repeat(4000),next:'N'.repeat(4000)});
assert.ok(report.length<32100);assert.match(report,/Resumo limitado a 32.000/);assert.equal(report.includes('\u0000'),false);
assert.match(report,/Não concede autorização/);
''')
