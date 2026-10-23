// Browse only successful read_file snapshots already present in this conversation.
// Never reads the filesystem, performs requests, or treats a path as permission.
const MAX_TEXT = 65536, MAX_HITS = 100;
function observedLines(text) {
  if(!text)return [];
  const rows=text.split('\n');if(rows.at(-1)==='')rows.pop();return rows;
}
function pagination(value) {
  const data = {};
  if (value && typeof value === 'object') {
    for (const key of ['has_more', 'partial_line', 'truncated','presentation_truncated']) if (typeof value[key] === 'boolean') data[key] = value[key];
    for (const key of ['next_offset', 'lines_read']) if (Number.isSafeInteger(value[key]) && value[key] >= (key === 'next_offset' ? 1 : 0)) data[key] = value[key];
  }
  return data;
}
export function sourceReadStatus(source) {
  if (source.partial_line) return 'Linha parcialmente lida; o restante não pode ser retomado por offset de linha.';
  if (source.clipped || source.presentation_truncated) return 'Trecho limitado na apresentação; não representa todo o conteúdo recebido.';
  if (source.has_more === true) return `Leitura paginada${source.next_offset ? ' · próxima linha '+source.next_offset : ''}`;
  if (source.has_more === false && !source.clipped) return 'Fim do arquivo observado nesta leitura; não certifica o estado atual do disco.';
  return 'Completude não registrada; trecho observado apenas.';
}
export function recordSourceSnapshot(node, event) {
  if(node?.dataset && event?.type !== 'tool_start') {
    if(event?.phase_timing&&typeof event.phase_timing==='object')node.dataset.studioToolPhases=JSON.stringify(Object.fromEntries(Object.entries(event.phase_timing).filter(([key,value])=>['dispatch_seconds','execution_seconds'].includes(key)&&Number.isFinite(value)&&value>=0)));
    if(Number.isFinite(event?.dispatch_execution_seconds)&&event.dispatch_execution_seconds>=0)node.dataset.studioToolSeconds=String(event.dispatch_execution_seconds);
    if(typeof event?.workspace==='string')node.dataset.studioToolWorkspace=event.workspace.slice(0,8192);
    if(typeof event?.output==='string')node.dataset.studioDiagnosticLocations=JSON.stringify(diagnosticLocations(event.output));
  }
  const ref = event?.source_reference;
  if (!node || event?.tool !== 'read_file' || event.exit_code !== 0 ||
      typeof ref?.path !== 'string' || !ref.path.trim() || ref.path.length > 4096 ||
      !Number.isSafeInteger(ref.start_line) || ref.start_line < 1 || typeof event.output !== 'string') return;
  node.dataset.studioSource = JSON.stringify({ path: ref.path, start: ref.start_line,
    ...pagination(event.source_pagination),
    text: event.output.slice(0, MAX_TEXT), clipped: event.output.length > MAX_TEXT || event.source_pagination?.presentation_truncated === true,
    workspace: typeof ref.workspace === 'string' ? ref.workspace.slice(0, 8192) : '',
    head: typeof ref.baseline_head === 'string' && /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(ref.baseline_head) ? ref.baseline_head : '',
    baseline: typeof ref.baseline_working_tree_sha256 === 'string' && /^[0-9a-f]{64}$/.test(ref.baseline_working_tree_sha256) ? ref.baseline_working_tree_sha256 : '' });
}
export function diagnosticLocations(output) {
  const result=[];
  for(const line of String(output||'').slice(0,65536).split('\n')){
    const match=line.match(/^\s*File "([^"\r\n]{1,4096})", line (\d+)/)||line.match(/^([^\r\n]{1,4096}\.(?:py|gd|js|ts)):(\d+)(?::|\s|$)/);
    if(match&&Number.isSafeInteger(Number(match[2]))&&Number(match[2])>0)result.push({path:match[1],line:Number(match[2])});
    if(result.length===100)break;
  }
  return result;
}
export function loadedSources(history) {
  const result = [];
  for (const node of history.querySelectorAll('.agent-thread-node')) {
    if (node.closest('.agent-thread')?.dataset.docWriting) continue;
    try {
      const source = JSON.parse(node.dataset.studioSource || 'null');
      if (typeof source?.path === 'string' && source.path.length <= 4096 && typeof source.text === 'string' && Number.isSafeInteger(source.start) && source.start > 0)
        result.push({ path:source.path, start:source.start, text:source.text.slice(0,MAX_TEXT),
          clipped:source.clipped === true || source.text.length > MAX_TEXT,
          workspace:typeof source.workspace === 'string' ? source.workspace.slice(0,8192) : '',
          head:typeof source.head === 'string' ? source.head.slice(0,64) : '',
          baseline:typeof source.baseline === 'string' ? source.baseline.slice(0,64) : '',
          ...pagination(source), node });
    } catch (_) {}
  }
  return result;
}
export function searchSources(sources, query) {
  const term = String(query || '').trim().toLocaleLowerCase();
  if (!term) return { hits: [], truncated: false };
  const hits = [];
  for (const source of sources) {
    for (const [i, line] of observedLines(source.text).entries()) {
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
export function groupSourcePages(sources) {
  const groups = new Map();
  for (const source of sources) {
    const key = JSON.stringify([workspaceKey(source.workspace),source.path,source.head || '',source.baseline || '']);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(source);
  }
  return [...groups.values()];
}
export function sourceConflicts(sources) {
  const conflicts = []; let comparisons = 0;
  for (const pages of groupSourcePages(sources)) for (let i=0;i<pages.length;i++) for(let j=i+1;j<pages.length;j++) {
    if (++comparisons > 2000 || conflicts.length === 100) return {conflicts,limited:true};
    const a=pages[i],b=pages[j],ar=a.text.split('\n'),br=b.text.split('\n');
    const start=Math.max(a.start,b.start),end=Math.min(a.start+ar.length-1,b.start+br.length-1);
    for(let line=start;line<=end;line++) {
      // A final empty split token is not an observed next line; partial tails
      // also cannot prove a contradictory complete line.
      if(line===a.start+ar.length-1 || line===b.start+br.length-1) continue;
      if(ar[line-a.start]!==br[line-b.start]) { conflicts.push({path:a.path,line}); break; }
    }
  }
  return {conflicts,limited:false};
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
    const filter=document.createElement('input');filter.type='search';filter.placeholder='Filtrar nome ou caminho';filter.setAttribute('aria-label',filter.placeholder);
    target.appendChild(filter);state.pathFilter=filter;
    filter.oninput=search.oninput;
  }
  const sources = loadedSources(history).filter(source => (!key || workspaceKey(source.workspace) === key) && source.path.toLocaleLowerCase().includes(state.pathFilter.value.trim().toLocaleLowerCase()));
  const diagnosticNodes=Array.from(history.querySelectorAll('.agent-thread-node'));
  const signature = JSON.stringify([state.search.value,state.pathFilter.value,diagnosticNodes.map(n=>[n.dataset.studioToolWorkspace,n.dataset.studioDiagnosticLocations]), sources.map(s => [s.path, s.start, s.text, s.head, s.baseline, s.workspace, s.clipped,s.has_more,s.next_offset,s.partial_line])]);
  if (state.signature === signature && state.nodes?.length === sources.length && state.nodes.every((node,i)=>node===sources[i].node) && state.diagnosticNodes?.length===diagnosticNodes.length && state.diagnosticNodes.every((node,i)=>node===diagnosticNodes[i])) return;
  state.diagnosticNodes=diagnosticNodes;
  state.nodes = sources.map(s=>s.node);
  state.signature = signature; state.tree.replaceChildren(); state.matches.replaceChildren(); state.viewer.replaceChildren();
  const current = source => target._studioSources === state && target.contains(state.search) && history.contains(source.node);
  const show = (source, line = source.start) => {
    if (!current(source)) return;
    state.viewer.replaceChildren();
    const origin = document.createElement('p'); origin.textContent = `${source.path} · ${source.workspace || 'workspace não informado'} · conversa ${session} · trecho recebido${source.clipped ? ' · limitado na apresentação' : ''} · baseline do mandato: ${source.head || 'não informado'}${source.baseline ? ' / '+source.baseline : ''}. Referência do mandato, não hash do conteúdo atual do arquivo.`;
    const lineInput = document.createElement('input'); lineInput.type = 'number'; lineInput.min = source.start; lineInput.value = line; lineInput.setAttribute('aria-label', 'Ir para linha carregada');
    const body = document.createElement('pre');
    const readState=document.createElement('p');readState.textContent=sourceReadStatus(source);
    const feedback=document.createElement('p');feedback.setAttribute('role','status');
    const copy=(label,makeText)=>{
      const button=document.createElement('button');button.type='button';button.textContent=label;
      button.onclick=async()=>{if(!current(source)||!state.viewer.contains(button))return;
        try{await navigator.clipboard.writeText(makeText());if(current(source)&&state.viewer.contains(button))feedback.textContent='Copiado; nenhum pedido foi enviado.';}
        catch(_){if(current(source)&&state.viewer.contains(button))feedback.textContent='Cópia indisponível.';}};
      return button;
    };
    const endInput=document.createElement('input');endInput.type='number';endInput.min=source.start;endInput.value=source.start;endInput.setAttribute('aria-label','Última linha para copiar');
    const excerpt=copy('Copiar intervalo com referência',()=>{
    const rows=observedLines(source.text),first=Math.max(source.start,Math.min(source.start+rows.length-1,Math.trunc(Number(lineInput.value))||source.start));
      const end=Math.max(first,Math.min(source.start+rows.length-1,Math.trunc(Number(endInput.value))||first));
      return `${source.path}:${first}-${end} · trecho observado · ${sourceReadStatus(source)}\n${rows.slice(first-source.start,end-source.start+1).join('\n')}`;
    });
    const jump=document.createElement('button');jump.type='button';jump.textContent='Ir ao evento de leitura';jump.onclick=()=>{if(current(source)){source.node.scrollIntoView({block:'center'});source.node.setAttribute('tabindex','-1');source.node.focus();}};
    const render = () => {
      if (!current(source)) return;
      const rows = observedLines(source.text);
      const n = Math.max(source.start, Math.min(source.start + rows.length - 1, Math.trunc(Number(lineInput.value)) || source.start));
      lineInput.value = n;
      const start = Math.max(0, n - source.start - 5);
      body.textContent = rows.slice(start, start + 40).map((text, i) => `${source.start + start + i}  ${text}`).join('\n');
    };
    lineInput.oninput = render; render();
    for (const node of [origin,readState,lineInput,body,endInput,excerpt,jump,feedback]) state.viewer.appendChild(node);
    if(source.has_more===true && !source.partial_line && source.next_offset) state.viewer.appendChild(copy('Copiar pedido de continuação',()=>`Leia o arquivo ${JSON.stringify(source.path)} a partir da linha ${source.next_offset}, usando somente o escopo e as ferramentas admitidas. Este pedido não concede autorização adicional.`));
  };
  const folders = new Map(),fileGroups=new Map();
  for (const source of sources) {
    const path = source.path.replaceAll('\\', '/');
    const folder = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '(raiz apresentada)';
    if (!folders.has(folder)) {
      const group = document.createElement('details'), title = document.createElement('summary'); title.textContent = folder; group.appendChild(title);
      folders.set(folder, group); state.tree.appendChild(group);
    }
    const fileKey=JSON.stringify([folder,path,source.head,source.baseline]);
    if(!fileGroups.has(fileKey)){const g=document.createElement('details'),t=document.createElement('summary');t.textContent=path.split('/').at(-1);g.appendChild(t);folders.get(folder).appendChild(g);fileGroups.set(fileKey,g);}
    const button = document.createElement('button'); button.type = 'button'; button.textContent = `${source.text ? 'Linhas '+source.start+'–'+(source.start+Math.max(0,observedLines(source.text).length-1)) : 'Trecho vazio'} · ${sourceReadStatus(source)}`; button.onclick = () => show(source); fileGroups.get(fileKey).appendChild(button);
  }
  if (!sources.length) state.tree.textContent = 'Nenhuma leitura de arquivo com origem registrada. Solicite uma leitura pelas ferramentas admitidas; abrir este painel não a executa.';
  const pages=document.createElement('p');pages.textContent=`${groupSourcePages(sources).length} arquivo(s)/referência(s) · ${sources.length} trecho(s), sem união automática.`;state.tree.appendChild(pages);
  const conflicts=sourceConflicts(sources);
  for(const conflict of conflicts.conflicts){const p=document.createElement('p');p.textContent=`Trechos observados divergem: ${conflict.path}:${conflict.line}. Confira os eventos; não há escolha automática da versão atual.`;state.tree.appendChild(p);}
  if(conflicts.limited){const p=document.createElement('p');p.textContent='Comparação de sobreposições limitada; ausência de alerta não comprova igualdade.';state.tree.appendChild(p);}
  const result = searchSources(sources, state.search.value);
  if (state.search.value.trim()) {
    const count = document.createElement('p'); count.setAttribute('role', 'status'); count.textContent = `${result.hits.length} trechos${result.truncated ? ' · limite de 100 resultados' : ''} nas leituras carregadas`; state.matches.appendChild(count);
  }
  for (const hit of result.hits) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = `${hit.source.path}:${hit.line} · ${hit.snippet}`; button.onclick = () => show(hit.source, hit.line); state.matches.appendChild(button);
  }
  for(const node of history.querySelectorAll('.agent-thread-node')){
    if(key&&workspaceKey(node.dataset.studioToolWorkspace)!==key)continue;
    let locations;try{locations=JSON.parse(node.dataset.studioDiagnosticLocations||'[]');}catch(_){continue;}
    if(!Array.isArray(locations))continue;
    for(const loc of locations.slice(0,100)){
      if(typeof loc?.path!=='string'||!Number.isSafeInteger(loc.line)||loc.line<1)continue;
      const matching=sources.filter(s=>s.path.replaceAll('\\','/')===loc.path.replaceAll('\\','/') && loc.line>=s.start && loc.line<s.start+observedLines(s.text).length);
      if(matching.length!==1)continue;
      const button=document.createElement('button');button.type='button';button.textContent=`Referência na saída: ${loc.path}:${loc.line} · trecho observado`;
      button.onclick=()=>{if(history.contains(node))show(matching[0],loc.line);};state.matches.appendChild(button);
    }
  }
}
