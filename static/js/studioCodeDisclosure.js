// Presentation only: retain the original code node and its copy/edit controls.
export function foldLongCode(history) {
  for (const pre of history.querySelectorAll('.msg-ai > .body pre')) {
    if (pre.closest('.studio-code-disclosure, .streaming, .thinking-content, .agent-thread') ||
        pre.hasAttribute('data-copy-content')) continue;
    const code = pre.querySelector('code');
    if (!code) continue;
    const text = code.textContent || '';
    const lines = text.replace(/\n$/, '').split('\n').length;
    if (lines < 8 && text.length < 600) continue;
    const details = document.createElement('details');
    details.className = 'studio-code-disclosure';
    const summary = document.createElement('summary');
    summary.title = 'Exemplo de código na resposta. Abrir e copiar não executa o código.';
    const description = document.createElement('span');
    const language = code.dataset.lang || code.className.match(/language-([\w-]+)/)?.[1] || '';
    description.textContent = `Código${language ? ' · ' + language : ''} · ${lines} linhas`;
    const action = document.createElement('span');
    action.className = 'studio-code-disclosure-action';
    const show = document.createElement('span');
    show.className = 'studio-code-show'; show.textContent = 'Abrir código';
    const hide = document.createElement('span');
    hide.className = 'studio-code-hide'; hide.textContent = 'Recolher código';
    action.append(show, hide);
    summary.append(description, action);
    details.appendChild(summary);
    pre.before(details);
    details.appendChild(pre);
  }
}
