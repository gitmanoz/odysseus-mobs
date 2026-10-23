// Observational views; draft persistence uses existing owner-scoped preferences.
import { taskDraftKey, taskDraftRequest } from './studioDrafts.js';
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
    'Comece pelo PROJECT_INDEX.md e siga a Decision Tree aplicável.',
    'Revalide baseline, escopo e autoridades; esta referência pode ser histórica.',
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
