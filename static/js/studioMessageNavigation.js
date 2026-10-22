// Presentation of already loaded messages only: no history fetch or decisions.
export function messagePreview(message) {
  const body = message.querySelector('.body');
  if (!body) return 'Mensagem sem texto';
  const copy = body.cloneNode(true);
  for (const node of copy.querySelectorAll('button,input,select,textarea,[hidden],script,style,.thinking-content,.censored-item')) node.remove();
  return copy.textContent.replace(/\s+/g, ' ').trim().slice(0, 360) || 'Mensagem sem texto';
}

export function initMessageNavigation({ history, container, getSession, isLoading = () => false, jumpToMessage }) {
  const navigation = document.createElement('nav');
  navigation.className = 'studio-message-nav';
  navigation.setAttribute('aria-label', 'Navegar pelas mensagens enviadas já carregadas');
  navigation.hidden = true;
  const tooltip = document.createElement('div');
  tooltip.id = 'studio-message-preview'; tooltip.className = 'studio-message-preview';
  tooltip.setAttribute('role', 'tooltip'); tooltip.hidden = true;
  container.appendChild(navigation); container.appendChild(tooltip);
  let nodes = [], buttons = [], frame = null, suspended = false, boundSession = getSession();
  const hidePreview = () => { tooltip.hidden = true; };
  const current = () => {
    if (!nodes.length) return;
    const top = history.getBoundingClientRect().top + 60;
    let selected = 0;
    nodes.forEach((node, index) => { if (node.getBoundingClientRect().top <= top) selected = index; });
    buttons.forEach((button, index) => {
      if (index === selected) button.setAttribute('aria-current', 'location');
      else button.removeAttribute('aria-current');
    });
  };
  const rebuild = () => {
    frame = null;
    if (suspended || isLoading()) return;
    if (boundSession !== getSession()) { boundSession = getSession(); nodes = []; hidePreview(); }
    const next = [...history.querySelectorAll('.msg-user')].filter(node => !node.hidden && !node.closest('[hidden]'));
    if (next.length === nodes.length && next.every((node, i) => node === nodes[i])) { current(); return; }
    nodes = next; buttons = []; navigation.replaceChildren(); hidePreview();
    navigation.hidden = !nodes.length;
    const session = boundSession;
    nodes.forEach((message, index) => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'studio-message-tick';
      const preview = messagePreview(message);
      button.setAttribute('aria-label', `Ir à mensagem ${index + 1}: ${preview.slice(0, 100)}`);
      button.setAttribute('aria-describedby', tooltip.id);
      const valid = () => !suspended && !isLoading() && session === getSession() && message.isConnected && history.contains(message);
      const show = () => {
        if (!valid()) return;
        tooltip.replaceChildren();
        const title = document.createElement('strong'); title.textContent = `Mensagem ${index + 1}`;
        const text = document.createElement('p'); text.textContent = messagePreview(message);
        tooltip.appendChild(title); tooltip.appendChild(text); tooltip.hidden = false;
        const rect = button.getBoundingClientRect();
        tooltip.style.left = `${Math.min(rect.right + 10, Math.max(8, window.innerWidth - 308))}px`;
        tooltip.style.top = `${Math.max(8, Math.min(rect.top - 20, window.innerHeight - tooltip.offsetHeight - 12))}px`;
      };
      button.addEventListener('mouseenter', show);
      button.addEventListener('focus', show);
      button.addEventListener('mouseleave', hidePreview);
      button.addEventListener('blur', hidePreview);
      button.addEventListener('click', () => {
        if (!valid()) return;
        if (!jumpToMessage?.(message)) return;
        message.tabIndex = -1; message.focus({ preventScroll: true });
        message.classList.add('studio-jump-target');
        setTimeout(() => message.classList.remove('studio-jump-target'), 1400);
        hidePreview();
      });
      button.addEventListener('keydown', e => {
        let target;
        if (e.key === 'ArrowDown') target = Math.min(index + 1, buttons.length - 1);
        if (e.key === 'ArrowUp') target = Math.max(0, index - 1);
        if (e.key === 'Home') target = 0;
        if (e.key === 'End') target = buttons.length - 1;
        if (e.key === 'Escape') hidePreview();
        if (target !== undefined) { e.preventDefault(); buttons[target]?.focus(); }
      });
      buttons.push(button); navigation.appendChild(button);
    });
    current();
  };
  const schedule = () => {
    if (frame !== null) return;
    frame = (window.requestAnimationFrame || (callback => setTimeout(callback, 0)))(rebuild);
  };
  const observer = new MutationObserver(schedule);
  observer.observe(history, { childList: true, subtree: true });
  history.addEventListener('scroll', current, { passive: true });
  document.addEventListener('studio-session-selected', event => {
    suspended = !!event.detail?.session;
    boundSession = getSession(); nodes = []; buttons = [];
    navigation.replaceChildren(); navigation.hidden = true; hidePreview();
    if (!suspended) schedule();
  });
  document.addEventListener('studio-history-ready', event => {
    if (event.detail?.session !== getSession()) return;
    suspended = !event.detail.loaded;
    if (!suspended) schedule();
  });
  window.addEventListener('resize', hidePreview);
  schedule();
  return { refresh: schedule };
}
