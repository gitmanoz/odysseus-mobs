// Model Picker — chatbox model selector dropdown
// Extracted from sessions.js

import { providerLogo } from './providers.js';
import uiModule from './ui.js';
import settingsModule from './settings.js';
import { sortModelObjects } from './modelSort.js';
import spinnerModule from './spinner.js';

const API_BASE = window.location.origin;
const MOBS_AUTO_MODEL_ID = '__mobs_auto__';
const MOBS_AUTO_DISPLAY = 'MOBS Auto';
const MOBS_GENERAL_MODEL = 'qwen3:8b';
const MOBS_CODER_MODEL = 'qwen2.5-coder:7b';

// ── Recent + Favorites persistence ──
// Recent is auto-tracked (last 5 picks, most-recent-first) and lives in its
// own key. Favorites is the SAME key the sidebar Models section uses, so a
// favorite toggled here shows up there and vice-versa.
const RECENT_KEY = 'odysseus-model-recent';
const FAVORITES_KEY = 'odysseus-model-favorites';
const RECENT_MAX = 5;
// Catalogs at or below this size are small enough that hiding everything
// behind search would be a regression — keep listing them in browse mode.
const BROWSE_ALL_LIMIT = 12;

function _loadList(key) {
  try {
    const a = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(a) ? a : [];
  } catch { return []; }
}
function _saveList(key, list) {
  try { localStorage.setItem(key, JSON.stringify(list)); } catch { /* quota / private mode */ }
}
function _loadRecent() { return _loadList(RECENT_KEY); }
function _pushRecent(mid) {
  if (!mid) return;
  const next = _loadRecent().filter(x => x !== mid);
  next.unshift(mid);
  _saveList(RECENT_KEY, next.slice(0, RECENT_MAX));
}
function _loadFavorites() { return _loadList(FAVORITES_KEY); }
function _toggleFavorite(mid) {
  const favs = _loadFavorites();
  const i = favs.indexOf(mid);
  if (i >= 0) favs.splice(i, 1);
  else favs.push(mid);
  _saveList(FAVORITES_KEY, favs);
  try {
    if (window.modelsModule && typeof window.modelsModule.refreshModels === 'function') {
      window.modelsModule.refreshModels();
    }
  } catch { /* sidebar not present */ }
  return i < 0;
}

function _pickerModelKey(m) {
  if (!m) return '';
  return `${m.endpointId || m.url || m.epName || 'model'}::${m.mid || ''}`;
}

function _displayModelName(modelId) {
  if (!modelId) return 'Select model';
  if (modelId === MOBS_AUTO_MODEL_ID) return MOBS_AUTO_DISPLAY;
  return modelId.split('/').pop();
}

function _handlePickerKeydown(e, listEl, itemSelector, closeFn) {
  if (e.key === 'Escape') { closeFn(); return; }
  if (e.key === 'Enter') {
    e.preventDefault();
    const active = listEl.querySelector(itemSelector + '.kb-active') || listEl.querySelector(itemSelector);
    if (active) active.click();
    return;
  }
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const items = [...listEl.querySelectorAll(itemSelector)].filter(el => el.style.display !== 'none');
    if (!items.length) return;
    const cur = items.findIndex(el => el.classList.contains('kb-active'));
    items.forEach(el => el.classList.remove('kb-active'));
    let next;
    if (e.key === 'ArrowDown') next = cur < items.length - 1 ? cur + 1 : 0;
    else next = cur > 0 ? cur - 1 : items.length - 1;
    items[next].classList.add('kb-active');
    items[next].scrollIntoView({ block: 'nearest' });
  }
}

let _deps = null;
let _autoSelectingDefault = false;
let _defaultChatPickInFlight = false;
let _defaultPendingSeq = 0;

function _modelExists(modelId, url) {
  if (modelId === MOBS_AUTO_MODEL_ID) return true;
  if (!modelId || !window.modelsModule || !window.modelsModule.getCachedItems) return false;
  const items = window.modelsModule.getCachedItems() || [];
  if (!items.length) return true;
  const targetUrl = (url || '').replace(/\/+$/, '');
  return items.some(item => {
    if (item.offline) return false;
    const itemUrl = (item.url || '').replace(/\/+$/, '');
    const models = (item.models || []).concat(item.models_extra || []);
    return models.includes(modelId) && (!targetUrl || itemUrl === targetUrl);
  });
}

function _firstAvailableModel() {
  if (!window.modelsModule || !window.modelsModule.getCachedItems) return null;
  const items = window.modelsModule.getCachedItems() || [];
  for (const item of items) {
    if (item.offline) continue;
    const models = (item.models || []).concat(item.models_extra || []);
    if (!models.length) continue;
    return { url: item.url, modelId: models[0], endpointId: item.endpoint_id || '' };
  }
  return null;
}

async function _ensureModelCacheForFallback() {
  if (!window.modelsModule || !window.modelsModule.getCachedItems) return;
  const items = window.modelsModule.getCachedItems() || [];
  if (items.length) return;
  if (typeof window.modelsModule.refreshModels === 'function') {
    try { await window.modelsModule.refreshModels(false); } catch (_) {}
  }
}

async function _ensureDefaultPendingChat() {
  if (!_deps || _defaultChatPickInFlight) return;
  if (_deps.getCurrentSessionId && _deps.getCurrentSessionId()) return;
  const pending = _deps.getPendingChat && _deps.getPendingChat();
  if (pending && pending.modelId) return;
  _defaultChatPickInFlight = true;
  const seq = ++_defaultPendingSeq;
  try {
    let dc = null;
    try { dc = window.__odysseusDefaultChat || null; } catch (_) {}
    if (!dc || !dc.endpoint_url || !dc.model) {
      try {
        const res = await fetch(`${API_BASE}/api/default-chat`, { credentials: 'same-origin' });
        if (res.ok) dc = await res.json();
      } catch (_) {}
    }
    if (dc && dc.endpoint_url && dc.model) {
      if (seq !== _defaultPendingSeq) return;
      const latest = _deps.getPendingChat && _deps.getPendingChat();
      if (latest && latest.modelId && latest.source !== 'default' && latest.source !== 'fallback') return;
      try {
        window.__odysseusDefaultChat = dc;
        localStorage.setItem('odysseus-default-chat-cache', JSON.stringify(dc));
      } catch (_) {}
      const pendingUrl = String((latest && latest.url) || '').replace(/\/+$/, '');
      const defaultUrl = String(dc.endpoint_url || '').replace(/\/+$/, '');
      _deps.setPendingChat({ url: dc.endpoint_url, modelId: dc.model, endpointId: dc.endpoint_id || '', source: 'default' });
      if (!latest || latest.modelId !== dc.model || pendingUrl !== defaultUrl || latest.source !== 'default') updateModelPicker();
      return;
    }
    if (pending && pending.modelId) return;
    await _ensureModelCacheForFallback();
    const fallback = _firstAvailableModel();
    if (fallback) {
      if (seq !== _defaultPendingSeq) return;
      const latest = _deps.getPendingChat && _deps.getPendingChat();
      if (latest && latest.modelId && latest.source !== 'default' && latest.source !== 'fallback') return;
      _deps.setPendingChat({ ...fallback, source: 'fallback' });
      updateModelPicker();
    }
  } finally {
    _defaultChatPickInFlight = false;
  }
}

export function initModelPicker(deps) {
  _deps = deps;
  _initModelPickerDropdown();
}

function _initModelPickerDropdown() {
  const wrap = document.getElementById('model-picker-wrap');
  const btn = document.getElementById('model-picker-btn');
  const menu = document.getElementById('model-picker-menu');
  const search = document.getElementById('model-picker-search');
  const listEl = document.getElementById('model-picker-list');
  const searchRow = menu ? menu.querySelector('.model-picker-search-row') : null;
  const refreshBtn = document.getElementById('model-picker-refresh-btn');
  if (!wrap || !btn || !menu || !search || !listEl) return;
  if (wrap.dataset.modelPickerBound === '1') return;
  wrap.dataset.modelPickerBound = '1';

  function _close() {
    if (menu.classList.contains('hidden')) return;
    const _scrollBtn = document.getElementById('scroll-bottom-btn');
    if (_scrollBtn) _scrollBtn.style.display = '';
    menu.classList.add('closing');
    menu.addEventListener('animationend', function _onDone() {
      menu.removeEventListener('animationend', _onDone);
      menu.classList.remove('closing');
      menu.classList.add('hidden');
      search.value = '';
    }, { once: true });
    setTimeout(() => {
      if (!menu.classList.contains('hidden')) {
        menu.classList.remove('closing');
        menu.classList.add('hidden');
        search.value = '';
      }
    }, 200);
  }

  function _openPickerShortcut(kind) {
    _close();
    try {
      if (kind === 'cookbook') {
        if (window.cookbookModule && typeof window.cookbookModule.open === 'function') window.cookbookModule.open();
        else {
          const btn = document.getElementById('tool-cookbook-btn') || document.getElementById('rail-cookbook');
          if (btn) btn.click(); else location.hash = '#cookbook';
        }
      } else if (kind === 'settings') {
        if (settingsModule && typeof settingsModule.open === 'function') settingsModule.open();
      } else if (window.adminModule && typeof window.adminModule.open === 'function') window.adminModule.open('services');
      else if (settingsModule && typeof settingsModule.open === 'function') settingsModule.open('services');
    } catch (_) {}
  }

  let _localProbe = {};
  let _localProbeFetchedAt = 0;
  const _LOCAL_PROBE_TTL_MS = 5000;
  let _pickerLoading = false;
  let _pickerLoadSeq = 0;

  async function _refreshLocalProbe() {
    try { if (window.__odysseusChatBusy || Date.now() < (window.__odysseusChatBusyUntil || 0)) return; } catch (_) {}
    const now = Date.now();
    if (now - _localProbeFetchedAt < _LOCAL_PROBE_TTL_MS) return;
    _localProbeFetchedAt = now;
    try {
      const r = await fetch('/api/model-endpoints/probe-local', { credentials: 'same-origin' });
      if (r.ok) _localProbe = (await r.json()) || {};
    } catch (_) {}
  }

  function _getAllModels() {
    const items = (window.modelsModule && window.modelsModule.getCachedItems) ? window.modelsModule.getCachedItems() : [];
    const result = [];
    const seen = new Set();
    items.forEach(item => {
      const epOffline = !!item.offline;
      const allModels = (item.models || []).concat(item.models_extra || []);
      const allDisplay = (item.models_display || []).concat(item.models_extra_display || []);
      const probeResult = item.endpoint_id ? _localProbe[item.endpoint_id] : null;
      const isLocalDead = !!(probeResult && probeResult.alive === false);
      const isApiEndpoint = item.category && item.category !== 'local';
      allModels.forEach((mid, i) => {
        const seenKey = isApiEndpoint ? `${item.endpoint_id || item.url || item.endpoint_name || 'api'}::${mid}` : mid;
        if (seen.has(seenKey)) return;
        seen.add(seenKey);
        result.push({
          key: seenKey,
          mid,
          display: (allDisplay[i] || mid).split('/').pop(),
          url: item.url,
          endpointId: item.endpoint_id,
          epName: item.endpoint_name || '',
          category: item.category || '',
          providerText: [item.endpoint_name || '', item.category || '', item.host || '', item.url || ''].filter(Boolean).join(' '),
          stale: isLocalDead || epOffline,
          staleReason: epOffline ? (item.ping_error || 'endpoint offline') : (isLocalDead ? (probeResult.error || 'not responding') : ''),
          offline: epOffline,
        });
      });
    });
    const general = result.find(m => m.mid === MOBS_GENERAL_MODEL && !m.stale);
    const coder = result.find(m => m.mid === MOBS_CODER_MODEL && !m.stale);
    if (general && coder) {
      result.unshift({
        key: MOBS_AUTO_MODEL_ID,
        mid: MOBS_AUTO_MODEL_ID,
        display: MOBS_AUTO_DISPLAY,
        url: general.url,
        endpointId: general.endpointId,
        epName: 'Automatic routing',
        category: 'local',
        providerText: 'MOBS Auto automatic routing qwen3 coder',
        stale: false,
        offline: false,
      });
    }
    return sortModelObjects(result);
  }

  function _hasModelCache() {
    try { return !!(window.modelsModule && window.modelsModule.getCachedItems && (window.modelsModule.getCachedItems() || []).length); }
    catch (_) { return false; }
  }

  function _renderLoading(text = 'Loading models…') {
    listEl.innerHTML = '';
    listEl.classList.remove('is-empty');
    listEl.classList.add('is-loading');
    menu.classList.remove('no-models');
    if (search) search.placeholder = text;
    let row = null;
    try { row = spinnerModule.createLoadingRow(text, 15); }
    catch (_) {
      row = document.createElement('div');
      row.className = 'model-switch-empty';
      row.textContent = text;
    }
    row.classList.add('model-picker-loading-row');
    listEl.appendChild(row);
  }

  async function _refreshPickerModels({ force = false, showLoading = false } = {}) {
    if (!window.modelsModule || typeof window.modelsModule.refreshModels !== 'function') return;
    const seq = ++_pickerLoadSeq;
    _pickerLoading = true;
    if (showLoading) _renderLoading(force ? 'Refreshing models…' : 'Loading models…');
    try {
      await window.modelsModule.refreshModels(force);
      await _refreshLocalProbe();
    } finally {
      if (seq === _pickerLoadSeq) {
        _pickerLoading = false;
        listEl.classList.remove('is-loading');
      }
    }
  }

  const _PROVIDER_NAMES = { 'qwen': 'Qwen', 'openai': 'OpenAI', 'anthropic': 'Anthropic', 'google': 'Google', 'mistralai': 'Mistral', 'meta': 'Llama', 'meta-llama': 'Llama', 'deepseek': 'DeepSeek', 'deepseek-ai': 'DeepSeek', 'other': 'Other' };
  function _providerDisplayName(slug) { return _PROVIDER_NAMES[slug] || slug.charAt(0).toUpperCase() + slug.slice(1).replace(/-/g, ' '); }
  function _providerSlug(mid) {
    if (mid === MOBS_AUTO_MODEL_ID) return 'mobs-auto';
    const slash = mid.indexOf('/');
    return slash > 0 ? mid.substring(0, slash) : 'other';
  }
  function _providerGroupKey(m) { return (m && m.category && m.category !== 'local' && m.epName) ? `~endpoint:${m.epName}` : _providerSlug((m && m.mid) || ''); }
  function _providerGroupName(key) { if (String(key || '').startsWith('~endpoint:')) return String(key).slice('~endpoint:'.length); return key === 'mobs-auto' ? MOBS_AUTO_DISPLAY : _providerDisplayName(key); }
  const _collapsedProviders = new Set(_loadList('odysseus-model-collapsed'));
  let _justExpandedProvider = null;

  function _populate(filter) {
    listEl.innerHTML = '';
    listEl.classList.remove('is-loading');
    const all = _getAllModels();
    const q = (filter || '').trim().toLowerCase();
    const hasAnyModel = all.length > 0;
    listEl.classList.toggle('is-empty', !hasAnyModel);
    menu.classList.toggle('no-models', !hasAnyModel);
    if (search) search.placeholder = hasAnyModel ? 'Search models…' : 'No models connected';
    if (searchRow) searchRow.classList.toggle('searching', !!q);
    if (!hasAnyModel) return;
    const byId = new Map();
    const byKey = new Map();
    all.forEach(m => { const key = _pickerModelKey(m); if (key && !byKey.has(key)) byKey.set(key, m); if (!byId.has(m.mid)) byId.set(m.mid, m); });
    const favs = _loadFavorites();
    function _addSection(label) { const el = document.createElement('div'); el.className = 'mp-section-label'; el.textContent = label; listEl.appendChild(el); }
    function _addEmpty(text) { const empty = document.createElement('div'); empty.className = 'model-switch-empty'; empty.textContent = text; listEl.appendChild(empty); }
    function _addRow(m) {
      const row = document.createElement('div');
      row.className = 'model-switch-item';
      if (m.stale) { row.classList.add('model-switch-stale'); row.style.opacity = '0.45'; row.title = `Local server appears offline: ${m.staleReason}. Click to try anyway.`; }
      const _mlogo = m.mid === MOBS_AUTO_MODEL_ID ? '' : providerLogo(m.mid);
      if (_mlogo) { const logoSpan = document.createElement('span'); logoSpan.className = 'provider-logo'; logoSpan.style.opacity = '0.6'; logoSpan.innerHTML = _mlogo; row.appendChild(logoSpan); }
      const nameSpan = document.createElement('span'); nameSpan.className = 'mp-model-name'; nameSpan.textContent = m.display; nameSpan.title = m.display; row.appendChild(nameSpan);
      const epSpan = document.createElement('span'); epSpan.className = 'model-switch-ep'; const _epDisplay = m.epName && !m.display.toLowerCase().includes(m.epName.toLowerCase().split('/').pop()) ? m.epName : ''; epSpan.textContent = _epDisplay; row.appendChild(epSpan);
      const favDot = document.createElement('button');
      if (m.mid === MOBS_AUTO_MODEL_ID) favDot.style.visibility = 'hidden';
      favDot.type = 'button';
      favDot.className = 'mp-fav-dot' + (favs.includes(m.mid) ? ' active' : '');
      favDot.textContent = '●';
      const _setFavState = (on) => { favDot.classList.toggle('active', on); favDot.title = on ? 'Remove from favorites' : 'Add to favorites'; favDot.setAttribute('aria-label', favDot.title); favDot.setAttribute('aria-pressed', on ? 'true' : 'false'); };
      _setFavState(favs.includes(m.mid));
      favDot.addEventListener('click', (e) => { e.stopPropagation(); const nowFav = _toggleFavorite(m.mid); _setFavState(nowFav); });
      row.appendChild(favDot);
      row.addEventListener('click', () => _pick(m));
      listEl.appendChild(row);
    }
    if (q) {
      const matches = all.filter(m => [m.mid, m.display, m.epName, m.providerText, _providerDisplayName(_providerSlug(m.mid))].filter(Boolean).join(' ').toLowerCase().includes(q));
      if (matches.length === 0) _addEmpty('No matching models'); else matches.forEach(_addRow);
      return;
    }
    const shown = new Set();
    const favModels = favs.map(id => byKey.get(id) || byId.get(id)).filter(Boolean);
    if (favModels.length) { _addSection('Favorites'); favModels.forEach(m => { shown.add(_pickerModelKey(m)); _addRow(m); }); }
    if (all.length > BROWSE_ALL_LIMIT) {
      const recentModels = _loadRecent().map(id => byKey.get(id) || byId.get(id)).filter(Boolean).filter(m => !shown.has(_pickerModelKey(m))).slice(0, RECENT_MAX);
      if (recentModels.length) { _addSection('Recent'); recentModels.forEach(m => { shown.add(_pickerModelKey(m)); _addRow(m); }); }
    }
    const rest = all.filter(m => !shown.has(_pickerModelKey(m)));
    if (all.length <= BROWSE_ALL_LIMIT) {
      if (rest.length) { if (shown.size) _addSection('All models'); rest.forEach(_addRow); }
    } else {
      const groups = new Map();
      rest.forEach(m => { const slug = _providerGroupKey(m); if (!groups.has(slug)) groups.set(slug, []); groups.get(slug).push(m); });
      const sorted = [...groups.keys()].sort((a, b) => _providerGroupName(a).localeCompare(_providerGroupName(b)));
      sorted.forEach(provider => {
        const models = groups.get(provider);
        const isCollapsed = _collapsedProviders.has(provider);
        const header = document.createElement('div');
        header.className = 'mp-provider-header';
        header.innerHTML = `<svg class="mp-provider-chevron${isCollapsed ? ' collapsed' : ''}" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg><span class="mp-provider-name">${_providerGroupName(provider)}</span><span class="mp-provider-count">${models.length}</span>`;
        header.addEventListener('click', (e) => { e.stopPropagation(); if (_collapsedProviders.has(provider)) { _collapsedProviders.delete(provider); _justExpandedProvider = provider; } else { _collapsedProviders.add(provider); _justExpandedProvider = null; } _saveList('odysseus-model-collapsed', [..._collapsedProviders]); const st = listEl.scrollTop; _populate(''); listEl.scrollTop = st; });
        listEl.appendChild(header);
        if (!isCollapsed) { const group = document.createElement('div'); group.className = 'mp-provider-group' + (_justExpandedProvider === provider ? ' mp-just-expanded' : ''); models.forEach(m => { _addRow(m); group.appendChild(listEl.lastElementChild); }); listEl.appendChild(group); if (_justExpandedProvider === provider) _justExpandedProvider = null; }
      });
    }
  }

  async function _pick(m) {
    _defaultPendingSeq++;
    try { window.__odysseusLastPickedRoute = { model: m.mid || '', endpoint_url: m.url || '', endpoint_id: m.endpointId || '', display: m.display || m.mid || '', picked_at: Date.now() }; } catch (_) {}
    let switchDone = null;
    const switchPromise = new Promise(resolve => { switchDone = resolve; });
    try { window.__odysseusModelSwitchPromise = switchPromise; } catch (_) {}
    const finishSwitch = () => { try { if (switchDone) switchDone(); if (window.__odysseusModelSwitchPromise === switchPromise) delete window.__odysseusModelSwitchPromise; } catch (_) {} };
    const currentSessionId = _deps.getCurrentSessionId();
    const _pendingChat = _deps.getPendingChat();
    if (m && m.mid) _pushRecent(_pickerModelKey(m) || m.mid);
    try { document.dispatchEvent(new CustomEvent('odysseus:model-picked', { detail: m })); } catch {}
    if (document.activeElement) document.activeElement.blur();
    _close();
    if (window.innerWidth >= 768) { const _ta = document.getElementById('message'); if (_ta) setTimeout(() => _ta.focus(), 50); }
    if (!currentSessionId && _pendingChat) {
      _deps.setPendingChat({ url: m.url, modelId: m.mid, endpointId: m.endpointId, source: 'manual' });
      updateModelPicker();
      uiModule.showToast(`Using ${m.display}`);
      finishSwitch();
      return;
    } else if (!currentSessionId) {
      try { await _deps.createDirectChat(m.url, m.mid, m.endpointId); }
      catch (e) { uiModule.showError('Failed to start chat: ' + e); finishSwitch(); return; }
    } else {
      const sessions = _deps.getSessions();
      const s = sessions.find(x => x.id === currentSessionId);
      if (s) { s.model = m.mid; s.endpoint_url = m.url; s.endpoint_id = m.endpointId || s.endpoint_id || ''; }
      updateModelPicker();
      const fd = new FormData();
      fd.append('model', m.mid);
      fd.append('endpoint_url', m.url);
      if (m.endpointId) fd.append('endpoint_id', m.endpointId);
      try {
        const res = await fetch(`${API_BASE}/api/session/${currentSessionId}`, { method: 'PATCH', body: fd });
        if (!res.ok) { uiModule.showError('Failed to set model'); finishSwitch(); return; }
      } catch (e) { uiModule.showError('Failed to set model: ' + e); finishSwitch(); return; }
    }
    updateModelPicker();
    if (window.refreshChatContextHeader) window.refreshChatContextHeader('model-pick');
    uiModule.showToast(`Using ${m.display}`);
    finishSwitch();
  }

  btn.addEventListener('pointerdown', (e) => e.stopPropagation());
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (menu.classList.contains('hidden') || menu.classList.contains('closing')) {
      menu.classList.remove('closing', 'hidden');
      const hasCache = _hasModelCache();
      if (hasCache) _populate(''); else _renderLoading('Loading models…');
      if (window.modelsModule && window.modelsModule.refreshModels) {
        _refreshPickerModels({ force: hasCache, showLoading: !hasCache }).then(() => { if (!menu.classList.contains('hidden')) _populate(search.value || ''); updateModelPicker(); }).catch(() => {});
      }
      if (window.innerWidth >= 768) search.focus();
      const _scrollBtn = document.getElementById('scroll-bottom-btn');
      if (_scrollBtn) _scrollBtn.style.display = 'none';
    } else _close();
  });
  search.addEventListener('input', () => { if (!_pickerLoading) _populate(search.value); });
  search.addEventListener('click', (e) => e.stopPropagation());
  if (refreshBtn) refreshBtn.addEventListener('click', async (e) => { e.stopPropagation(); refreshBtn.disabled = true; refreshBtn.classList.add('spinning'); try { await _refreshPickerModels({ force: true, showLoading: true }); if (!menu.classList.contains('hidden')) _populate(search.value || ''); updateModelPicker(); } catch (_) { uiModule.showToast('Model refresh failed'); } finally { refreshBtn.disabled = false; refreshBtn.classList.remove('spinning'); } });
  search.addEventListener('keydown', (e) => _handlePickerKeydown(e, listEl, '.model-switch-item', _close));
  const addModelsBtn = document.getElementById('model-picker-add-models-btn');
  if (addModelsBtn) addModelsBtn.addEventListener('click', (e) => { e.stopPropagation(); _openPickerShortcut('models'); });
  document.addEventListener('click', (e) => { if (!menu.classList.contains('hidden') && !wrap.contains(e.target)) _close(); });
}

export function updateModelPicker() {
  if (!_deps) return;
  const label = document.getElementById('model-picker-label');
  if (!label) return;
  const wrap = document.getElementById('model-picker-wrap');
  if (window.groupModule && window.groupModule.isActive()) { if (wrap) wrap.style.display = 'none'; return; }
  if (wrap) { wrap.style.display = ''; wrap.style.opacity = ''; wrap.style.pointerEvents = ''; }
  const currentSessionId = _deps.getCurrentSessionId();
  const sessions = _deps.getSessions();
  const _pendingChat = _deps.getPendingChat();
  const s = sessions.find(x => x.id === currentSessionId);
  let modelId = null;
  if (s && s.model) modelId = s.model;
  else if (_pendingChat && _pendingChat.modelId) {
    modelId = _pendingChat.modelId;
    if (_pendingChat.source === 'fallback' && !_modelExists(modelId, _pendingChat.url || '')) { _deps.setPendingChat(null); modelId = null; }
  }
  if (!modelId && !currentSessionId && !_pendingChat && _deps.setPendingChat) {
    let cachedDefault = null;
    try { cachedDefault = window.__odysseusDefaultChat || null; } catch (_) {}
    if (!cachedDefault || !cachedDefault.endpoint_url || !cachedDefault.model) {
      try { cachedDefault = JSON.parse(localStorage.getItem('odysseus-default-chat-cache') || 'null'); } catch (_) {}
    }
    if (cachedDefault && cachedDefault.endpoint_url && cachedDefault.model) {
      modelId = cachedDefault.model;
      _deps.setPendingChat({ url: cachedDefault.endpoint_url, modelId, endpointId: cachedDefault.endpoint_id || '', source: 'default' });
    }
  }
  if (modelId && !currentSessionId && _pendingChat && _pendingChat.source !== 'manual' && modelId !== MOBS_AUTO_MODEL_ID && window.modelsModule && window.modelsModule.getCachedItems) {
    const items = window.modelsModule.getCachedItems();
    const allAvailable = [];
    items.forEach(item => { if (!item.offline) (item.models || []).concat(item.models_extra || []).forEach(m => allAvailable.push(m)); });
    if (allAvailable.length > 0 && !allAvailable.includes(modelId)) {
      const fallback = items.find(item => !item.offline && (item.models || []).length > 0);
      if (fallback) { modelId = fallback.models[0]; _deps.setPendingChat({ url: fallback.url, modelId, endpointId: fallback.endpoint_id, source: 'fallback' }); }
    }
  }
  const latestPending = _deps.getPendingChat && _deps.getPendingChat();
  if (!currentSessionId && !_autoSelectingDefault && window.modelsModule && window.modelsModule.getCachedItems && (!modelId || (latestPending && latestPending.source === 'fallback'))) _ensureDefaultPendingChat();
  const displayName = _displayModelName(modelId);
  label.title = modelId === MOBS_AUTO_MODEL_ID ? MOBS_AUTO_DISPLAY : (modelId || '');
  const logo = modelId && modelId !== MOBS_AUTO_MODEL_ID ? providerLogo(modelId) : null;
  if (logo) label.innerHTML = '<span class="model-picker-logo">' + logo + '</span> ' + displayName;
  else label.textContent = displayName;
}
