// Browse only successful read_file snapshots already present in this conversation.
// Never reads the filesystem, performs requests, or treats a path as permission.
const MAX_TEXT = 65536, MAX_HITS = 100;
export function recordSourceSnapshot(node, event) {
  const ref = event?.source_reference;
  if (!node || event?.tool !== 'read_file' || event.exit_code !== 0 ||
      typeof ref?.path !== 'string' || !ref.path.trim() || ref.path.length > 4096 ||
      !Number.isSafeInteger(ref.start_line) || ref.start_line < 1 || typeof event.output !== 'string') return;
  node.dataset.studioSource = JSON.stringify({ path: ref.path, start: ref.start_line,
    text: event.output.slice(0, MAX_TEXT), clipped: event.output.length > MAX_TEXT,
    workspace: typeof ref.workspace === 'string' ? ref.workspace.slice(0, 8192) : '',
    head: typeof ref.baseline_head === 'string' && /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(ref.baseline_head) ? ref.baseline_head : '',
    baseline: typeof ref.baseline_working_tree_sha256 === 'string' && /^[0-9a-f]{64}$/.test(ref.baseline_working_tree_sha256) ? ref.baseline_working_tree_sha256 : '' });
}
export function loadedSources(history) {
  const result = [];
  for (const node of history.querySelectorAll('.agent-thread-node')) {
    if (node.closest('.agent-thread')?.dataset.docWriting) continue;
    try {
      const source = JSON.parse(node.dataset.studioSource || 'null');
      if (typeof source?.path === 'string' && typeof source.text === 'string' && Number.isSafeInteger(source.start) && source.start > 0)
        result.push({ ...source, node });
    } catch (_) {}
  }
  return result;
}
export function searchSources(sources, query) {
  const term = String(query || '').trim().toLocaleLowerCase();
  if (!term) return { hits: [], truncated: false };
  const hits = [];
  for (const source of sources) {
    for (const [i, line] of source.text.split('\n').entries()) {
      if (line.toLocaleLowerCase().includes(term)) {
        if (hits.length === MAX_HITS) return { hits, truncated: true };
        hits.push({ source, line: source.start + i, snippet: line.slice(0, 240) });
      }
    }
  }
  return { hits, truncated: false };
}
function workspaceKey(value) {
  const key = String(value || '').replaceAll('\\', '/').replace(/\/+$/, '');
  return /^[a-z]:\//i.test(key) || key.startsWith('//') ? key.toLocaleLowerCase() : key;
}
export function renderSources(target, history, session = '', workspace = '') {
  let state = target._studioSources;
  const key = workspaceKey(workspace);
  if (!state || state.session !== session || state.workspace !== key || !target.contains(state.search)) {
    target.replaceChildren();
    const heading = document.createElement('h3'); heading.textContent = 'Fontes carregadas';
    const note = document.createElement('p'); note.textContent = 'Leituras autorizadas já carregadas nesta conversa. Histórico parcial, sem varredura do workspace. Caminhos e linhas identificam o trecho observado; baseline e atualidade não são certificados aqui.';
    const search = document.createElement('input'); search.type = 'search'; search.placeholder = 'Buscar texto nas leituras carregadas'; search.setAttribute('aria-label', search.placeholder);
    const tree = document.createElement('div'), matches = document.createElement('div'), viewer = document.createElement('div');
    for (const node of [heading, note, search, tree, matches, viewer]) target.appendChild(node);
    state = { session, workspace:key, search, tree, matches, viewer, signature: null }; target._studioSources = state;
    search.oninput = () => { if (target._studioSources !== state || !target.contains(search)) return; state.signature = null; renderSources(target, history, session, workspace); };
  }
  const sources = loadedSources(history).filter(source => !key || workspaceKey(source.workspace) === key);
  const signature = JSON.stringify([state.search.value, sources.map(s => [s.path, s.start, s.text, s.head, s.baseline, s.workspace, s.clipped])]);
  if (state.signature === signature && state.nodes?.length === sources.length && state.nodes.every((node,i)=>node===sources[i].node)) return;
  state.nodes = sources.map(s=>s.node);
  state.signature = signature; state.tree.replaceChildren(); state.matches.replaceChildren(); state.viewer.replaceChildren();
  const current = source => target._studioSources === state && target.contains(state.search) && history.contains(source.node);
  const show = (source, line = source.start) => {
    if (!current(source)) return;
    state.viewer.replaceChildren();
    const origin = document.createElement('p'); origin.textContent = `${source.path} · ${source.workspace || 'workspace não informado'} · conversa ${session} · trecho recebido${source.clipped ? ' · limitado na apresentação' : ''} · baseline do mandato: ${source.head || 'não informado'}${source.baseline ? ' / '+source.baseline : ''}. Referência do mandato, não hash do conteúdo atual do arquivo.`;
    const lineInput = document.createElement('input'); lineInput.type = 'number'; lineInput.min = source.start; lineInput.value = line; lineInput.setAttribute('aria-label', 'Ir para linha carregada');
    const body = document.createElement('pre');
    const render = () => {
      if (!current(source)) return;
      const rows = source.text.split('\n');
      const n = Math.max(source.start, Math.min(source.start + rows.length - 1, Math.trunc(Number(lineInput.value)) || source.start));
      lineInput.value = n;
      const start = Math.max(0, n - source.start - 5);
      body.textContent = rows.slice(start, start + 40).map((text, i) => `${source.start + start + i}  ${text}`).join('\n');
    };
    lineInput.oninput = render; render();
    for (const node of [origin, lineInput, body]) state.viewer.appendChild(node);
  };
  const folders = new Map();
  for (const source of sources) {
    const path = source.path.replaceAll('\\', '/');
    const folder = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '(raiz apresentada)';
    if (!folders.has(folder)) {
      const group = document.createElement('details'), title = document.createElement('summary'); title.textContent = folder; group.appendChild(title);
      folders.set(folder, group); state.tree.appendChild(group);
    }
    const button = document.createElement('button'); button.type = 'button'; button.textContent = `${path.split('/').at(-1)} · linha ${source.start}`; button.onclick = () => show(source); folders.get(folder).appendChild(button);
  }
  if (!sources.length) state.tree.textContent = 'Nenhuma leitura de arquivo com origem registrada. Solicite uma leitura pelas ferramentas admitidas; abrir este painel não a executa.';
  const result = searchSources(sources, state.search.value);
  if (state.search.value.trim()) {
    const count = document.createElement('p'); count.setAttribute('role', 'status'); count.textContent = `${result.hits.length} trechos${result.truncated ? ' · limite de 100 resultados' : ''} nas leituras carregadas`; state.matches.appendChild(count);
  }
  for (const hit of result.hits) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = `${hit.source.path}:${hit.line} · ${hit.snippet}`; button.onclick = () => show(hit.source, hit.line); state.matches.appendChild(button);
  }
}
