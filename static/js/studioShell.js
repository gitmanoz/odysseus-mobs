// Consumer presentation only. Institutional decisions remain in the backend.
import { initMessageNavigation } from './studioMessageNavigation.js';
import { foldLongCode } from './studioCodeDisclosure.js';
import { studioColumns } from './studioColumns.js';
import { refreshStudioActivity, renderStudioWorkSummary, renderStudioPlanIndex, renderStudioDiagnostics } from './studioActivity.js';
import { sealedArtifactPreview } from './studioArtifactPreview.js';
import { renderSources } from './studioSources.js';
import { renderProjectScope, renderEngineeringReview, renderTaskPreparation } from './studioEngineering.js';
export function initStudioShell({ chat, sessions, workspace, storage, ui }) {
  if (!document.getElementById('studio-home')) {
    // An older navigation document may be returned once by the existing SW.
    // Preserve the legacy shell; never reload a draft or run automatically.
    const warning = document.createElement('p');
    warning.setAttribute('role', 'alert');
    warning.textContent = 'Interface atualizada disponível. Recarregue quando terminar a interação atual.';
    document.getElementById('chat-history').before(warning);
    return null;
  }
  document.body.classList.add('studio-shell');
  const el = id => document.getElementById(id);
  const session = () => sessions.getCurrentSessionId();
  let view = null, loading = false, epoch = 0, selected = 'proposal', pinned = false, expanded = false;
  let returnFocus = null, prepared = null, timer = null, liveBusy = false;
  let boundSession = session();
  let historyState = sessions.isSessionLoading?.() ? 'loading' : 'ready';
  const historyAvailable = () => historyState === 'ready' && !sessions.isSessionLoading?.();
  let inspectedMessage = null, responseSignature = null, panelSignature = null, optionSignature = null;
  let previewControl = null, previewAbort = null, stateFlight = null, queuedStateRefresh = false, disposed = false;
  const seen = new Set();
  const labels = { review: 'Confirmar revisão do snapshot', approve: 'Aprovar mandato e iniciar tarefa',
    cancel: 'Cancelar proposta', promote: 'Aprovar promoção exata', validate_promotion: 'Validar artifact exato',
    propose: 'Preparar proposta' };
  const panel = document.createElement('aside');
  panel.id = 'studio-context';
  panel.hidden = true;
  panel.setAttribute('aria-label', 'Contexto da sessão');
  panel.innerHTML = `<header><h2>Contexto</h2><button id="studio-expand" type="button" aria-pressed="false">Expandir</button><button id="studio-pin" type="button" aria-pressed="false">Fixar</button><button id="studio-close" type="button" aria-label="Fechar contexto">×</button></header>
    <label for="studio-selection">Conteúdo</label><select id="studio-selection"></select>
    <p id="studio-validity" role="status"></p><div id="studio-detail"></div><div id="studio-controls"></div>`;
  document.body.appendChild(panel);
  const bar = document.createElement('div');
  bar.className = 'studio-statusbar';
  bar.innerHTML = `<div class="studio-heading"><h2 id="studio-title">Nova conversa</h2><span id="studio-workspace-label"></span></div>
    <span id="studio-pending" role="status"></span>
    <div id="studio-header-actions" class="studio-header-actions">
      <button id="studio-context-open" class="studio-header-icon" type="button" aria-label="Contexto da conversa" title="Contexto da conversa" aria-controls="studio-context" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/></svg></button>
      <button id="studio-refresh" class="studio-header-icon" type="button" aria-label="Atualizar estado" title="Atualizar estado — somente consulta"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 7a7 7 0 0 1 11.6-1L20 9M4 15l2.3 3A7 7 0 0 0 17.9 17"/></svg></button>
    <details id="studio-view-options" class="studio-view-options"><summary aria-label="Opções da conversa" title="Opções da conversa">⋯</summary>
      <div class="studio-view-options-menu"><p id="studio-status-description">Pronto para conversar. Permissões e execuções dependem de autorização.</p>
      <label class="studio-tips"><input id="studio-tips" type="checkbox" checked> Dicas de uso</label></div>
    </details></div>`;
  const history = el('chat-history');
  initMessageNavigation({ history, container: history.parentNode, getSession: session, isLoading: () => !!sessions.isSessionLoading?.(), jumpToMessage: message => ui?.scrollHistoryToMessage(message) });
  history.parentNode.insertBefore(bar, history);
  const activity = el('product-agent-activity');
  if (activity) {
    const actions = el('studio-header-actions'); actions.insertBefore(activity, actions.firstChild);
    activity.setAttribute('role', 'button'); activity.tabIndex = 0;
    activity.title = ['ready', 'idle'].includes(activity.dataset.state) ?
      'Pronto para conversar. Permissões e execuções dependem de autorização.' :
      el('product-agent-activity-label')?.textContent || 'Estado da resposta';
    activity.setAttribute('aria-label', activity.title);
    const showStatus = () => {
      const options = el('studio-view-options'); options.open = !options.open;
      if (options.open) options.querySelector('summary')?.focus();
    };
    activity.onclick = showStatus;
    activity.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showStatus(); } };
  }
  const action = document.createElement('div');
  action.id = 'studio-prepared';
  action.hidden = true;
  action.innerHTML = '<span id="studio-prepared-label" role="status"></span><button id="studio-discard" type="button">Descartar preparação</button>';
  const composer = el('message');
  composer.placeholder = 'Descreva a tarefa…';
  composer.parentNode.insertBefore(action, composer);
  const persona = document.createElement('button');
  persona.type = 'button'; persona.id = 'studio-persona'; persona.className = 'input-icon-btn product-workspace-btn';
  persona.textContent = 'Persona'; persona.title = 'Persona é distinta do modelo e das permissões';
  persona.onclick = () => {
    el('overflow-preset-btn').click();
    document.querySelector('.preset-tab[data-chartab="character"]')?.click();
  };
  el('product-workspace-btn').after(persona);
  // Recompose the existing composer; one control per concept, no duplicate
  // model/persona toolbar. Handlers and IDs remain owned by their modules.
  const model = el('model-picker-wrap');
  if (model) persona.after(model);
  const more = el('overflow-plus-btn');
  const right = document.querySelector('.chat-input-right');
  if (more && right) right.prepend(more);
  // Reuse the existing picker and its listener; the paperclip is a direct
  // attachment action, while the chevron continues to expose other tools.
  const attachment = el('overflow-attach-btn');
  if (attachment && right) {
    attachment.title = 'Anexar arquivos';
    attachment.setAttribute('aria-label', 'Anexar arquivos');
    right.insertBefore(attachment, right.querySelector('.send-btn'));
  }
  const sidebarInner = document.querySelector('.sidebar-inner');
  const sidebarHeader = document.querySelector('.sidebar-header');
  if (sidebarHeader) {
    const heading = document.createElement('span');
    heading.className = 'studio-project-heading';
    heading.textContent = 'Conversas';
    const collapse = document.createElement('button');
    collapse.type = 'button'; collapse.id = 'studio-list-collapse';
    collapse.setAttribute('aria-label', 'Recolher lista de projetos e conversas');
    collapse.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m11 6-6 6 6 6m7-12-6 6 6 6"/></svg>';
    collapse.onclick = () => el('studio-conversations').click();
    sidebarHeader.appendChild(heading);
    sidebarHeader.appendChild(collapse);
    const options = document.createElement('details');
    options.className = 'studio-navigation-options';
    const summary = document.createElement('summary');
    summary.textContent = '⋯';
    summary.setAttribute('aria-label', 'Opções da lateral');
    summary.title = 'Opções da lateral';
    options.appendChild(summary);
    const menu = document.createElement('div');
    menu.className = 'studio-navigation-menu';
    for (const [id, label] of [['studio-capabilities', 'Capacidades'], ['studio-help', 'Orientação'], ['product-advanced-btn', null]]) {
      const button = el(id);
      if (!button) continue;
      if (label) button.textContent = label;
      menu.appendChild(button);
    }
    options.appendChild(menu);
    menu.addEventListener('click', () => { options.open = false; });
    sidebarHeader.appendChild(options);
  }
  // Move the existing avatar, preserving its authenticated identity updates.
  // The existing profile handler remains the only owner of account actions.
  const avatar = el('user-bar-avatar');
  const rail = el('icon-rail');
  if (avatar && rail) {
    const profile = document.createElement('button');
    profile.type = 'button'; profile.id = 'studio-profile';
    profile.className = 'icon-rail-btn';
    profile.setAttribute('aria-label', 'Abrir perfil da conta');
    profile.title = 'Perfil da conta';
    profile.appendChild(avatar);
    profile.onclick = () => el('user-bar-profile').click();
    rail.appendChild(profile);
  }
  let projectEntry, projectName;
  if (sidebarInner) {
    projectEntry = document.createElement('button');
    projectEntry.type = 'button'; projectEntry.id = 'studio-project-entry';
    projectEntry.className = 'list-item studio-project-entry';
    projectName = document.createElement('span');
    projectName.className = 'studio-project-name';
    projectEntry.appendChild(projectName);
    projectEntry.onclick = () => workspace.openWorkspaceBrowser();
    sidebarInner.insertBefore(projectEntry, sidebarInner.firstChild);
  }

  function syncPanelMode() {
    const container = el('chat-container');
    const bounds = container.getBoundingClientRect?.() || { left: 0, width: window.innerWidth };
    const columns = studioColumns(bounds.width, !panel.hidden);
    container.style.setProperty?.('--studio-reading-width', `${columns.reading}px`);
    container.style.setProperty?.('--studio-reading-left', `${columns.left}px`);
    container.style.setProperty?.('--studio-reading-right', `${columns.right}px`);
    panel.style.setProperty?.('--studio-panel-right', `${Math.max(12, window.innerWidth - bounds.left - columns.panelLeft - columns.panel)}px`);
    panel.style.setProperty?.('--studio-panel-width', `${columns.panel}px`);
    panel.classList.toggle('studio-context-modal', !columns.hasLane);
    const modal = !panel.hidden && (expanded || !columns.hasLane);
    container.inert = modal;
    for (const node of document.querySelectorAll('#sidebar, #icon-rail')) node.inert = modal;
    if (!panel.hidden) panel.setAttribute('role', 'dialog');
    if (modal) panel.setAttribute('aria-modal', 'true');
    else panel.removeAttribute('aria-modal');
    const bottom = bar.getBoundingClientRect?.().bottom ?? 64;
    const top = Math.min(bottom + 16, Math.max(12, (window.innerHeight || 800) - 160));
    panel.style.setProperty?.('--studio-context-top', `${Math.max(12, top)}px`);
  }
  function open(focus = true) {
    if (focus) returnFocus = document.activeElement;
    panel.hidden = false;
    document.body.classList.add('studio-context-open');
    el('studio-context-open').setAttribute('aria-expanded', 'true');
    syncPanelMode();
    if (focus) el('studio-close').focus();
  }
  function close(restoreFocus = true) {
    previewAbort?.abort(); previewAbort = null;
    panel.hidden = true;
    document.body.classList.remove('studio-context-open');
    el('studio-context-open').setAttribute('aria-expanded', 'false');
    panel.removeAttribute('role');
    panel.removeAttribute('aria-modal');
    expanded = false;
    panel.classList.remove('studio-context-expanded');
    el('studio-expand').setAttribute('aria-pressed', 'false');
    el('studio-expand').textContent = 'Expandir';
    syncPanelMode();
    if (restoreFocus && returnFocus?.isConnected) returnFocus.focus();
  }
  function busy() {
    return loading || liveBusy || view?.active || view?.proposal?.status === 'approved' ||
      document.querySelector('.send-btn.send-pending');
  }
  function notice(text) {
    const node = el('studio-pending');
    if (node.firstChild?.textContent !== text || !node.firstChild) node.textContent = text;
  }
  function controls(items, reference) {
    const area = el('studio-controls');
    area.replaceChildren();
    for (const type of items) {
      const b = document.createElement('button');
      const preauthorized = reference.promotionId && view?.promotions.find(p => p.id === reference.promotionId)?.status === 'promotion_preauthorized';
      b.type = 'button'; b.textContent = type === 'validate_promotion' && preauthorized ? 'Validar e promover pela política ativa' : labels[type];
      b.dataset.priority = type === 'cancel' ? 'secondary' : 'primary';
      b.disabled = loading || liveBusy || !!view?.active;
      b.addEventListener('click', async () => {
        // Re-read before staging; sending performs the authoritative validation.
        const sid = session();
        await refresh(false);
        if (sid !== session() || view?.validity !== 'valid') return;
        const current = reference.promotionId ? view.promotions.find(p => p.id === reference.promotionId) : view;
        const exact = reference.promotionId ? current?.artifact_digest === reference.promotionDigest :
          current?.proposal?.proposal_digest === reference.proposalDigest &&
          current?.proposal?.authority_snapshot === reference.authoritySnapshot;
        if (!exact || !current.actions.includes(type)) {
          chat.clearPreparedMobsAction(); notice('Referência alterada. Consulte o estado atual.'); return;
        }
        const warning = type === 'approve' ? 'Enviar esta aprovação pode iniciar a execução da tarefa. Preparar ação?' :
          type === 'validate_promotion' && preauthorized ? 'Uma validação bem-sucedida pode aplicar o artifact exato pela política já ativa. Preparar ação?' :
          'Preparar esta decisão para a referência exibida? Ainda será necessário pressionar Enviar.';
        if (!window.confirm(warning)) return;
        chat.stageMobsAction({ action: type, ...reference, presentationPreauthorized: !!preauthorized });
        if (type === 'validate_promotion') notice('Digite um comando aprovado e pressione Enviar.');
        if (window.innerWidth <= 900) close();
        composer.focus();
      });
      area.appendChild(b);
    }
  }
  function detailText(value) {
    const pre = document.createElement('pre');
    pre.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    el('studio-detail').replaceChildren(pre);
  }
  function proposalDetail() {
    const proposal = view?.proposal;
    if (!proposal) { detailText('Nenhuma proposta apresentável nesta sessão.'); return; }
    const summary = document.createElement('dl'); summary.className = 'studio-proposal-summary';
    for (const [label, value] of [['Workspace', view.workspace], ['Categoria', proposal.category],
      ['Objetivo', proposal.objective], ['Estado', proposal.status], ['Snapshot', proposal.authority_snapshot]]) {
      const term = document.createElement('dt'); term.textContent = label;
      const description = document.createElement('dd'); description.textContent = value || 'Não informado';
      summary.appendChild(term); summary.appendChild(description);
    }
    const evidence = document.createElement('details'); evidence.className = 'studio-proposal-evidence';
    const heading = document.createElement('summary'); heading.textContent = 'Ver autoridades e snapshot — conteúdo integral';
    const full = document.createElement('pre'); full.textContent = JSON.stringify(proposal, null, 2);
    evidence.appendChild(heading); evidence.appendChild(full);
    const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'studio-copy-proposal';
    copy.textContent = 'Copiar proposta';
    copy.onclick = async () => {
      try { await navigator.clipboard.writeText(full.textContent); copy.textContent = 'Proposta copiada'; }
      catch (_) { notice('Cópia indisponível. Selecione o conteúdo integral da proposta.'); }
    };
    el('studio-detail').replaceChildren(summary, evidence, copy);
  }
  function syncPreviewControl() {
    if (!previewControl) return;
    const { button, section, promotion, busy } = previewControl;
    if (el('studio-detail').children[0] !== section) { previewControl = null; return; }
    const current = view?.promotions?.find(p => p.id === promotion.id && p.artifact_digest === promotion.artifact_digest);
    button.disabled = busy || loading || liveBusy || !!view?.active || view?.validity !== 'valid' || current?.validity !== 'valid';
  }
  function promotionDetail(promotion) {
    if (!promotion) { detailText('Conteúdo não disponível.'); return; }
    const section = document.createElement('section'); section.className = 'studio-promotion-summary';
    const heading = document.createElement('h3'); heading.textContent = 'Alterações de arquivos';
    const state = document.createElement('p');
    const states = { human_approval_required: 'Aguardando revisão e aplicação autorizada',
      promotion_preauthorized: 'Aguardando validação conforme a política ativa',
      promotion_applied_verified: 'Aplicação verificada pelo backend',
      promotion_applying: 'Aplicação em andamento',
      promotion_interrupted_or_uncertain: 'Aplicação interrompida ou incerta — não reaplicar',
      promotion_blocked: 'Aplicação bloqueada' };
    state.textContent = states[promotion.status] || `Estado registrado: ${promotion.status || 'indisponível'}`;
    const validation = document.createElement('p');
    validation.textContent = promotion.validated === true ? 'Validação registrada para este artefato.' :
      'Sem confirmação de validação deste artefato nesta consulta.';
    const files = document.createElement('ul');
    const effects = Array.isArray(promotion.effects) ? promotion.effects : promotion.path ? [promotion] : [];
    for (const effect of effects) {
      const item = document.createElement('li');
      const path = document.createElement('code'); path.textContent = effect.path || 'Caminho indisponível';
      const operation = document.createElement('span');
      operation.textContent = ` · ${effect.effect === 'create' ? 'Criar' : effect.effect === 'write' ? 'Alterar' : 'Operação não reconhecida'}`;
      item.appendChild(path); item.appendChild(operation); files.appendChild(item);
    }
    if (!effects.length) { const item = document.createElement('li'); item.textContent = 'Arquivos indisponíveis nesta consulta.'; files.appendChild(item); }
    const limitation = document.createElement('p');
    limitation.textContent = 'Esta lista identifica os arquivos; não mostra as diferenças de conteúdo. Preparar uma ação não a envia.';
    const compare = document.createElement('button'); compare.type = 'button';
    compare.textContent = 'Comparar conteúdo';
    compare.disabled = promotion.validity !== 'valid' || !!view?.active || loading || liveBusy;
    const control = { button: compare, section, promotion, busy: false }; previewControl = control;
    const preview = document.createElement('div'); preview.className = 'studio-artifact-preview';
    compare.onclick = async () => {
      const sid = session(), seq = epoch, id = promotion.id, digest = promotion.artifact_digest;
      const controller = new AbortController();
      const sameReference = () => sid === session() && selected === id &&
        el('studio-detail').children[0] === section && view?.validity === 'valid' &&
        view?.promotions?.some(p => p.id === id && p.artifact_digest === digest && p.validity === 'valid');
      const current = () => sameReference() && seq === epoch && !controller.signal.aborted && !view?.active && !liveBusy && !loading;
      if (!current() || view?.active || liveBusy || loading) return;
      control.busy = true; compare.disabled = true; preview.textContent = 'Consultando conteúdo selado…';
      previewAbort?.abort(); previewAbort = controller;
      const deadline = setTimeout(() => controller.abort(), 90000);
      try {
        const query = new URLSearchParams({ promotion_id: id, promotion_digest: digest });
        const response = await fetch(`/api/chat/institutional_state/${encodeURIComponent(sid)}?${query}`,
          { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error('Unavailable');
        const data = await response.json();
        if (!current()) return;
        const p = data.preview;
        if (data.session_id !== sid || data.validity !== 'valid' || data.active || p?.validity !== 'valid' ||
            p.session_id !== sid || p.promotion_id !== id || p.artifact_digest !== digest ||
            !Array.isArray(p.files) || p.files.length !== effects.length || p.files.some((file, index) =>
              file.path !== effects[index].path || file.effect !== effects[index].effect ||
              !['before', 'after', 'diff'].every(key => typeof file[key] === 'string'))) throw new Error('Invalid preview');
        preview.replaceChildren();
        preview.appendChild(sealedArtifactPreview(p.files, digest, sameReference));
        limitation.textContent = 'Conteúdo selado desta referência. Consultar não valida, aprova ou aplica alterações.';
      } catch (_) {
        if (current()) preview.textContent = 'Comparação indisponível. A referência pode estar obsoleta, alterada, ser binária ou exceder o limite de leitura. Nenhuma alteração foi aplicada.';
      } finally {
        clearTimeout(deadline);
        if (previewAbort === controller) previewAbort = null;
        control.busy = false;
        if (sameReference()) {
          if (previewControl === control) syncPreviewControl();
          if (seq !== epoch) preview.textContent = 'O estado foi atualizado. Consulte a comparação novamente.';
          else if (controller.signal.aborted) preview.textContent = 'Consulta cancelada. Abra a comparação novamente quando precisar.';
        }
      }
    };
    const record = document.createElement('details');
    const label = document.createElement('summary'); label.textContent = 'Ver referência e registro integral';
    const full = document.createElement('pre'); full.textContent = JSON.stringify(promotion, null, 2);
    record.appendChild(label); record.appendChild(full);
    for (const node of [heading, state, validation, files, limitation, record, compare, preview]) section.appendChild(node);
    el('studio-detail').replaceChildren(section);
  }
  function responseDetail() {
    if (!historyAvailable()) { detailText(historyState === 'unavailable' ? 'Histórico indisponível. Reabra a conversa para consultar seus registros.' : 'Aguardando o histórico desta conversa…'); return; }
    if (!inspectedMessage?.isConnected || !history.contains(inspectedMessage)) {
      if (responseSignature !== 'missing') detailText('Resposta indisponível nesta conversa. Selecione um resultado novamente.');
      responseSignature = 'missing';
      return;
    }
    const body = inspectedMessage.querySelector('.body') || inspectedMessage;
    const copy = body.cloneNode(true);
    for (const hidden of copy.querySelectorAll('.censored-item')) hidden.textContent = '[Ocultado]';
    for (const control of copy.querySelectorAll('button,input,select,textarea,[hidden],.thinking-content,.ai-spinner,.studio-inspect,.studio-file-index,.studio-work-toolbar,.studio-code-disclosure-action,.studio-response-time,script,style')) control.remove();
    const streaming = inspectedMessage.classList.contains('streaming') &&
      (typeof chat.hasActiveStream !== 'function' || chat.hasActiveStream(session()));
    const signature = `${streaming}:${copy.innerHTML}`;
    if (responseSignature !== signature) {
      if (copy.textContent.trim()) {
        copy.className = 'studio-response-body';
        el('studio-detail').replaceChildren(copy);
      } else detailText(streaming ? 'Aguardando conteúdo da resposta…' : 'Resultado sem conteúdo textual.');
      responseSignature = signature;
    }
    el('studio-validity').textContent = streaming ? 'Resposta em andamento — conteúdo parcial, sem confirmação de conclusão.' : 'Resposta da conversa selecionada. Não representa aprovação ou execução institucional.';
  }
  function syncHeading() {
    const current = sessions.getSessions?.().find(s => s.id === session());
    const name = String(current?.name || '').trim();
    const model = String(current?.model || '').split('/').pop();
    const placeholder = model && (name === model || (name.startsWith(model + ' ') && /\d{1,2}:\d{2}/.test(name)));
    const firstMessage = historyAvailable() && history.querySelector('.msg-user > .body')?.textContent?.trim();
    const title = (!placeholder && name) || firstMessage?.slice(0, 80) || 'Nova conversa';
    el('studio-title').textContent = title;
    el('studio-title').title = title;
    const path = workspace.getWorkspace();
    el('studio-workspace-label').textContent = path ? path.split(/[\\/]/).filter(Boolean).pop() : '';
    el('studio-workspace-label').hidden = !path;
    el('studio-workspace-label').title = path;
  }
  function render() {
    for (const b of document.querySelectorAll('button[data-studio-mobs-action]')) {
      b.disabled = !window.studioShell?.canStageMobsAction({ action: b.dataset.studioMobsAction,
        proposalId: b.dataset.studioProposalId, proposalDigest: b.dataset.studioProposalDigest,
        authoritySnapshot: b.dataset.studioSnapshot, promotionId: b.dataset.studioPromotionId,
        promotionDigest: b.dataset.studioPromotionDigest });
    }
    const path = workspace.getWorkspace();
    if (projectEntry) {
      projectName.textContent = path ? path.split(/[\\/]/).filter(Boolean).pop() : 'Selecionar projeto';
      projectEntry.title = path || 'Selecionar projeto ou workspace';
      projectEntry.classList.toggle('active', !!path);
    }
    syncHeading();
    const selector = el('studio-selection');
    const options = [['proposal', 'Proposta / autoridades']];
    for (const p of view?.promotions || []) options.push([p.id, `Promoção ${p.id.slice(0, 12)} · ${p.status}`]);
    options.push(['project', 'Projeto e escopo'], ['sources', 'Fontes carregadas'], ['review', 'Revisão da tarefa'], ['task', 'Preparar tarefa'], ['activity', 'Atividade e arquivos'], ['plans', 'Planos e atualizações'], ['diagnostics', 'Recursos e contexto'], ['help', 'Orientação / capacidades existentes']);
    if (selected === 'response') options.push(['response', 'Resposta inspecionada']);
    const nextOptions = JSON.stringify(options);
    if (nextOptions !== optionSignature) selector.replaceChildren(...options.map(([value, text]) => {
      const o = document.createElement('option'); o.value = value; o.textContent = text; return o;
    }));
    optionSignature = nextOptions;
    if (!options.some(([value]) => value === selected)) selected = 'proposal';
    selector.value = selected;
    el('studio-validity').textContent = loading ? 'Consultando estado confiável…' :
      !view ? 'Selecione uma conversa para consultar pendências.' :
      view.validity !== 'valid' ? 'Estado indisponível ou inválido. Ações institucionais bloqueadas.' :
      view.proposal?.status === 'pending' && !view.reviewer_available ? 'Revisão indisponível nesta sessão. Verifique a configuração operacional do reviewer.' :
      view.continuity === 'unconfirmed' ? 'Aprovação registrada; execução ativa não confirmada. Nenhuma retomada automática.' :
      view.active ? 'Execução ativa confirmada pelo servidor.' : 'Registro consultado; nenhuma execução ativa confirmada.';
    const nextPanel = JSON.stringify([selected, view, ['project', 'review'].includes(selected) && loading, selected === 'sources' ? workspace.getWorkspace() : '']);
    if (nextPanel !== panelSignature) {
    panelSignature = nextPanel;
    el('studio-controls').replaceChildren();
    if (selected === 'project') {
      renderProjectScope(el('studio-detail'), loading ? { ...view, validity: 'unavailable' } : view);
    } else if (selected === 'sources') {
      if (historyAvailable()) renderSources(el('studio-detail'), history, session(), workspace.getWorkspace());
      else detailText('Aguardando o histórico da conversa para consultar suas fontes.');
    } else if (selected === 'review') {
      renderEngineeringReview(el('studio-detail'), loading ? { ...view, validity: 'unavailable' } : view);
    } else if (selected === 'task') {
      renderTaskPreparation(el('studio-detail'), view);
    } else if (selected === 'activity') {
      if (el('studio-detail')._studioWorkUI?.heading.parentNode !== el('studio-detail')) el('studio-detail').replaceChildren();
    } else if (selected === 'plans') {
      delete el('studio-detail')._studioPlanSignature;
    } else if (selected === 'diagnostics') {
      delete el('studio-detail')._studioDiagnosticSignature;
    } else if (selected === 'help') {
      detailText('O workspace define a pasta da tarefa; não concede permissões. Persona define a apresentação e o contexto; modelo e MOBS Auto dizem respeito à inferência e ao roteamento. Use Capacidades para consultar Memory, Skills, modelos e ferramentas existentes. Fechar contexto não cancela ou aprova uma tarefa.');
    } else if (selected === 'proposal') {
      proposalDetail();
      if (view?.validity === 'valid') controls(view.actions, {
        proposalId: view.proposal?.proposal_id, proposalDigest: view.proposal?.proposal_digest,
        authoritySnapshot: view.proposal?.authority_snapshot });
    } else if (selected !== 'response') {
      const p = view?.promotions.find(p => p.id === selected);
      promotionDetail(p);
      if (p?.validity === 'valid' && view?.validity === 'valid') controls(p.actions, {
        promotionId: p.id, promotionDigest: p.artifact_digest });
    }
    }
    for (const b of el('studio-controls').children) b.disabled = loading || liveBusy || !!view?.active;
    syncPreviewControl();
    if (selected === 'response') responseDetail();
    if (selected === 'activity' && historyAvailable()) {
      renderStudioWorkSummary(el('studio-detail'), history, session());
      el('studio-validity').textContent = 'Histórico visível da conversa; permissões e evidências institucionais permanecem na proposta e nos artefatos.';
    }
    if (selected === 'plans' && historyAvailable()) {
      renderStudioPlanIndex(el('studio-detail'), history);
      el('studio-validity').textContent = 'Planejamento informado pelo agente; autorizações continuam separadas.';
    }
    if (selected === 'diagnostics' && historyAvailable()) {
      renderStudioDiagnostics(el('studio-detail'), history);
      el('studio-validity').textContent = 'Observação do runtime; não inicia inferência, ferramenta ou autorização.';
    }
    if (['activity', 'plans', 'diagnostics'].includes(selected) && !historyAvailable()) {
      detailText(historyState === 'unavailable' ? 'Histórico indisponível. Reabra a conversa para consultar seus registros.' : 'Aguardando o histórico desta conversa…');
      el('studio-validity').textContent = 'Registros locais ainda não confirmados para esta conversa.';
    }
    const pending = !!(view?.proposal?.status === 'pending' || view?.promotions?.some(p =>
      ['human_approval_required', 'promotion_preauthorized', 'promotion_applying', 'promotion_interrupted_or_uncertain'].includes(p.status)));
    notice(loading && !view ? 'Consultando pendências…' : view?.validity === 'unavailable' ? 'Pendências não verificáveis — consulte Contexto.' :
      pending ? 'Pendência MOBS — acessível em Contexto.' : view?.active ? 'Tarefa em andamento.' :
      view?.continuity === 'unconfirmed' ? 'Continuidade não confirmada — consulte Contexto.' : '');
    el('studio-pending').classList.toggle('has-pending', pending);
    if (pending && !el('studio-pending').querySelector('button')) {
      const inspect = document.createElement('button');
      inspect.type = 'button'; inspect.textContent = 'Ver proposta';
      inspect.onclick = () => { selected = 'proposal'; render(); open(); };
      el('studio-pending').appendChild(inspect);
    }
    const key = pending && `${view?.session_id}:${view?.proposal?.proposal_digest}:${view?.reviewed}:${view?.promotions.map(p => p.id + p.status + p.validated).join(',')}`;
    if (!loading && key && !seen.has(key)) {
      seen.add(key);
      if (!pinned) selected = 'proposal';
      if (window.innerWidth > 900) open(false);
    }
  }
  async function refresh(reset = false) {
    if (disposed) return;
    const sid = session();
    if (!reset && stateFlight?.sid === sid) {
      queuedStateRefresh = true;
      return stateFlight.done;
    }
    stateFlight?.controller.abort();
    queuedStateRefresh = false;
    previewAbort?.abort(); previewAbort = null;
    const seq = ++epoch;
    if (reset) { inspectedMessage = null; responseSignature = null; panelSignature = null; view = null; pinned = false; liveBusy = false; prepared = null; selected = 'proposal'; chat.clearPreparedMobsAction(); close(); el('studio-pin').setAttribute('aria-pressed', 'false'); }
    loading = !!sid;
    render();
    if (!sid) return;
    const controller = new AbortController();
    let settle;
    const flight = { sid, controller, done: new Promise(resolve => { settle = resolve; }) };
    stateFlight = flight;
    const deadline = setTimeout(() => controller.abort(), 90000);
    flight.deadline = deadline;
    try {
      const r = await fetch(`/api/chat/institutional_state/${encodeURIComponent(sid)}`, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
      if (!r.ok) throw new Error('Unavailable');
      const next = await r.json();
      if (seq !== epoch || sid !== session()) return;
      if (next.session_id !== sid) throw new Error('Wrong session');
      view = next;
      if (prepared) {
        const p = prepared.promotionId ? next.promotions.find(p => p.id === prepared.promotionId) : next;
        const exact = prepared.promotionId ? p?.artifact_digest === prepared.promotionDigest :
          p?.proposal?.proposal_digest === prepared.proposalDigest && p?.proposal?.authority_snapshot === prepared.authoritySnapshot;
        if (next.validity !== 'valid' || !exact || !p?.actions?.includes(prepared.action)) chat.clearPreparedMobsAction();
      }
    } catch (_) {
      if (seq !== epoch || sid !== session()) return;
      view = { session_id: sid, validity: 'unavailable', actions: [], promotions: [] };
      chat.clearPreparedMobsAction();
    } finally {
      clearTimeout(deadline);
      if (seq === epoch) { loading = false; render(); }
      settle();
      if (stateFlight === flight) {
        stateFlight = null;
        if (queuedStateRefresh) { queuedStateRefresh = false; scheduleRefresh(); }
      }
    }
  }
  function scheduleRefresh() { if (disposed) return; clearTimeout(timer); timer = setTimeout(() => refresh(), 120); }
  el('studio-close').onclick = close;
  el('studio-context-open').onclick = () => {
    el('studio-view-options').open = false;
    if (!panel.hidden) close(); else {
      render(); open(); returnFocus = el('studio-context-open');
    }
  };
  el('studio-expand').onclick = () => {
    expanded = !expanded;
    panel.classList.toggle('studio-context-expanded', expanded);
    el('studio-expand').setAttribute('aria-pressed', String(expanded));
    el('studio-expand').textContent = expanded ? 'Reduzir' : 'Expandir';
    syncPanelMode();
  };
  el('studio-refresh').onclick = () => refresh();
  el('studio-selection').onchange = e => { previewAbort?.abort(); previewAbort = null; selected = e.target.value; responseSignature = null; render(); };
  el('studio-pin').onclick = () => { pinned = !pinned; el('studio-pin').setAttribute('aria-pressed', String(pinned)); };
  el('studio-discard').onclick = () => chat.clearPreparedMobsAction();
  document.addEventListener('studio-action-prepared', e => {
    prepared = e.detail;
    composer.required = !chat.hasTextlessMobsAction();
    action.hidden = !prepared;
    el('studio-prepared-label').textContent = prepared ? `${labels[prepared.action] || prepared.action} · ${prepared.proposalId || prepared.promotionId || 'nova proposta'} · Ainda não enviada${prepared.action === 'approve' ? ' — o envio pode iniciar execução' : prepared.presentationPreauthorized ? ' — validação bem-sucedida pode promover pela política ativa' : ''}` : '';
    if (window._updateSendBtnIcon) window._updateSendBtnIcon();
  });
  document.addEventListener('studio-session-selected', event => {
    historyState = event.detail?.session ? 'loading' : 'ready';
    const changed = boundSession !== session();
    boundSession = session();
    refresh(changed);
  });
  document.addEventListener('studio-history-ready', event => {
    if (event.detail?.session !== session()) return;
    historyState = event.detail.loaded ? 'ready' : 'unavailable';
    responseSignature = null; panelSignature = null; render();
    if (historyAvailable()) refreshHistoryPresentation();
  });
  document.addEventListener('studio-session-metadata-changed', syncHeading);
  document.addEventListener('studio-workspace-changed', () => {
    chat.clearPreparedMobsAction();
    if (selected === 'sources') {
      if (historyAvailable()) renderSources(el('studio-detail'), history, session(), workspace.getWorkspace());
      else detailText('Aguardando o histórico da conversa para consultar suas fontes.');
    }
    scheduleRefresh();
  });
  document.addEventListener('studio-activity', e => {
    el('studio-status-description').textContent = e.detail.label || el('product-agent-activity-label')?.textContent || 'Estado da resposta';
    liveBusy = ['understanding', 'investigating', 'executing', 'validating'].includes(e.detail.state);
    render();
    if (['awaiting-decision', 'complete', 'failed'].includes(e.detail.state)) scheduleRefresh();
    if (['complete', 'failed'].includes(e.detail.state)) setTimeout(() => refresh(), 1000);
  });
  function refreshHistoryPresentation() {
    syncHeading();
    if (!historyAvailable()) return;
    foldLongCode(history);
    refreshStudioActivity(history, Date.now(), chat.hasActiveStream ? chat.hasActiveStream(session()) : true);
    if (selected === 'activity') renderStudioWorkSummary(el('studio-detail'), history, session());
    if (selected === 'sources') renderSources(el('studio-detail'), history, session(), workspace.getWorkspace());
    if (selected === 'plans') renderStudioPlanIndex(el('studio-detail'), history);
    if (selected === 'diagnostics') renderStudioDiagnostics(el('studio-detail'), history);
    for (const msg of history.querySelectorAll('.msg-ai:not([data-studio-inspect]),.agent-thread:not([data-studio-inspect])')) {
      msg.dataset.studioInspect = 'true';
      const b = document.createElement('button'); b.type = 'button'; b.className = 'studio-inspect';
      b.textContent = 'Inspecionar resultado';
      const messageSession = session();
      b.onclick = () => {
        // History loads asynchronously after session selection. An old button
        // must never project the previous conversation into the new context.
        if (messageSession !== session() || !msg.isConnected || !history.contains(msg)) {
          notice('Aguarde o carregamento da conversa e selecione o resultado novamente.'); return;
        }
        inspectedMessage = msg; responseSignature = null;
        selected = 'response'; render();
        open();
      };
      msg.appendChild(b);
    }
    // Streaming creates the footer after the message. Keep inspection beside
    // the existing actions once it exists, rather than adding an empty row.
    for (const footer of history.querySelectorAll('.msg-ai > .msg-footer')) {
      const inspect = footer.parentNode.querySelector(':scope > .studio-inspect');
      if (inspect) footer.appendChild(inspect);
    }
    if (selected === 'response') responseDetail();
  }
  const observer = new MutationObserver(refreshHistoryPresentation);
  const character = el('character-indicator-name');
  if (character) {
    const syncPersona = () => {
      const indicator = el('character-indicator-btn');
      persona.textContent = indicator?.style.display !== 'none' && indicator?.title.startsWith('Persona') ?
        character.textContent.trim() || 'Persona' : 'Persona';
    };
    new MutationObserver(syncPersona).observe(character, { childList: true, characterData: true, subtree: true });
    new MutationObserver(syncPersona).observe(el('character-indicator-btn'), { attributes: true });
    syncPersona();
  }
  observer.observe(history, { childList: true, characterData: true, attributes: true, attributeFilter: ['class'], subtree: true });
  window.addEventListener('pagehide', () => {
    disposed = true; queuedStateRefresh = false; clearTimeout(timer);
    if (stateFlight) { clearTimeout(stateFlight.deadline); stateFlight.controller.abort(); }
    previewAbort?.abort(); observer.disconnect?.();
  }, { once: true });
  refreshHistoryPresentation();
  if (window.setInterval) {
    const activityTimer = window.setInterval(() => {
      if (historyAvailable() && history.querySelector('.msg-ai.streaming')) refreshStudioActivity(history, Date.now(), chat.hasActiveStream ? chat.hasActiveStream(session()) : true);
    }, 1000);
    window.addEventListener('pagehide', () => window.clearInterval(activityTimer), { once: true });
  }
  document.addEventListener('pointerdown', e => {
    const options = el('studio-view-options');
    if (options?.open && !options.contains(e.target) && !activity?.contains(e.target)) options.open = false;
    if (!panel.hidden && !pinned && !panel.contains(e.target) && !el('studio-context-open').contains(e.target)) close(false);
  });
  document.addEventListener('keydown', e => {
    // The desktop WebView does not guarantee browser reload accelerators.
    // Reload presentation only when no local work can be interrupted/lost.
    if (e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey && e.key?.toLowerCase() === 'r') {
      e.preventDefault();
      if (e.repeat) return;
      const ids = new Set([session(), ...(sessions.getSessions?.() || []).map(s => s.id)]);
      const active = liveBusy || view?.active || document.querySelector('.send-btn.send-pending') ||
        [...ids].some(id => id && chat.hasActiveStream?.(id));
      if (active || loading || composer.value.trim() || prepared) {
        const text = active || loading ? 'Aguarde a atividade atual terminar para recarregar a interface.' :
          'Envie ou descarte o rascunho e a ação preparada antes de recarregar a interface.';
        if (ui?.showToast) ui.showToast(text, 5000); else notice(text);
        return;
      }
      window.location.reload();
      return;
    }
    const options = el('studio-view-options');
    if (e.key === 'Escape' && options?.open) {
      options.open = false; options.querySelector('summary')?.focus();
      e.preventDefault(); return;
    }
    if (panel.hidden) return;
    if (e.key === 'Escape') { close(); e.preventDefault(); }
    if (e.key === 'Tab' && panel.getAttribute?.('aria-modal') === 'true') {
      const focusable = Array.from(panel.querySelectorAll('button:not(:disabled),select,input,textarea,[tabindex="0"]')).filter(n => n.offsetParent !== null);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (first && e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (last && !e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('resize', () => {
    syncPanelMode();
  });
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(syncPanelMode).observe(el('chat-container'));
  syncPanelMode();
  const ms = el('studio-home');
  ms.onclick = () => { close(); history.scrollIntoView({ block: 'nearest' }); composer.focus(); };
  el('studio-projects').onclick = () => workspace.openWorkspaceBrowser();
  const conversations = el('studio-conversations');
  if (conversations) conversations.onclick = () => el('hamburger-btn').click();
  el('studio-capabilities').onclick = () => {
    if (document.body.classList.contains('sidebar-collapsed')) el('hamburger-btn').click();
    if (!document.body.classList.contains('product-shell-advanced')) el('product-advanced-btn').click();
  };
  el('studio-help').onclick = () => { selected = 'help'; render(); open(); };
  const tips = el('studio-tips');
  function setTips(value) {
    tips.checked = value; el('studio-help').hidden = !value;
    const hint = el('workspace-tip-toggle'), text = el('workspace-tip');
    if (hint) hint.hidden = !value;
    if (!value && text) text.hidden = true;
    if (!value) for (const tip of document.querySelectorAll('.tour-hint')) tip.remove();
  }
  tips.onchange = () => {
    setTips(tips.checked);
    fetch('/api/prefs/studio-tips', { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: tips.checked }) }).catch(() => notice('Não foi possível salvar a preferência de dicas.'));
  };
  fetch('/api/prefs/studio-tips', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : {}).then(v => { if (typeof v.value === 'boolean') setTips(v.value); }).catch(() => {});
  window.studioShell = {
    refresh,
    canStageMobsAction(a) {
      if (a.action === 'propose') return !busy();
      if (loading || liveBusy || view?.active || view?.validity !== 'valid') return false;
      if (a.action !== 'cancel' && view.workspace && workspace.getWorkspace() !== view.workspace) {
        notice('Selecione o workspace exato desta proposta antes de preparar a decisão.');
        return false;
      }
      if (a.promotionId) {
        const p = view.promotions.find(p => p.id === a.promotionId);
        return !!(p?.validity === 'valid' && p.artifact_digest === a.promotionDigest && p.actions.includes(a.action));
      }
      return !!(view.proposal?.proposal_id === a.proposalId && view.proposal?.proposal_digest === a.proposalDigest &&
        view.proposal?.authority_snapshot === a.authoritySnapshot && view.actions.includes(a.action));
    },
    canChangeWorkspace(path) {
      if (path === workspace.getWorkspace()) return true;
      if (busy()) { notice('Contexto ativo ou não confirmado. Use outra conversa para mudar o alvo.'); open(); return false; }
      return true;
    },
    canChangeModel() {
      if (busy()) { notice('Modelo da tarefa preservado. Aguarde confirmação de término ou use outra conversa.'); return false; }
      chat.clearPreparedMobsAction(); return true;
    },
  };
  refresh(true);
  document.body.dataset.studioReady = 'true';
  return window.studioShell;
}
