// Presentation of existing timing and tool events; never synthesize work claims.
export function toolResultPresentation(event) {
  if (event?.exit_code === 0) return { failed: false, icon: '✓', label: 'retorno sem erro' };
  if (typeof event?.exit_code === 'number' && Number.isFinite(event.exit_code)) return { failed: true, icon: '✗', label: 'com falha' };
  return { failed: false, icon: '·', label: 'retorno recebido' };
}

export function recordStudioDiagnostics(message, metrics) {
  if (!message?.dataset || !metrics) return;
  let previous = {};
  try { previous = JSON.parse(message.dataset.studioDiagnostics || '{}'); } catch (_) {}
  const data = { ...previous };
  for (const key of ['response_time', 'time_to_first_token', 'request_context_tokens', 'context_length', 'agent_prep_time']) {
    if (typeof metrics[key] === 'number' && Number.isFinite(metrics[key]) && metrics[key] >= 0) data[key] = metrics[key];
  }
  if (metrics.agent_prep_breakdown && typeof metrics.agent_prep_breakdown === 'object') {
    data.preparation = Object.fromEntries(Object.entries(metrics.agent_prep_breakdown).filter(([, value]) => typeof value === 'number' && Number.isFinite(value) && value >= 0).slice(0, 16));
  }
  for (const key of ['initial_context_profile', 'last_round_context_profile']) {
    const profile = metrics[key]; if (!profile || profile.estimate_only !== true) continue;
    const safe = { estimate_only: true, categories: {} };
    for (const name of ['messages', 'message_tokens_estimated', 'duplicate_system_messages', 'duplicate_system_tokens_estimated', 'duplicate_protected_messages', 'tool_schema_count', 'tool_schema_tokens_estimated']) {
      if (Number.isFinite(profile[name]) && profile[name] >= 0) safe[name] = profile[name];
    }
    for (const [name, value] of Object.entries(profile.categories || {}).slice(0, 16)) {
      if (Number.isFinite(value?.estimated_tokens) && value.estimated_tokens >= 0) safe.categories[name] = { estimated_tokens: value.estimated_tokens, messages: Number.isFinite(value.messages) ? value.messages : 0 };
    }
    safe.tool_schema_groups = {};
    for (const name of ['navigation', 'editing', 'execution', 'coordination', 'other']) {
      const value = profile.tool_schema_groups?.[name];
      if (Number.isFinite(value?.count) && value.count >= 0 && Number.isFinite(value.estimated_tokens) && value.estimated_tokens >= 0)
        safe.tool_schema_groups[name] = { count: value.count, estimated_tokens: value.estimated_tokens };
    }
    data[key] = safe;
  }
  if (Object.keys(data).length) message.dataset.studioDiagnostics = JSON.stringify(data);
}

export function renderStudioDiagnostics(target, history) {
  const messages = Array.from(history.querySelectorAll('.msg-ai')).filter(message => message.dataset.studioDiagnostics);
  const work = collectStudioWork(history);
  const last = messages.at(-1), signature = JSON.stringify([last?.dataset.studioDiagnostics || 'missing', work.map(item => [item.tool, item.file, item.status])]);
  if (target._studioDiagnosticSignature === signature && target._studioDiagnosticMessage === last) return;
  target._studioDiagnosticSignature = signature; target._studioDiagnosticMessage = last;
  const heading = document.createElement('h3'); heading.textContent = 'Recursos e contexto';
  const note = document.createElement('p'); note.textContent = 'Última resposta com medidas disponíveis nesta conversa. Estimativas não são contagem do tokenizer nem comprovam a janela realmente carregada no Ollama.';
  const content = document.createElement('div'); content.className = 'studio-diagnostics';
  let data; try { data = JSON.parse(last?.dataset.studioDiagnostics || 'null'); } catch (_) {}
  if (!data || typeof data !== 'object') content.textContent = 'Sem medidas registradas. Novas respostas poderão trazer composição e tempos; nenhuma inferência é iniciada por esta consulta.';
  else {
    const row = (label, value) => { const p = document.createElement('p'); p.textContent = `${label}: ${value}`; content.appendChild(p); };
    for (const [key, label, unit] of [['response_time', 'Tempo da rodada', 's'], ['time_to_first_token', 'Primeiro token', 's'], ['agent_prep_time', 'Preparação', 's'], ['request_context_tokens', 'Contexto estimado da rodada', 'tokens'], ['context_length', 'Janela informada pelo runtime', 'tokens']]) {
      if (typeof data[key] === 'number') row(label, `${data[key]} ${unit}`);
    }
    const stages = { request_setup: 'Preparação do pedido', tool_selection: 'Seleção de ferramentas', prompt_build: 'Composição do contexto', context_trim: 'Ajuste ao orçamento' };
    for (const [key, value] of Object.entries(data.preparation || {})) row(stages[key] || key, `${value} s`);
    const labels = { persona: 'Persona', tool_protocol: 'Protocolo de ferramentas', action_instruction: 'Instrução da ação', protected_context: 'Contexto protegido', system: 'Sistema', user: 'Mensagens do usuário', assistant: 'Histórico do agente', tool: 'Retornos de ferramentas', other: 'Outros' };
    const profile = data.initial_context_profile;
    if (profile) {
      const title = document.createElement('h4'); title.textContent = 'Composição inicial estimada'; content.appendChild(title);
      const categories = Object.entries(profile.categories || {}).sort((a, b) => b[1].estimated_tokens - a[1].estimated_tokens);
      const total = categories.reduce((sum, [, value]) => sum + value.estimated_tokens, 0);
      for (const [key, value] of categories) row(labels[key] || 'Outros', `${value.estimated_tokens} tokens · ${value.messages} mensagens · ${total ? Math.round(value.estimated_tokens * 100 / total) : 0}% da composição estimada`);
      row('Mensagens de sistema repetidas literalmente', profile.duplicate_system_messages || 0);
      if (typeof profile.duplicate_system_tokens_estimated === 'number') row('Custo estimado das repetições', `${profile.duplicate_system_tokens_estimated} tokens`);
      if (typeof profile.duplicate_protected_messages === 'number') row('Repetições que são mensagens protegidas', profile.duplicate_protected_messages);
      if (profile.duplicate_system_messages) row('Revisão das repetições', 'Verifique origem e obrigatoriedade antes de propor mudanças. Nenhuma deduplicação automática ou remoção de autoridade foi autorizada.');
      const schemas = data.last_round_context_profile || profile;
      row('Schemas na última chamada observada', `${schemas.tool_schema_count || 0} · ~${schemas.tool_schema_tokens_estimated || 0} tokens`);
      const toolFamilies = {navigation:'Navegação de código',editing:'Edição',execution:'Execução',coordination:'Coordenação',other:'Outras ferramentas'};
      for (const [family, value] of Object.entries(schemas.tool_schema_groups || {})) row(toolFamilies[family] || 'Outras ferramentas', `${value.count} schemas · ~${value.estimated_tokens} tokens`);
      row('Auditoria de seleção', 'Peso por família não demonstra irrelevância. Compare tarefa, ferramentas admitidas e chamadas efetivas antes de reduzir schemas; nenhuma autoridade foi removida.');
      const last = data.last_round_context_profile;
      if (last && Number.isFinite(last.message_tokens_estimated) && Number.isFinite(profile.message_tokens_estimated)) {
        const change = last.message_tokens_estimated - profile.message_tokens_estimated;
        row('Variação estimada de mensagens até a última rodada', `${change > 0 ? '+' : ''}${change} tokens`);
        const keys = new Set([...Object.keys(profile.categories || {}), ...Object.keys(last.categories || {})]);
        for (const key of keys) {
          const delta = (last.categories?.[key]?.estimated_tokens || 0) - (profile.categories?.[key]?.estimated_tokens || 0);
          if (delta) row(`Variação · ${labels[key] || 'Outros'}`, `${delta > 0 ? '+' : ''}${delta} tokens`);
        }
        row('Interpretação da variação', 'Compara observações de rodadas diferentes, incluindo novas mensagens e retornos. Não mede desperdício nem autoriza remover contexto obrigatório.');
      }
      row('Limite da estimativa', 'Schemas contabilizados separadamente; custo de imagens não incluído. Nenhum conteúdo obrigatório foi removido por este diagnóstico.');
    } else row('Composição detalhada', 'Não registrada nesta resposta. Dados antigos não são reconstruídos por suposição.');
  }
  const execution = document.createElement('section');
  const executionTitle = document.createElement('h4'); executionTitle.textContent = 'Evidência de ferramentas na conversa carregada'; execution.appendChild(executionTitle);
  const summary = document.createElement('p');
  summary.textContent = work.length ? `${work.length} registros · ${work.filter(item => item.status === 'running').length} em andamento · ${work.filter(item => item.status === 'failed').length} com falha. Retorno recebido não comprova o objetivo cumprido.` : 'Nenhum registro de ferramenta carregado. Uma promessa textual não comprova chamada, despacho ou execução.';
  execution.appendChild(summary);
  const provenance = document.createElement('p');
  provenance.textContent = 'Origem: registros carregados desta conversa. Chamada nativa, autorização e despacho não são certificados por este resumo. Para conferi-los, confronte a proposta e os eventos/recibos originais; validação exata fica em Revisão da tarefa.';
  execution.appendChild(provenance);
  const failureGuide = document.createElement('details');
  const guideTitle = document.createElement('summary'); guideTitle.textContent = 'Como distinguir uma falha'; failureGuide.appendChild(guideTitle);
  for (const text of [
    'Provedor ou transporte: confira o evento de erro e o status original. Um timeout não demonstra falta de memória.',
    'Formato da chamada: confira o parser e a chamada nativa; uma ferramenta anunciada no texto pode nem ter sido emitida.',
    'Autorização: confira a negação registrada pelo servidor e o escopo aprovado. Revisão de snapshot não concede execução.',
    'Execução: confira despacho, retorno e recibo do processo. Um código de saída isolado não distingue todas as causas e não comprova o objetivo.'
  ]) { const p = document.createElement('p'); p.textContent = text; failureGuide.appendChild(p); }
  execution.appendChild(failureGuide);
  const failure = work.filter(item => item.status === 'failed').at(-1);
  if (failure) { const p = document.createElement('p'); p.textContent = `Último registro com falha: ${failure.tool}${failure.file ? ` · ${failure.file}` : ''}. Consulte o evento original em Atividade e arquivos para distinguir formato, autorização, execução ou timeout; este resumo não determina a causa.`; execution.appendChild(p); }
  content.appendChild(execution);
  target.replaceChildren(heading, note, content);
}

export function planFromToolEvent(event) {
  if (event?.tool !== 'update_plan' || event.exit_code !== 0 || typeof event.command !== 'string') return '';
  let plan = event.command;
  try { const parsed = JSON.parse(plan); if (parsed && typeof parsed.plan === 'string') plan = parsed.plan; } catch (_) {}
  return plan.slice(0, 8192);
}

export function collectStudioWork(history) {
  return Array.from(history.querySelectorAll('.agent-thread-node'))
    .filter(node => !node.closest('.agent-thread')?.dataset.docWriting)
    .map(node => ({ node, tool: node.querySelector('.agent-thread-tool')?.textContent || 'Ferramenta',
      file: node.dataset.studioDiffFile || '', status: node.classList.contains('running') ? 'running' : node.classList.contains('error') ? 'failed' : 'returned' }));
}
const workLabels = { running: 'em andamento', failed: 'com falha', returned: 'retorno recebido' };
export function studioWorkReport(items, session = '') {
  return ['MOBS Studio — acompanhamento da conversa', `Conversa: ${session || 'não identificada'}`,
    'Registro de ferramentas; não comprova objetivo cumprido ou aplicação no projeto principal.',
    'Saídas brutas e raciocínio privado não estão incluídos.', '',
    ...items.map((item, index) => `${index + 1}. ${item.tool} · ${workLabels[item.status]}${item.file ? ` · ${item.file}` : ''}`)].join('\n');
}
function revealWorkNode(node, history) {
  if (!history.contains(node)) return;
  const group = node.closest('.studio-tool-group'); if (group) group.open = true;
  node.classList.add('open'); node.tabIndex = -1; node.focus({ preventScroll: true }); node.scrollIntoView({ block: 'nearest' });
}
export function renderStudioWorkSummary(target, history, session = '') {
  let state = target._studioWorkUI;
  if (!state || state.session !== session || state.heading.parentNode !== target) {
    const heading = document.createElement('h3'); heading.textContent = 'Atividade e arquivos';
    const note = document.createElement('p'); note.textContent = 'Registros de ferramentas desta conversa. Um retorno recebido não comprova o objetivo cumprido nem a aplicação no projeto principal.';
    const list = document.createElement('div'); list.className = 'studio-file-index';
    const toolbar = document.createElement('div'); toolbar.className = 'studio-work-toolbar';
    const search = document.createElement('input'); search.type = 'search'; search.placeholder = 'Buscar ferramenta ou arquivo'; search.setAttribute('aria-label', search.placeholder);
    const filter = document.createElement('select'); filter.setAttribute('aria-label', 'Filtrar atividade');
    for (const [value, label] of [['all', 'Toda atividade'], ['running', 'Em andamento'], ['failed', 'Com falha'], ['files', 'Com diff de arquivo']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = label; filter.appendChild(option);
    }
    filter.value = 'all';
    const copy = document.createElement('button'); copy.type = 'button'; copy.textContent = 'Copiar acompanhamento';
    const feedback = document.createElement('p'); feedback.setAttribute('role', 'status');
    const count = document.createElement('p'); count.setAttribute('role', 'status');
    const files = document.createElement('details'); files.className = 'studio-file-index';
    for (const control of [search, filter, copy]) toolbar.appendChild(control);
    target.replaceChildren(heading, note, toolbar, count, files, list, feedback);
    state = { session, heading, list, search, filter, count, files, feedback, items: [], signature: null };
    target._studioWorkUI = state;
    search.oninput = filter.onchange = () => { state.signature = null; renderStudioWorkSummary(target, history, session); };
    copy.onclick = async () => {
      if (target._studioWorkUI !== state || heading.parentNode !== target) return;
      try { await navigator.clipboard.writeText(studioWorkReport(collectStudioWork(history), session)); feedback.textContent = 'Acompanhamento copiado.'; }
      catch (_) { feedback.textContent = 'Cópia indisponível neste ambiente. Os registros continuam acessíveis abaixo.'; }
    };
  }
  const items = collectStudioWork(history);
  const signature = JSON.stringify([state.search.value, state.filter.value, items.map(({ tool, file, status }) => [tool, file, status])]);
  if (state.signature === signature && state.items.length === items.length && state.items.every((item, i) => item.node === items[i].node)) return;
  const focusedWork = state.buttons?.find(entry => entry.button === document.activeElement)?.node;
  state.signature = signature; state.items = items;
  const query = String(state.search.value || '').trim().toLocaleLowerCase();
  const visible = items.filter(item => (!query || `${item.tool} ${item.file}`.toLocaleLowerCase().includes(query)) &&
    (state.filter.value === 'all' || state.filter.value === item.status || state.filter.value === 'files' && item.file));
  state.list.replaceChildren();
  state.buttons = [];
  if (!items.length) state.list.textContent = 'Nenhuma atividade de ferramenta registrada nesta conversa.';
  else if (!visible.length) state.list.textContent = 'Nenhum registro corresponde à busca e ao filtro.';
  else state.list.textContent = '';
  for (const item of visible) {
    const button = document.createElement('button'); button.type = 'button';
    button.textContent = `${item.tool} · ${workLabels[item.status]}${item.file ? ` · ${item.file}` : ''}`;
    button.onclick = () => revealWorkNode(item.node, history); state.list.appendChild(button);
    state.buttons.push({ button, node: item.node });
  }
  const grouped = new Map();
  for (const item of items.filter(item => item.file)) { const group = grouped.get(item.file) || []; group.push(item); grouped.set(item.file, group); }
  state.count.textContent = `${visible.length}/${items.length} registros · ${items.filter(item => item.status === 'running').length} em andamento · ${items.filter(item => item.status === 'failed').length} com falha · ${grouped.size} arquivos com diff`;
  state.files.replaceChildren();
  state.files.hidden = !grouped.size;
  if (grouped.size) {
    const title = document.createElement('summary'); title.textContent = `Arquivos com revisões recebidas · ${grouped.size}`; state.files.appendChild(title);
    for (const [file, revisions] of grouped) {
      if (query && !file.toLocaleLowerCase().includes(query)) continue;
      const button = document.createElement('button'); button.type = 'button'; button.textContent = `${file} · ${revisions.length} revisão(ões)`;
      button.onclick = () => revealWorkNode(revisions.at(-1).node, history); state.files.appendChild(button);
    }
  }
  if (focusedWork) {
    const replacement = state.buttons.find(entry => entry.node === focusedWork)?.button;
    (replacement || state.search).focus({ preventScroll: true });
  }
}

export function parseStudioPlan(text) {
  const steps = []; let fence = null;
  for (const line of String(text || '').split('\n')) {
    const marker = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (marker) { if (!fence) fence = marker[1]; else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = null; continue; }
    if (fence) continue;
    const match = line.match(/^\s*(?:[-*]|\d+\.)\s+\[([ x-])\]\s+(.+)$/i);
    if (match) steps.push({ done: match[1].toLowerCase() === 'x', current: match[1] === '-', text: match[2] });
  }
  return steps;
}

export function renderStudioPlanIndex(target, history) {
  const plans = Array.from(history.querySelectorAll('.studio-plan'));
  const work = collectStudioWork(history);
  const signature = JSON.stringify(plans.map(plan => plan.dataset.signature));
  const evidenceText = work.length ? `${work.length} registros de ferramentas nesta conversa · ${work.filter(item => item.status === 'running').length} em andamento · ${work.filter(item => item.status === 'failed').length} com falha. Confira em Atividade e arquivos; não há vínculo automático entre cada etapa e esses registros.` : 'Sem registros de ferramentas nesta conversa. Etapas marcadas como concluídas pelo agente ainda não têm evidência de ferramenta registrada aqui.';
  if (target._studioPlanSignature === signature && target._studioPlanNodes?.length === plans.length &&
      target._studioPlanNodes.every((node, index) => node === plans[index]) && target._studioPlanEvidence?.parentNode === target) {
    target._studioPlanEvidence.textContent = evidenceText; return;
  }
  target._studioPlanSignature = signature; target._studioPlanNodes = plans;
  const heading = document.createElement('h3'); heading.textContent = 'Planos e atualizações';
  const note = document.createElement('p'); note.textContent = 'Checklists informados pelo agente na conversa carregada. Marcações não comprovam execução, validação ou aplicação.';
  const evidence = document.createElement('p');
  evidence.textContent = evidenceText; target._studioPlanEvidence = evidence;
  const list = document.createElement('div'); list.className = 'studio-file-index';
  if (!plans.length) list.textContent = 'Nenhum checklist registrado nesta conversa. Solicite um planejamento para começar.';
  for (const [index, plan] of plans.entries()) {
    const section = document.createElement('details');
    const summary = document.createElement('summary'); summary.textContent = `Registro ${index + 1} · ${plan.querySelector('summary')?.textContent || 'Plano'}`;
    const contents = document.createElement('pre'); contents.textContent = Array.from(plan.querySelector('ul')?.children || []).map(item => item.textContent).join('\n');
    const jump = document.createElement('button'); jump.type = 'button'; jump.textContent = 'Ver na conversa';
    jump.onclick = () => { if (!history.contains(plan)) return; plan.open = true; plan.tabIndex = -1; plan.focus({ preventScroll: true }); plan.scrollIntoView({ block: 'nearest' }); };
    for (const node of [summary, contents, jump]) section.appendChild(node); list.appendChild(section);
  }
  target.replaceChildren(heading, note, evidence, list);
}

export function renderStudioPlan(target, text) {
  if (!target || !document.body.classList.contains('studio-shell')) return;
  const steps = parseStudioPlan(text);
  let panel = target.querySelector(':scope > .studio-plan');
  if (!steps.length) { panel?.remove(); return; }
  if (!panel) { panel = document.createElement('details'); panel.className = 'studio-plan'; target.appendChild(panel); }
  const signature = JSON.stringify(steps);
  if (panel.dataset.signature === signature) return;
  panel.dataset.signature = signature;
  const summary = document.createElement('summary');
  summary.textContent = `Plano informado pelo agente · ${steps.filter(step => step.done).length}/${steps.length}`;
  const note = document.createElement('p');
  note.textContent = 'Checklist de acompanhamento. Não concede autorização nem comprova execução ou aplicação de arquivos.';
  const list = document.createElement('ul');
  for (const step of steps) {
    const item = document.createElement('li'); item.textContent = `${step.done ? '✓' : step.current ? '→' : '○'} ${step.text}`;
    if (step.current) item.setAttribute('aria-current', 'step'); list.appendChild(item);
  }
  panel.replaceChildren(summary, note, list);
}

function refreshFileIndex(group, content) {
  const nodes = Array.from(content.children).filter(node => node.dataset.studioDiffFile && node.querySelector('.agent-tool-diff'));
  let index = group.querySelector(':scope > .studio-file-index');
  if (!nodes.length) return;
  const signature = JSON.stringify(nodes.map(node => [node.dataset.studioDiffFile, node.classList.contains('error')]));
  if (index?.dataset.signature === signature) return;
  if (!index) { index = document.createElement('nav'); index.className = 'studio-file-index'; index.setAttribute('aria-label', 'Arquivos com diff recebido'); group.appendChild(index); }
  index.dataset.signature = signature;
  const label = document.createElement('p'); label.textContent = 'Diffs recebidos · aplicação no projeto depende do fluxo de promoção';
  index.replaceChildren(label);
  for (const node of nodes) {
    const button = document.createElement('button'); button.type = 'button';
    button.textContent = `${node.dataset.studioDiffFile}${node.classList.contains('error') ? ' · ferramenta com falha' : ''}`;
    button.onclick = () => {
      group.open = true; node.classList.add('open');
      const diff = node.querySelector('.agent-tool-diff'); diff.open = true;
      diff.tabIndex = -1; diff.focus({ preventScroll: true }); diff.scrollIntoView({ block: 'nearest' });
    };
    index.appendChild(button);
  }
}

export function formatElapsed(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  return value < 60 ? `${value} s` : `${Math.floor(value / 60)} min ${value % 60} s`;
}

export function refreshStudioActivity(history, now = Date.now(), streamActive = true) {
  for (const msg of history.querySelectorAll('.msg-ai')) {
    const streaming = streamActive && msg.classList.contains('streaming');
    if (streaming && !msg.dataset.studioStartedAt) msg.dataset.studioStartedAt = String(now);
    const measured = Number(msg.dataset.studioResponseSeconds);
    const hasMeasured = msg.dataset.studioResponseSeconds !== undefined && Number.isFinite(measured);
    if (!streaming && !hasMeasured && !msg.dataset.studioStartedAt) continue;
    // The preparation row already has its own timer. Avoid two wait indicators.
    if (msg.querySelector('.ai-spinner, .live-think-header-text')) continue;
    const body = msg.querySelector(':scope > .body');
    if (!body) continue;
    let line = msg.querySelector(':scope > .studio-response-time');
    if (!line) {
      line = document.createElement('div'); line.className = 'studio-response-time';
      body.before(line);
    }
    if (!streaming && !msg.dataset.studioEndedAt) msg.dataset.studioEndedAt = String(now);
    const seconds = hasMeasured ? measured : ((streaming ? now : Number(msg.dataset.studioEndedAt)) - Number(msg.dataset.studioStartedAt)) / 1000;
    const text = !streaming && hasMeasured ? `Trabalhou por ${formatElapsed(seconds)}` :
      `${streaming ? 'Em andamento' : 'Tempo observado'} · ${formatElapsed(seconds)}`;
    if (line.textContent !== text) line.textContent = text;
  }
  for (const thread of history.querySelectorAll('.agent-thread')) {
    // A document preview being streamed is not proof of a tool execution.
    if (thread.dataset.docWriting) continue;
    const direct = Array.from(thread.children).filter(node => node.classList.contains('agent-thread-node'));
    let group = thread.querySelector(':scope > .studio-tool-group');
    if (!group && direct.length) {
      group = document.createElement('details'); group.className = 'studio-tool-group';
      const summary = document.createElement('summary');
      const content = document.createElement('div'); content.className = 'studio-tool-group-content';
      group.append(summary, content); thread.insertBefore(group, direct[0]);
    }
    if (!group) continue;
    const content = group.querySelector('.studio-tool-group-content');
    for (const node of direct) content.appendChild(node);
    const nodes = Array.from(content.children);
    const running = nodes.some(node => node.classList.contains('running'));
    const failed = nodes.some(node => node.classList.contains('error'));
    const label = `${running ? 'Ferramentas em andamento' : 'Atividade de ferramentas'} · ${nodes.length}${failed ? ' · com falha' : ''}`;
    const summary = group.querySelector('summary');
    if (summary.textContent !== label) summary.textContent = label;
    refreshFileIndex(group, content);
  }
}
