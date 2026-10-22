"""Read-only engineering views with synthetic server data and an offline DOM."""
import json
from pathlib import Path
from tests.test_studio_development_workbench_js import run_js

MODULE = (Path(__file__).resolve().parents[1] / 'static/js/studioEngineering.js').as_uri()


def run(script):
    run_js(f'const G=await import({json.dumps(MODULE)});\n' + script)


def test_scope_uses_only_presented_fields_and_does_not_read_or_execute():
    run(r'''
globalThis.fetch=()=>{throw Error('render must not request anything')};
const view={session_id:'s',validity:'valid',workspace:'<workspace>',proposal:{
 project_profile:'godot',profile:'development',objective:'<img onerror=alert(1)>',
 allowed_read_paths:['project.godot','src/**'],allowed_write_paths:[],allowed_create_paths:[],
 allowed_tools:['read_file'],allowed_commands:[['python','-m','pytest']],
 authority_documents:{secret:'PRIVATE SOURCE'},raw_tool_output:'PRIVATE OUTPUT'}};
const report=G.projectScopeReport(view);
assert.match(report,/project.godot/);assert.match(report,/python -m pytest/);
assert.doesNotMatch(report,/PRIVATE SOURCE|PRIVATE OUTPUT/);
assert.match(report,/não comprova execução headless/);
const target=new E();G.renderProjectScope(target,view);
assert.match(target.textContent,/<img onerror/);assert.equal(target.querySelector('img'),null);
assert.match(G.projectScopeReport(null),/Sem proposta registrada/);
''')


def test_detached_copy_cannot_copy_previous_conversation_and_payload_is_exact():
    run(r'''
const target=new E(),view={session_id:'first',validity:'valid'};
G.renderProjectScope(target,view);const old=target.querySelector('button');
await old.onclick();assert.equal(copied[0],G.projectScopeReport(view));
G.renderProjectScope(target,{session_id:'second',validity:'unavailable'});
await old.onclick();assert.equal(copied.length,1);
assert.match(target.textContent,/Consulta não confirmada/);
assert.match(target.textContent,/second/);assert.doesNotMatch(target.textContent,/first/);
''')


def test_invalid_observation_cannot_claim_snapshot_or_receipt_confirmation():
    run(r'''
const view={validity:'unavailable',reviewed:true,active:true,proposal:{status:'blocked'},
 promotions:[{id:'candidate',status:'human_approval_required',validity:'valid',validated:true}]};
const result=G.reviewChecklist(view).map(item=>item.state).join('\n');
assert.doesNotMatch(result,/registrada pelo servidor|referência conferida|recibo de validação exato registrado/);
assert.match(result,/não confirmada/);assert.match(result,/bloqueada/);
assert.match(result,/sem execução ativa confirmada/);
const target=new E();G.renderEngineeringReview(target,view);
assert.match(target.textContent,/não comprova o objetivo/);assert.equal(target.querySelectorAll('button').length,1);
''')


def test_valid_receipt_is_reported_without_claiming_promotion_or_objective():
    run(r'''
const view={session_id:'s',validity:'valid',reviewed:true,active:false,
 proposal:{proposal_id:'p',proposal_digest:'d',authority_snapshot:'a'},
 promotions:[{id:'candidate',status:'human_approval_required',validity:'valid',validated:true}]};
const target=new E();G.renderEngineeringReview(target,view);await target.querySelector('button').onclick();
assert.match(copied[0],/recibo de validação exato registrado/);
assert.match(copied[0],/nenhum objetivo, aprovação ou aplicação é certificado/);
assert.doesNotMatch(copied[0],/PRIVATE/);
''')


def test_plan_evidence_updates_without_recreating_open_steps_or_certifying_them():
    run(r'''
const history=new E(),message=new E(),target=new E();history.appendChild(message);
A.renderStudioPlan(message,'- [x] claimed done');A.renderStudioPlanIndex(target,history);
assert.match(target.textContent,/Sem registros de ferramentas/);
const originalList=target.querySelector('.studio-file-index');originalList.children[0].open=true;
const item=tool(history,'read_file','running','src/a.py');A.renderStudioPlanIndex(target,history);
assert.equal(target.querySelector('.studio-file-index'),originalList);assert.equal(originalList.children[0].open,true);
assert.match(target.textContent,/1 registros de ferramentas/);assert.match(target.textContent,/1 em andamento/);
item.className='agent-thread-node error';A.renderStudioPlanIndex(target,history);
assert.match(target.textContent,/1 com falha/);assert.match(target.textContent,/não há vínculo automático/);
''')


def test_context_weights_are_sorted_and_duplicate_metrics_remain_content_free():
    run(r'''
const history=new E(),message=new E('div','msg-ai'),target=new E();history.appendChild(message);
A.recordStudioDiagnostics(message,{initial_context_profile:{estimate_only:true,
 categories:{user:{messages:1,estimated_tokens:10},protected_context:{messages:2,estimated_tokens:90}},
 duplicate_system_messages:1,duplicate_system_tokens_estimated:45,duplicate_protected_messages:1,
 private_content:'PRIVATE CONTENT',tool_schema_count:2,tool_schema_tokens_estimated:5}});
assert.doesNotMatch(message.dataset.studioDiagnostics,/PRIVATE CONTENT/);
A.renderStudioDiagnostics(target,history);
const body=target.textContent;
assert.ok(body.indexOf('Contexto protegido:')<body.indexOf('Mensagens do usuário:'));
assert.match(body,/90% da composição estimada/);assert.match(body,/10% da composição estimada/);
assert.match(body,/Custo estimado das repetições: 45 tokens/);
assert.match(body,/Repetições que são mensagens protegidas: 1/);
assert.match(body,/Nenhuma deduplicação automática/);
assert.doesNotMatch(body,/PRIVATE CONTENT/);
''')


def test_task_draft_copies_without_requests_and_preserves_fields_on_refresh():
    run(r'''
globalThis.fetch=()=>{throw Error('task preparation must stay local')};
const target=new E(),view={session_id:'one',workspace:'old'};
G.renderTaskPreparation(target,view);
const objective=target.querySelectorAll('textarea')[0],acceptance=target.querySelectorAll('textarea')[1];
objective.value='<script>repair bug</script>';acceptance.value='fixture passes';objective.oninput();
const first=target.querySelector('select');first.value='change';first.oninput();
G.renderTaskPreparation(target,{session_id:'one',workspace:'current'});
assert.equal(target.querySelectorAll('textarea')[0],objective);
assert.match(target.textContent,/<script>repair bug<\/script>/);assert.equal(target.querySelector('script'),null);
await target.querySelector('button').onclick();
assert.match(copied[0],/Implementar uma mudança pequena/);assert.match(copied[0],/current/);
assert.match(copied[0],/Copiar não envia mensagem/);assert.match(copied[0],/fixture passes/);
''')


def test_task_draft_is_not_reused_across_conversations_or_detached_controls():
    run(r'''
const target=new E();G.renderTaskPreparation(target,{session_id:'one'});
target.querySelectorAll('textarea')[0].value='private first task';
const old=target.querySelector('button');G.renderTaskPreparation(target,{session_id:'two'});
await old.onclick();assert.equal(copied.length,0);assert.doesNotMatch(target.textContent,/private first task/);
const report=G.developmentTaskReport(null,'unknown');assert.match(report,/Investigar/);assert.match(report,/Selecione o projeto/);
''')


def test_failure_observation_changes_with_tools_without_inventing_cause():
    run(r'''
const history=new E(),target=new E();A.renderStudioDiagnostics(target,history);
assert.match(target.textContent,/Nenhum registro de ferramenta/);
const item=tool(history,'bash','running','tests/probe.py');A.renderStudioDiagnostics(target,history);
assert.match(target.textContent,/1 em andamento/);
item.className='agent-thread-node error';A.renderStudioDiagnostics(target,history);
assert.match(target.textContent,/1 com falha/);assert.match(target.textContent,/Último registro com falha: bash/);
assert.match(target.textContent,/não determina a causa/);assert.doesNotMatch(target.textContent,/memória insuficiente/);
item.remove();A.renderStudioDiagnostics(target,history);assert.match(target.textContent,/Nenhum registro de ferramenta/);
assert.doesNotMatch(target.textContent,/Último registro com falha/);
''')


def test_review_lists_exact_candidate_digest_and_files_without_claiming_application():
    run(r'''
const target=new E();G.renderEngineeringReview(target,{session_id:'one',validity:'valid',promotions:[
 {id:'pair',status:'human_approval_required',validity:'valid',validated:true,artifact_digest:'exact-version',
 effects:[{effect:'write',path:'src/<script>.py'},{effect:'create',path:'tests/test_a.py'}]}]});
assert.match(target.textContent,/Digest do candidato: exact-version/);
assert.match(target.textContent,/Arquivo apresentado: write · src\/<script>.py/);
assert.equal(target.querySelector('script'),null);
assert.match(target.textContent,/não significa arquivo aplicado/);
await target.querySelector('button').onclick();assert.match(copied[0],/tests\/test_a.py/);
''')


def test_round_comparison_distinguishes_history_growth_from_authority_and_schemas():
    run(r'''
const target=new E(),history=new E(),message=new E('div','msg-ai');history.appendChild(message);
A.recordStudioDiagnostics(message,{
 initial_context_profile:{estimate_only:true,message_tokens_estimated:100,categories:{protected_context:{estimated_tokens:80,messages:1},user:{estimated_tokens:20,messages:1}}},
 last_round_context_profile:{estimate_only:true,message_tokens_estimated:145,categories:{protected_context:{estimated_tokens:80,messages:1},user:{estimated_tokens:20,messages:1},tool:{estimated_tokens:45,messages:1}},tool_schema_count:2,tool_schema_tokens_estimated:500}});
A.renderStudioDiagnostics(target,history);
assert.match(target.textContent,/Variação estimada de mensagens até a última rodada: \+45 tokens/);
assert.match(target.textContent,/Variação · Retornos de ferramentas: \+45 tokens/);
assert.doesNotMatch(target.textContent,/Variação · Contexto protegido/);
assert.match(target.textContent,/Não mede desperdício/);assert.match(target.textContent,/~500 tokens/);
''')


def test_evidence_chain_does_not_upgrade_review_or_visual_activity_into_execution():
    run(r'''
const target=new E();
for(const validity of ['valid','unavailable']){
 G.renderEngineeringReview(target,{session_id:'one',validity,reviewed:true,proposal:{status:'approved'}});
 assert.match(target.textContent,/Solicitação → autorização → chamada de ferramenta → despacho → retorno → validação/);
 assert.match(target.textContent,/não certifica sozinho/);
 if(validity==='valid')assert.match(target.textContent,/aprovação registrada pelo servidor; execução ainda exige evidência/);
 else assert.doesNotMatch(target.textContent,/aprovação registrada pelo servidor/);
}
G.renderEngineeringReview(target,{validity:'valid',reviewed:true,proposal:{status:'pending'}});
assert.match(target.textContent,/revisão do snapshot não concede execução/);
const history=new E();tool(history,'bash','returned');A.renderStudioDiagnostics(target,history);
assert.match(target.textContent,/autorização e despacho não são certificados/);
assert.doesNotMatch(target.textContent,/objetivo cumprido confirmado/);
''')
