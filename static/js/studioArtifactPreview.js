// Sealed bytes arrive through the existing authenticated observation route.
// These helpers only present/copy text; they never evaluate code or apply files.
export function diffLineStats(text) {
  let added = 0, removed = 0, hunk = false;
  for (const line of String(text || '').split('\n')) {
    if (line.startsWith('@@')) { hunk = true; continue; }
    if (line.startsWith('+') && (hunk || !line.startsWith('+++'))) added++;
    if (line.startsWith('-') && (hunk || !line.startsWith('---'))) removed++;
  }
  return { added, removed };
}

export function contentLayout(text) {
  const value=typeof text==='string'?text:'';
  return {crlf:(value.match(/\r\n/g)||[]).length,lf:(value.replaceAll('\r\n','').match(/\n/g)||[]).length,
    cr:(value.replaceAll('\r\n','').match(/\r/g)||[]).length,finalNewline:/[\r\n]$/.test(value)};
}
export function candidateSummary(files) {
  return {created:files.filter(f=>f.effect==='create').length,changed:files.filter(f=>f.effect==='write').length,
    added:files.reduce((n,f)=>n+diffLineStats(f.diff).added,0),removed:files.reduce((n,f)=>n+diffLineStats(f.diff).removed,0)};
}

export function sealedFilePreview(file, isCurrent = () => true) {
  const item = document.createElement('details'); item.open = true;
  const title = document.createElement('summary'); title.textContent = file.path;
  const diff = document.createElement('pre'); diff.className = 'studio-sealed-diff';
  const diffRows=String(file.diff||'').split('\n');let page=0,showWhitespace=false;
  const renderDiff=()=>{if(!isCurrent())return;let text=diffRows.slice(page*200,(page+1)*200).join('\n');
    if(showWhitespace)text=text.replaceAll('\t','⇥').replaceAll(' ','·');
    diff.textContent=text||'Sem diferença de linhas; confira os conteúdos integrais e suas terminações.';};
  renderDiff();
  item.appendChild(title); item.appendChild(diff);
  const feedback = document.createElement('p'); feedback.setAttribute('role', 'status');
  const copyButton = (label, text) => {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
    button.onclick = async () => {
      if (!isCurrent()) return;
      try { await navigator.clipboard.writeText(text); feedback.textContent = 'Conteúdo exato copiado.'; }
      catch (_) { feedback.textContent = 'Cópia indisponível. Selecione o texto para copiar manualmente.'; }
    };
    return button;
  };
  const versions = [];
  for (const [key, label] of [['before', 'Antes — conteúdo integral'], ['after', 'Depois — conteúdo integral']]) {
    const full = document.createElement('details');
    const heading = document.createElement('summary'); heading.textContent = label;
    const body = document.createElement('pre'); body.textContent = file[key] ||
      (key === 'before' && file.effect === 'create' ? '(arquivo ainda inexistente)' : '(arquivo vazio)');
    for (const node of [heading, body, copyButton(`Copiar ${key === 'before' ? 'antes' : 'depois'}`, file[key])]) full.appendChild(node);
    item.appendChild(full); versions.push(full);
  }
  const { added, removed } = diffLineStats(file.diff);
  const stats = document.createElement('p'); stats.textContent = `+${added} / −${removed} linhas · conteúdo selado, sem aplicação`;
  const mode = document.createElement('select'); mode.setAttribute('aria-label', `Visualização de ${file.path}`);
  for (const [value, label] of [['all', 'Diff e conteúdos'], ['diff', 'Somente diferenças'], ['before', 'Somente antes'], ['after', 'Somente depois']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = label; mode.appendChild(option);
  }
  mode.value = 'all'; mode.onchange = () => {
    if (!isCurrent()) return;
    diff.hidden = !['all', 'diff'].includes(mode.value);
    versions.forEach((version, index) => {
      const chosen = mode.value === (index === 0 ? 'before' : 'after');
      version.hidden = mode.value !== 'all' && !chosen; if (chosen) version.open = true;
    });
  };
  for (const node of [stats, copyButton('Copiar diff', file.diff), mode, feedback]) item.appendChild(node);
  const layout=document.createElement('p');
  const before=contentLayout(file.before),after=contentLayout(file.after);
  layout.textContent=`Quebras antes/depois: CRLF ${before.crlf}/${after.crlf}, LF ${before.lf}/${after.lf}, CR ${before.cr}/${after.cr}; newline final ${before.finalNewline?'sim':'não'}/${after.finalNewline?'sim':'não'}. Cópia preserva o conteúdo selado.`;
  const normalized=t=>String(t||'').replace(/\r\n|\r/g,'\n').replace(/[ \t]/g,'');
  if(file.before!==file.after&&normalized(file.before)===normalized(file.after))layout.textContent+=' Mudança apenas de espaços/tabulações ou tipo de quebra; isso não prova equivalência semântica.';
  item.appendChild(layout);
  const whitespace=document.createElement('button');whitespace.type='button';whitespace.textContent='Destacar espaços no diff';
  whitespace.onclick=()=>{if(!isCurrent())return;showWhitespace=!showWhitespace;renderDiff();};item.appendChild(whitespace);
  if(diffRows.length>200){
    const status=document.createElement('p');status.setAttribute('role','status');
    const update=()=>{renderDiff();status.textContent=`Diff: parte ${page+1}/${Math.ceil(diffRows.length/200)}; copiar diff mantém o conteúdo integral.`;};
    for(const [label,delta]of[['Parte anterior',-1],['Próxima parte',1]]){const b=document.createElement('button');b.type='button';b.textContent=label;
      b.onclick=()=>{if(!isCurrent())return;page=Math.max(0,Math.min(Math.ceil(diffRows.length/200)-1,page+delta));update();};item.appendChild(b);}
    item.appendChild(status);update();
  }
  return item;
}

export function sealedArtifactPreview(files, identity = '', isCurrent = () => true) {
  const group = document.createElement('section');
  const heading = document.createElement('h4'); heading.textContent = `${files.length} arquivo(s) do mesmo candidato`;
  const note = document.createElement('p'); note.textContent = `Referência: ${identity || 'não informada'}. Conteúdo selado; validar, aprovar e aplicar continuam ações distintas.`;
  const selector = document.createElement('select'); selector.setAttribute('aria-label', 'Arquivo do candidato');
  const mode = document.createElement('select'); mode.setAttribute('aria-label', 'Comparação do conjunto');
  for (const [value, text] of [['all', 'Todos os arquivos'], ['selected', 'Um arquivo por vez']]) { const o = document.createElement('option'); o.value = value; o.textContent = text; mode.appendChild(o); }
  mode.value = 'all';
  const content = document.createElement('div');
  const previews = files.map((file, i) => {
    const option = document.createElement('option'); option.value = String(i); option.textContent = file.path; selector.appendChild(option);
    const preview = sealedFilePreview(file, isCurrent); content.appendChild(preview); return preview;
  });
  selector.value = '0';
  const update = () => { if (!isCurrent()) return; previews.forEach((node, i) => { node.hidden = mode.value === 'selected' && String(i) !== selector.value; }); };
  mode.onchange = selector.onchange = update;
  for (const node of [heading, note, selector, mode, content]) group.appendChild(node);
  const totals=candidateSummary(files),summary=document.createElement('p');summary.textContent=`Conjunto selado: ${totals.created} criados · ${totals.changed} escritos · +${totals.added}/−${totals.removed} linhas. Não comprova aplicação.`;group.appendChild(summary);
  const annotations=document.createElement('details'),label=document.createElement('summary');label.textContent='Anotações consultivas deste candidato';annotations.appendChild(label);
  const notes=files.map(file=>{const title=document.createElement('p');title.textContent=file.path;const input=document.createElement('textarea');input.maxLength=4000;input.setAttribute('aria-label',`Anotação de revisão de ${file.path}`);annotations.appendChild(title);annotations.appendChild(input);return{path:file.path,input};});
  const copy=document.createElement('button');copy.type='button';copy.textContent='Copiar anotações com referência';
  copy.onclick=async()=>{if(!isCurrent()||!group.contains(copy))return;const text=`Candidato observado: ${identity}\nAnotações consultivas; não aprovam execução, revisão institucional ou promoção.\n`+notes.map(n=>`${n.path}\n${n.input.value||'(sem anotação)'}`).join('\n\n');
    try{await navigator.clipboard.writeText(text);}catch(_){if(isCurrent())copy.textContent='Cópia indisponível';}};
  annotations.appendChild(copy);group.appendChild(annotations);
  return group;
}
