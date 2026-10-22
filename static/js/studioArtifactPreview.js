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

export function sealedFilePreview(file, isCurrent = () => true) {
  const item = document.createElement('details'); item.open = true;
  const title = document.createElement('summary'); title.textContent = file.path;
  const diff = document.createElement('pre'); diff.className = 'studio-sealed-diff';
  diff.textContent = file.diff || 'Sem diferença de linhas; confira os conteúdos integrais e suas terminações.';
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
    diff.hidden = !['all', 'diff'].includes(mode.value);
    versions.forEach((version, index) => {
      const chosen = mode.value === (index === 0 ? 'before' : 'after');
      version.hidden = mode.value !== 'all' && !chosen; if (chosen) version.open = true;
    });
  };
  for (const node of [stats, copyButton('Copiar diff', file.diff), mode, feedback]) item.appendChild(node);
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
  return group;
}
