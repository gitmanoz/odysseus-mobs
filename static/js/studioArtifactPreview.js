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

export function sealedFilePreview(file) {
  const item = document.createElement('details'); item.open = true;
  const title = document.createElement('summary'); title.textContent = file.path;
  const diff = document.createElement('pre'); diff.className = 'studio-sealed-diff';
  diff.textContent = file.diff || 'Sem diferença de linhas; confira os conteúdos integrais e suas terminações.';
  item.appendChild(title); item.appendChild(diff);
  const feedback = document.createElement('p'); feedback.setAttribute('role', 'status');
  const copyButton = (label, text) => {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
    button.onclick = async () => {
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
