// Observational views; draft persistence uses existing owner-scoped preferences.
import { taskDraftKey, taskDraftRequest } from './studioDrafts.js';
import { collectStudioWork } from './studioActivity.js';
import { loadedSources, groupSourcePages, sourceCoverage } from './studioSources.js';
function text(value, fallback = 'Não registrado') {
  return typeof value === 'string' && value.trim() ? value : fallback;
}
function paths(value) {
  return Array.isArray(value) ? value.filter(item => typeof item === 'string') : [];
}
function commands(value) {
  return Array.isArray(value) ? value.map(command => Array.isArray(command) ? command.join(' ') : text(command, '')).filter(Boolean) : [];
}
function paragraph(target, value) {
  const node = document.createElement('p'); node.textContent = value; target.appendChild(node); return node;
}
function heading(target, value, tag = 'h3') {
  const node = document.createElement(tag); node.textContent = value; target.appendChild(node);
}
function copyReport(target, label, report) {
  const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
  const feedback = document.createElement('p'); feedback.setAttribute('role', 'status');
  button.onclick = async () => {
    // Detached controls must not operate on a conversation selected later.
    if (!target.contains(button)) return;
    try { await navigator.clipboard.writeText(report); if (target.contains(button)) feedback.textContent = 'Relatório copiado.'; }
    catch (_) { if (target.contains(button)) feedback.textContent = 'Cópia indisponível. Selecione o texto para copiar.'; }
  };
  target.appendChild(button); target.appendChild(feedback);
}

export function projectScopeReport(view) {
  const p = view?.proposal;
  const rows = ['MOBS Studio — projeto e escopo',
    'Consulta da proposta existente; não lê novos arquivos, não concede permissões e não inicia uma tarefa.',
    `Conversa: ${text(view?.session_id)}`, `Estado da consulta: ${text(view?.validity)}`];
  if (!p) return [...rows, 'Sem proposta registrada. Selecione o projeto e formule uma tarefa para obter o escopo apresentado pelo backend.'].join('\n');
  rows.push(`Workspace: ${text(view.workspace)}`, `Perfil do projeto: ${text(p.project_profile)}`,
    `Modo: ${text(p.profile)}`, `Objetivo: ${text(p.objective)}`,
    `Proposta: ${text(p.proposal_id)}`, `Versão: ${text(p.proposal_digest)}`,
    `Snapshot: ${text(p.authority_snapshot)}`);
  for (const [key, label] of [['allowed_read_paths', 'Leitura'], ['allowed_write_paths', 'Escrita'], ['allowed_create_paths', 'Criação'], ['allowed_tools', 'Ferramentas']]) {
    rows.push(`${label}: ${paths(p[key]).join(', ') || 'Nenhum item apresentado'}`);
  }
  rows.push(`Receitas apresentadas: ${commands(p.allowed_commands).join('; ') || 'Nenhuma'}`,
    `Exclusões: ${text(p.exclusions)}`,
    'A disponibilidade de uma receita não comprova toolchain instalada, execução ou resultado.');
  if (p.project_profile === 'godot') rows.push('Godot: confira os caminhos e receitas acima. O perfil atual não comprova execução headless, acesso a todos os scripts ou gameplay.');
  return rows.join('\n');
}

export function renderProjectScope(target, view) {
  target.replaceChildren(); heading(target, 'Projeto e escopo');
  if (view?.validity !== 'valid') paragraph(target, 'Consulta não confirmada. O escopo exibido pode ser histórico e não autoriza ações.');
  const report = projectScopeReport(view);
  const body = document.createElement('pre'); body.textContent = report; target.appendChild(body);
  copyReport(target, 'Copiar escopo apresentado', report);
  const recipes = document.createElement('details'), title = document.createElement('summary'); title.textContent = 'O que as receitas apresentadas verificam'; recipes.appendChild(title);
  for (const recipe of validationRecipes(view)) paragraph(recipes, `${recipe.command}: ${recipe.meaning}`);
  target.appendChild(recipes);
}

export function validationRecipes(view) {
  return commands(view?.proposal?.allowed_commands).map(command => {
    let meaning = 'Receita apresentada pelo servidor; finalidade não classificada aqui. Confira argv e escopo antes de solicitar execução.';
    if (/^(?:python -m )?pytest(?:\s|$)/.test(command)) meaning = 'Executa testes selecionados. Retorno zero não prova cobertura completa nem ausência de defeitos.';
    else if (/^python -m py_compile(?:\s|$)/.test(command)) meaning = 'Verifica compilação/sintaxe Python; não executa os testes de comportamento.';
    else if (/^(?:python -m )?ruff(?:\s|$)/.test(command)) meaning = 'Verifica regras estáticas admitidas; não comprova o comportamento em execução.';
    else if (['git_branch_current', 'git_head_current', 'git_status_current'].includes(command) || /^git (?:branch|rev-parse|status)(?:\s|$)/.test(command)) meaning = 'Consulta identidade/estado Git; não altera arquivos nem substitui teste.';
    return { command, meaning };
  });
}

export function reviewChecklist(view) {
  const p = view?.proposal, candidates = Array.isArray(view?.promotions) ? view.promotions : [];
  const fresh = view?.validity === 'valid';
  const pending = candidates.filter(item => ['human_approval_required', 'promotion_preauthorized'].includes(item.status));
  const checks = [
    { label: 'Consulta institucional atual', state: view?.validity === 'valid' ? 'confirmada' : 'não confirmada' },
    { label: 'Proposta identificada', state: p?.proposal_id && p?.proposal_digest && p?.authority_snapshot ? 'registrada' : 'ausente' },
    { label: 'Revisão do snapshot', state: fresh && view?.reviewed === true ? 'registrada pelo servidor' : 'não confirmada' },
    { label: 'Autorização de execução', state: fresh && p?.status === 'approved' ? 'aprovação registrada pelo servidor; execução ainda exige evidência' : 'não confirmada nesta visão; revisão do snapshot não concede execução' },
    { label: 'Atividade no servidor', state: fresh && view?.active === true ? 'execução ativa' : 'sem execução ativa confirmada' },
    { label: 'Candidatos pendentes', state: String(pending.length) },
  ];
  for (const candidate of pending) {
    checks.push({ label: `Artefato ${text(candidate.id)}`,
      state: `${fresh && candidate.validity === 'valid' ? 'referência conferida' : 'referência não confirmada'}; ${fresh && candidate.validity === 'valid' && candidate.validated === true ? 'recibo de validação exato registrado' : 'validação exata não confirmada'}` });
    checks.push({ label: 'Digest do candidato', state: text(candidate.artifact_digest) });
    const effects = Array.isArray(candidate.effects) ? candidate.effects : [candidate];
    for (const effect of effects) {
      if (typeof effect?.path !== 'string') continue;
      checks.push({ label: 'Arquivo apresentado', state: `${text(effect.effect)} · ${effect.path}` });
    }
  }
  if (p?.status === 'blocked') checks.push({ label: 'Última rodada', state: 'bloqueada; consulte o evento original para determinar a causa, sem presumir falta de memória' });
  return checks;
}

export function renderEngineeringReview(target, view) {
  target.replaceChildren(); heading(target, 'Revisão da tarefa');
  paragraph(target, 'Checklist de acompanhamento. Não substitui revisão de código, recibos, confirmação humana ou os controles institucionais.');
  const checks = reviewChecklist(view);
  for (const check of checks) paragraph(target, `${check.label}: ${check.state}`);
  heading(target, 'Antes de decidir', 'h4');
  paragraph(target, 'Confira o objetivo, o escopo e as exclusões em Projeto e escopo. Inspecione o diff e os conteúdos selados do candidato exato.');
  paragraph(target, 'Confronte comandos, retornos e falhas em Atividade e arquivos. Uma marcação no plano ou um retorno sem erro não comprova o objetivo cumprido.');
  heading(target, 'Caminho da evidência', 'h4');
  paragraph(target, 'Solicitação → autorização → chamada de ferramenta → despacho → retorno → validação. Etapas não registradas continuam não comprovadas; não são deduzidas do texto do modelo.');
  paragraph(target, 'A proposta identifica a solicitação e o servidor informa revisão/aprovação. Atividade mostra os registros carregados da conversa. Chamada nativa e despacho precisam dos eventos e recibos originais; um registro visual de ferramenta não certifica sozinho essas etapas.');
  paragraph(target, 'Confirme testes pertinentes, efeitos fora do escopo e possibilidade de rollback. As ações disponíveis continuam na proposta e no artefato, com nova validação no servidor.');
  paragraph(target, 'Arquivo apresentado não significa arquivo aplicado. O recibo confirma somente a validação vinculada ao candidato; não informa aqui cobertura completa de testes ou ausência de riscos. Renomear ou criar arquivos no target pode invalidar o candidato.');
  const report = ['MOBS Studio — revisão da tarefa', `Conversa: ${text(view?.session_id)}`,
    ...checks.map(check => `${check.label}: ${check.state}`),
    'Checklist observacional; nenhum objetivo, aprovação ou aplicação é certificado por este relatório.'].join('\n');
  copyReport(target, 'Copiar checklist de revisão', report);
}

// Task preparation stays local and cannot stage, submit or authorize a mandate.
const taskKinds = { bug: 'Investigar e corrigir um defeito', change: 'Implementar uma mudança pequena', test: 'Validar um comportamento existente' };
export function developmentTaskReport(view, kind = 'bug', objective = '', acceptance = '') {
  const p = view?.proposal;
  return ['MOBS Studio — preparação de tarefa', taskKinds[kind] || taskKinds.bug,
    `Objetivo: ${text(objective, '[Descreva um resultado concreto]')}`,
    `Critérios de aceitação: ${text(acceptance, '[Defina como verificar o resultado]')}`,
    `Workspace apresentado: ${text(view?.workspace, '[Selecione o projeto]')}`,
    `Referência observada: ${text(p?.proposal_id)} / ${text(p?.proposal_digest)}`,
    'Para trabalho comum, comece pelo código, testes e requisitos locais; não inicie Boot institucional.',
    'Se houver decisão institucional ou operação governada, siga o PROJECT_INDEX.md e revalide baseline, escopo e autoridades.',
    'Defina o teste antes de executar. Use somente ferramentas e receitas admitidas, com recursos suficientes e isolamento obrigatório.',
    'Revise um delta pequeno e coeso. A promoção atual admite um arquivo ou exatamente dois; não fragmente um delta atômico para contornar o limite.',
    'Entregue arquivos afetados, chamadas efetivas, comandos/retornos, evidências, regressões e limitações. Texto ou checklist não comprovam execução.',
    'Exclusões: dados pessoais e saves reais, instalação de dependências, publicação, ativação e ampliação de permissões sem autorização específica.',
    'Este texto é um rascunho. Copiar não envia mensagem, cria proposta, revisa snapshot ou aprova execução.'].join('\n');
}

export function renderTaskPreparation(target, view) {
  const previous = target._studioTaskUI;
  if (previous && view?.session_id && target.contains(previous.objective) && previous.view?.session_id === view.session_id && previous.view?.workspace === view.workspace) {
    previous.view = view; previous.update(); return;
  }
  target.replaceChildren(); heading(target, 'Preparar tarefa');
  paragraph(target, 'Preencha um objetivo pequeno e verificável. Salvar guarda somente o rascunho nas suas preferências, por conversa/projeto. Copiar ou salvar não envia pedido nem aprova tarefa.');
  const kind = document.createElement('select'); kind.setAttribute('aria-label', 'Tipo da tarefa');
  for (const [value, label] of Object.entries(taskKinds)) {
    const option = document.createElement('option'); option.value = value; option.textContent = label; kind.appendChild(option);
  }
  kind.value = 'bug'; target.appendChild(kind);
  const objective = document.createElement('textarea'); objective.setAttribute('aria-label', 'Objetivo verificável'); objective.placeholder = 'O que precisa mudar ou ser investigado?'; objective.rows = 3; target.appendChild(objective);
  objective.maxLength=4000;
  const acceptance = document.createElement('textarea'); acceptance.setAttribute('aria-label', 'Critérios de aceitação'); acceptance.placeholder = 'Qual resultado comprova que a tarefa foi atendida?'; acceptance.rows = 3; target.appendChild(acceptance);
  acceptance.maxLength=8000;
  const preview = document.createElement('pre'); target.appendChild(preview);
  const draft = { view, objective };
  const update = () => { preview.textContent = developmentTaskReport(draft.view, kind.value, objective.value, acceptance.value); };
  draft.update = update; target._studioTaskUI = draft;
  for (const input of [kind, objective, acceptance]) input.oninput = update;
  update();
  const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Copiar rascunho da tarefa';
  const feedback = document.createElement('p'); feedback.setAttribute('role', 'status');
  button.onclick = async () => {
    if (!target.contains(button)) return;
    try { await navigator.clipboard.writeText(developmentTaskReport(draft.view, kind.value, objective.value, acceptance.value)); if (target.contains(button)) feedback.textContent = 'Rascunho copiado. Revise antes de enviar na conversa.'; }
    catch (_) { if (target.contains(button)) feedback.textContent = 'Cópia indisponível. Selecione o texto para copiar.'; }
  };
  target.appendChild(button); target.appendChild(feedback);
  const current=()=>target._studioTaskUI===draft&&target.contains(objective);
  const persistenceButtons=[];
  for(const [label,operation]of[['Salvar rascunho','save'],['Restaurar rascunho salvo','restore'],['Limpar rascunho salvo','clear']]){
    const b=document.createElement('button');b.type='button';b.textContent=label;
    persistenceButtons.push(b);
    b.onclick=async()=>{if(!current()||!draft.view?.session_id||draft.pending)return;
      draft.pending=true;persistenceButtons.forEach(button=>button.disabled=true);
      const captured={format:1,kind:kind.value,objective:objective.value,acceptance:acceptance.value};
      try{const key=await taskDraftKey(draft.view.session_id,draft.view.workspace||'');if(!current())return;
        const loaded=await taskDraftRequest(key,operation==='save'?captured:operation==='clear'?null:undefined);if(!current())return;
        if(operation==='restore'&&loaded){
          if(objective.value!==captured.objective||acceptance.value!==captured.acceptance||kind.value!==captured.kind){feedback.textContent='O rascunho local mudou durante a consulta; restauração não aplicada.';return;}
          kind.value=loaded.kind;objective.value=loaded.objective;acceptance.value=loaded.acceptance;update();
        }
        feedback.textContent=operation==='save'?'Rascunho salvo nas suas preferências; tarefa não enviada.':operation==='clear'?'Rascunho salvo limpo. O texto local foi preservado.':loaded?'Rascunho restaurado.':'Nenhum rascunho válido salvo neste escopo.';
      }catch(_){if(current())feedback.textContent='Não foi possível acessar o rascunho salvo. O texto local foi preservado.';}
      finally{draft.pending=false;if(current())persistenceButtons.forEach(button=>button.disabled=false);}
    };target.appendChild(b);
  }
  const evidence=document.createElement('textarea');evidence.rows=3;evidence.maxLength=8000;evidence.setAttribute('aria-label','Critérios e referências observadas');evidence.placeholder='Para cada critério, anote evento/arquivo/recibo existente ou marque evidência ausente. Não certifica conclusão.';
  target.appendChild(evidence);
  const copyEvidence=document.createElement('button');copyEvidence.type='button';copyEvidence.textContent='Copiar critérios e referências';
  copyEvidence.onclick=async()=>{if(!current())return;try{await navigator.clipboard.writeText(`Critérios: ${acceptance.value}\nReferências consultivas: ${evidence.value}\nProposta observada: ${draft.view?.proposal?.proposal_digest||'não registrada'}\nNão aprova nem comprova objetivo cumprido.`);}catch(_){if(current())feedback.textContent='Cópia indisponível.';}};target.appendChild(copyEvidence);
}

function handoffWorkspace(value) {
  const key = typeof value === 'string' ? value.replaceAll('\\', '/').replace(/\/+$/, '') : '';
  return /^[a-z]:\//i.test(key) || key.startsWith('//') ? key.toLowerCase() : key;
}
function handoffText(value, limit = 4000) {
  return typeof value === 'string' ? value.slice(0, limit) : '';
}
function handoffReference(value, hash = false) {
  return typeof value === 'string' && (hash ? /^[0-9a-f]{64}$/ : /^[A-Za-z0-9_-]{1,128}$/).test(value) ? value : 'não registrada';
}
export function handoffScopedView(view, session, workspace, loading = false) {
  const current=typeof view?.workspace==='string' && view?.session_id===session && handoffWorkspace(view.workspace)===handoffWorkspace(workspace);
  return current ? {...view,validity:loading?'unavailable':view.validity} : {session_id:session,workspace,validity:'unavailable'};
}
export function developmentHandoff(view, history, notes = {}) {
  const key = handoffWorkspace(view?.workspace), fresh = view?.validity === 'valid';
  const work = collectStudioWork(history);
  const scoped = work.filter(item => typeof item.node.dataset.studioToolWorkspace === 'string' && handoffWorkspace(item.node.dataset.studioToolWorkspace) === key);
  const p = view?.proposal;
  const proposalExact=handoffReference(p?.proposal_id)!=='não registrada'&&handoffReference(p?.proposal_digest,true)!=='não registrada'&&handoffReference(p?.authority_snapshot,true)!=='não registrada';
  const rows = ['MOBS Studio — resumo para continuidade (consultivo)',
    'Não concede autorização, retoma execução ou comprova objetivo cumprido. Revalide baseline, autoridades e recursos antes de agir.',
    'Contém notas manuais e referências do projeto. Revise antes de compartilhar. Não extrai conteúdo de arquivos, comandos, saídas ou raciocínio privado; notas digitadas por você serão incluídas.',
    `Conversa: ${JSON.stringify(handoffText(view?.session_id, 256) || 'não registrada')}`,
    `Workspace apresentado: ${JSON.stringify(handoffText(view?.workspace, 1024) || 'não selecionado')}`,
    `Objetivo manual: ${handoffText(notes?.objective) || 'não preenchido'}`,
    `Bloqueios manuais: ${handoffText(notes?.blockers) || 'não preenchidos; não significa ausência de bloqueios'}`,
    `Próxima ação proposta: ${handoffText(notes?.next) || 'não preenchida'}`,
    `Consulta institucional: ${fresh ? 'registrada como válida nesta visão; revalidar antes de agir' : 'não confirmada; referências podem ser históricas'}`,
    `Proposta observada: ${handoffReference(p?.proposal_id)}`,
    `Digest: ${handoffReference(p?.proposal_digest, true)}`,
    `Snapshot: ${handoffReference(p?.authority_snapshot, true)}`,
    `Revisão do snapshot: ${fresh && proposalExact && view?.reviewed === true ? 'informada pelo servidor; não concede execução' : 'não confirmada'}`,
    `Autorização: ${fresh && proposalExact && p?.status === 'approved' ? 'aprovação informada pelo servidor; não é prova de execução' : 'não confirmada nesta visão'}`,
    `Ferramentas no workspace: ${scoped.length} registros, ${scoped.filter(x=>x.status==='running').length} em andamento, ${scoped.filter(x=>x.status==='failed').length} com falha. Retorno recebido não prova objetivo.`,
    `Outros registros da conversa fora deste escopo ou sem workspace: ${work.length-scoped.length}; detalhes omitidos.`];
  const plans = Array.from(history.querySelectorAll('.studio-plan'));
  const planCounts = {total:0,done:0,current:0};
  for (const plan of plans.slice(-20)) {
    if(typeof plan.dataset.signature!=='string'||plan.dataset.signature.length>65536)continue;
    let steps;try{steps=JSON.parse(plan.dataset.signature||'null');}catch(_){continue;}
    if (!Array.isArray(steps)) continue;
    for (const step of steps.slice(0,100)) {
      if (!step || typeof step.text !== 'string') continue;
      planCounts.total++;if(step.done===true)planCounts.done++;if(step.current===true)planCounts.current++;
    }
  }
  rows.push(`Planos da conversa: ${planCounts.done}/${planCounts.total} etapas marcadas pelo agente, ${planCounts.current} atuais (até 20 planos/100 etapas por plano). Sem vínculo comprovado ao workspace nem certificação de execução.`);
  const candidates = Array.isArray(view?.promotions) ? view.promotions : [];
  rows.push(`Candidatos apresentados: ${candidates.length}; até 10 referências abaixo, sem conteúdos/diffs.`);
  for (const candidate of candidates.slice(0,10)) {
    const digest=handoffReference(candidate?.artifact_digest,true);
    const exact=fresh&&candidate?.validity==='valid'&&candidate?.validated===true&&digest!=='não registrada'&&handoffReference(candidate?.id)!=='não registrada';
    rows.push(`- Candidato ${handoffReference(candidate?.id)} / ${digest}: ${exact ? 'validação exata informada pelo servidor; não comprova promoção ou objetivo' : 'validação exata não confirmada'}.`);
  }
  const sources = loadedSources(history).filter(source=>handoffWorkspace(source.workspace)===key);
  const groups = groupSourcePages(sources.slice(-100));
  rows.push(`Fontes do workspace: ${sources.length} trechos; referências das últimas 100 leituras, até 20 grupos. Nenhuma leitura nova.`);
  for (const pages of groups.slice(0,20)) {
    const intervals=sourceCoverage(pages).intervals;
    const ranges=intervals.slice(0,10).map(([a,b])=>`${a}–${b}`).join(', ')||'linhas completas não registradas';
    rows.push(`- ${JSON.stringify(handoffText(pages[0].path,240))}: ${ranges}${intervals.length>10?' (intervalos limitados)':''}; head ${pages[0].head||'não registrado'}; não certifica leitura integral/atualidade.`);
  }
  if(sources.length>100||groups.length>20)rows.push('Lista de referências limitada; consulte os eventos e o painel Fontes carregadas.');
  const report=rows.join('\n');
  return report.length<=32000 ? report : report.slice(0,32000)+'\n[Resumo limitado a 32.000 caracteres; consulte as referências originais.]';
}

export function renderDevelopmentHandoff(target, view, history) {
  let state=target._studioHandoff;
  if(!state || state.session!==view?.session_id || state.workspace!==handoffWorkspace(view?.workspace) || !target.contains(state.preview)) {
    target.replaceChildren();heading(target,'Resumo para continuidade');
    paragraph(target,'Prepare uma passagem manual de trabalho com referências já carregadas. Nada é enviado, autorizado ou retomado. Notas locais, sem salvamento: sair desta visão ou mudar de conversa/projeto descarta o preenchimento.');
    state={session:view?.session_id,workspace:handoffWorkspace(view?.workspace),fields:{}};
    for(const [key,label] of [['objective','Objetivo para continuidade'],['blockers','Bloqueios conhecidos'],['next','Próxima ação proposta']]) {
      const field=document.createElement('textarea');field.rows=2;field.maxLength=4000;field.setAttribute('aria-label',label);field.placeholder=label;
      target.appendChild(field);state.fields[key]=field;
    }
    state.preview=document.createElement('pre');target.appendChild(state.preview);
    state.copy=document.createElement('button');state.copy.type='button';state.copy.textContent='Copiar resumo para continuidade';target.appendChild(state.copy);
    state.feedback=document.createElement('p');state.feedback.setAttribute('role','status');target.appendChild(state.feedback);
    target._studioHandoff=state;
    const current=()=>target._studioHandoff===state&&target.contains(state.preview);
    const update=()=>{if(!current())return;state.preview.textContent=developmentHandoff(state.view,state.history,Object.fromEntries(Object.entries(state.fields).map(([k,f])=>[k,f.value])));};
    state.update=update;for(const field of Object.values(state.fields))field.oninput=update;
    state.copy.onclick=async()=>{if(!current())return;update();try{await navigator.clipboard.writeText(state.preview.textContent);if(current())state.feedback.textContent='Resumo copiado. Revise as referências; nenhuma tarefa foi enviada.';}catch(_){if(current())state.feedback.textContent='Cópia indisponível. O texto continua no painel.';}};
  }
  state.view=view;state.history=history;state.update();
}
