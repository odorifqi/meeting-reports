/* Meeting Report v1.6 UI (was Meeting Notes v1.2). Plain JS, no build step, no external requests.
   Screens follow the approved hi-fi prototype: S1 Riwayat, S2 Rapat baru, S3/S3b progres,
   S4 tinjau / S4b edit transkrip, S4c bandingkan, S5 meringkas, S6 detail (transkrip,
   ringkasan, audio), S6e/S6f riwayat versi, S7 pengaturan, sheets M1 M2 M2b M4 M5. */
(function () {
'use strict';
const D = window.MNDiff;
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = o => JSON.parse(JSON.stringify(o));

/* ------------------------------------------------------------------ icons */
const P = {
  list: '<path d="M5.5 4h8M5.5 8h8M5.5 12h8"/><path d="M2.5 4h0M2.5 8h0M2.5 12h0" stroke-width="2"/>',
  plus: '<path d="M8 3v10M3 8h10"/>',
  gear: '<g transform="scale(.6667)" stroke-width="2.25"><path d="M10.3 2.6h3.4l.5 2.6a7.4 7.4 0 0 1 1.9 1.1l2.5-.9 1.7 2.9-2 1.7a7.6 7.6 0 0 1 0 2.2l2 1.7-1.7 2.9-2.5-.9a7.4 7.4 0 0 1-1.9 1.1l-.5 2.6h-3.4l-.5-2.6a7.4 7.4 0 0 1-1.9-1.1l-2.5.9-1.7-2.9 2-1.7a7.6 7.6 0 0 1 0-2.2l-2-1.7 1.7-2.9 2.5.9a7.4 7.4 0 0 1 1.9-1.1z"/><circle cx="12" cy="12" r="3"/></g>',
  grip: '<path d="M6 3.5h0M10 3.5h0M6 8h0M10 8h0M6 12.5h0M10 12.5h0" stroke-width="2.2"/>',
  ins: '<path d="M2.5 3.5h11M2.5 12.5h11"/><path d="M8 5.8v4.4M5.8 8h4.4"/>',
  search: '<circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2 13.5 13.5"/>',
  play: '<path d="M5 3.2v9.6L12.6 8z" fill="currentColor" stroke="none"/>',
  pause: '<path d="M5.5 3.5v9M10.5 3.5v9" stroke-width="2.4"/>',
  lock: '<rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5.2a2.5 2.5 0 0 1 5 0V7"/>',
  unlock: '<rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5.2a2.5 2.5 0 0 1 4.8-1"/>',
  spark: '<path d="M8 1.8 9.4 6.6 14.2 8 9.4 9.4 8 14.2 6.6 9.4 1.8 8 6.6 6.6z" fill="currentColor" stroke="none"/>',
  warn: '<path d="M8 2.3 14.2 13.2H1.8z"/><path d="M8 6.6v3M8 11.2v.3"/>',
  check: '<path d="M3.5 8.5 6.5 11.5 12.5 4.5"/>',
  x: '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
  left: '<path d="M10 3.5 5.5 8l4.5 4.5"/>',
  up: '<path d="M4 10l4-4 4 4"/>', down: '<path d="M4 6l4 4 4-4"/>',
  folder: '<path d="M2 4.5h4l1.5 1.5H14v6.5H2z"/>',
  dl: '<path d="M8 2.5v7.5M4.8 7 8 10.2 11.2 7M3 13.2h10"/>',
  trash: '<path d="M3 4.5h10M6.2 4.5V3h3.6v1.5M4.5 4.5l.7 9h5.6l.7-9"/>',
  pencil: '<path d="M10.5 2.8l2.7 2.7L6 12.7l-3.2.5.5-3.2z"/>',
  doc: '<path d="M4 2h5.5L12 4.5V14H4z"/><path d="M6 7h4M6 9.5h4M6 12h2.5"/>',
  wave: '<path d="M2 8v0M4.5 5.5v5M7 3v10M9.5 5v6M12 6.5v3M14 8v0"/>',
  revert: '<path d="M3.5 6.5h6a3 3 0 0 1 0 6H6"/><path d="M6 4 3.5 6.5 6 9"/>',
  clock: '<circle cx="8" cy="8" r="5.6"/><path d="M8 5v3.2l2 1.3"/>',
  info: '<circle cx="8" cy="8" r="5.8"/><path d="M8 7.3v3.5M8 5.2v.2"/>',
  person: '<circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c.6-2.6 2.6-4 5-4s4.4 1.4 5 4"/>',
  cmp: '<rect x="2" y="3" width="5" height="10" rx="1"/><rect x="9" y="3" width="5" height="10" rx="1"/>',
  merge: '<path d="M4 3v3.5a3 3 0 0 0 3 3h5M12 3v10"/>',
  split: '<path d="M8 2.5v11M3 5.5h3M10 10.5h3"/>',
  tray: '<path d="M2.5 9.5h3l1 2h3l1-2h3V13h-11z"/><path d="M8 2.5v6M5.5 6 8 8.5 10.5 6"/>',
  key: '<circle cx="5.5" cy="10.5" r="2.6"/><path d="M7.4 8.6 13 3M11 5l1.6 1.6"/>',
  eye: '<path d="M1.8 8S4 3.8 8 3.8 14.2 8 14.2 8 12 12.2 8 12.2 1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.8"/>',
  send: '<path d="M2.5 8 13.5 3l-4 10.5-2-4.5z"/>'
};
const ic = (n, c = '') => `<svg class="ic ${c}" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${P[n] || ''}</svg>`;

/* ------------------------------------------------------------------ formatting */
const pad = n => String(n).padStart(2, '0');
function fmtTs(sec) { sec = Math.max(0, Math.floor(sec || 0)); return `${pad(Math.floor(sec / 3600))}:${pad(Math.floor(sec % 3600 / 60))}:${pad(sec % 60)}`; }
function fmtDur(sec) { if (sec == null) return '–'; sec = Math.max(0, Math.round(sec)); const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60; return `${h}:${pad(m)}:${pad(s)}`; }
/* ------------------------------------------------------------------ language (v1.7) */
// NOTE: dictionary entries are trusted HTML; values passed in vars must be escaped by the caller
const I18N = window.MR_I18N || {};
const osLang = () => (/^id\b/i.test(navigator.language || '') ? 'id' : 'en');
let UI_LANG = osLang();
function setLang(pref) {
  UI_LANG = pref === 'id' || pref === 'en' ? pref : osLang();
  document.documentElement.lang = UI_LANG;
}
function _t(key, vars) {
  const e = I18N[key];
  let s = e ? (e[UI_LANG] != null ? e[UI_LANG] : e.id) : key;
  if (s && typeof s === 'object') s = s[new Intl.PluralRules(UI_LANG).select(Number(vars && vars.n) || 0)] || s.other;
  return vars ? String(s).replace(/\{(\w+)\}/g, (m, k) => (vars[k] != null ? vars[k] : m)) : s;
}
const locale = () => (UI_LANG === 'id' ? 'id-ID' : 'en-GB');
const monShort = d => new Intl.DateTimeFormat(locale(), { month: 'short' }).format(d).replace('.', '');
function fmtDate(iso) { if (!iso) return '–'; const d = new Date(iso); return `${d.getDate()} ${monShort(d)} ${d.getFullYear()}`; }
function fmtDT(iso) { if (!iso) return '–'; const d = new Date(iso); return `${d.getDate()} ${monShort(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`; }
function fmtClock(d) { d = d || new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; }
const num = n => Number(n || 0).toLocaleString(UI_LANG === 'id' ? 'id-ID' : 'en-US');
const dec = (x, d = 1) => Number(x).toFixed(d).replace('.', UI_LANG === 'id' ? ',' : '.');
const tsec = t => { const a = String(t).split(':').map(Number); return a[0] * 3600 + a[1] * 60 + (a[2] || 0); };
const LANG_KEYS = ['id', 'en', ''];
const langName = k => _t(k === 'id' ? 'lang.id' : k === 'en' ? 'lang.en' : 'lang.auto');
const words = segs => segs.reduce((a, s) => a + (s.text || '').split(/\s+/).filter(Boolean).length, 0);

/* ------------------------------------------------------------------ API */
async function api(path, opts = {}) {
  const o = { method: opts.method || 'GET', headers: { 'X-UI-Lang': UI_LANG }, credentials: 'same-origin' };
  if (opts.body !== undefined) {
    if (opts.raw) { o.body = opts.body; Object.assign(o.headers, opts.headers || {}); }
    else { o.body = JSON.stringify(opts.body); o.headers['Content-Type'] = 'application/json'; }
  }
  const r = await fetch(path, o);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  if (!r.ok) {
    const msg = (data && data.detail) || _t('err.status', { status: r.status });
    const err = new Error(typeof msg === 'string' ? msg : _t('err.refused'));
    err.status = r.status;
    throw err;
  }
  return data;
}
const post = (p, b) => api(p, { method: 'POST', body: b || {} });
const audioUrl = (mid, kind) => `/api/meetings/${encodeURIComponent(mid)}/audio/${kind}`;

/* ------------------------------------------------------------------ state */
const S = {
  route: { name: 'list' },
  state: null,            // /api/state
  meetings: [], q: '', fstat: 'all', root: '',
  m: null,                // detail of current meeting
  ver: null,              // transcript version shown in S6
  vsel: 'latest', s6q: '', s6spk: 'all', hl: null,
  sum: null, ssel: 'latest',
  ed: null,               // editor state
  diff: { mode: 'side', only: true, tags: true, cur: 0, left: 'whisper', revs: [] },
  hist: { left: null, right: 'latest', L: null, R: null },
  shist: { left: null, right: 'latest', L: null, R: null },
  modal: null, ctx: '', prev: null, prevOpen: false,
  toast: null, s2: null, settings: null, sendlog: [], keyEdit: false, keyMsg: '',
  recent: [], logOpen: false, busy: false,
};
let theme = 'system';
try { theme = localStorage.getItem('mn-theme') || 'system'; } catch (e) { /* storage blocked */ }
function applyTheme(t) {
  theme = t || 'system';
  if (theme === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('mn-theme', theme); } catch (e) { /* ignore */ }
}
applyTheme(theme);

function toast(text, undo, kind) {
  S.toast = { text, undo, kind: kind || 'ok' };
  clearTimeout(toast.h);
  toast.h = setTimeout(() => { S.toast = null; patchToast(); }, undo || text.length > 60 ? 6000 : kind === 'bad' ? 5000 : 2800);
  patchToast();
}
function toastHTML() {
  const t = S.toast; if (!t) return '';
  return `<div class="toast${t.kind === 'bad' ? ' bad' : ''}" role="${t.kind === 'bad' ? 'alert' : 'status'}">${ic(t.kind === 'bad' ? 'warn' : t.kind === 'info' ? 'info' : 'check')}<span>${esc(t.text)}</span>${t.undo ? `<button class="btn" data-act="undo">${_t('undo')}</button>` : ''}</div>`;
}
// the toast is patched on its own so it never re-renders a long transcript
function patchToast() {
  const w = document.querySelector('#app .win'); if (!w) return;
  const old = w.querySelector(':scope > .toast'); if (old) old.remove();
  if (S.toast) w.insertAdjacentHTML('beforeend', toastHTML());
}
function fail(e) { toast(e && e.message ? e.message : String(e), null, 'bad'); }
/* AI provider labels (Usulan 14). The key itself never reaches the browser. */
const AI = () => (S.state && S.state.ai) || { provider: 'anthropic', provider_short: 'Anthropic', provider_name: 'Anthropic (Claude)', local: false, model: '' };
const toAI = () => AI().local ? _t('ai.local_model') : esc(AI().provider_name);
/* titles become Finder folder names: / : \ are not allowed (Usulan 11) */
const BAD_T = /[\/:\\]/, BAD_TG = /[\/:\\]/g, TITLE_MAX = 80;
function titleMsg(v) {
  if (!String(v || '').trim()) return _t('title.empty');
  if (BAD_T.test(v)) return _t('title.bad_char');
  if (v.length > TITLE_MAX) return _t('title.too_long', { n: TITLE_MAX });
  return '';
}
function titleInput(t, msgId) {
  let msg = '';
  if (BAD_T.test(t.value)) {
    const pos = t.selectionStart || t.value.length;
    const before = t.value.slice(0, pos).replace(BAD_TG, '').length;
    t.value = t.value.replace(BAD_TG, '');
    try { t.setSelectionRange(before, before); } catch (e) { /* not focused */ }
    msg = _t('title.bad_char');
    titleInput.bad = Date.now();
  }
  // keep the "not allowed" note on screen a moment after the next keystrokes
  if (!msg && Date.now() - (titleInput.bad || 0) < 4000) msg = _t('title.bad_char');
  if (!msg) msg = titleMsg(t.value);
  if (!msg && t.value.length >= TITLE_MAX) msg = _t('title.max', { n: TITLE_MAX });
  const el = document.getElementById(msgId);
  if (el) { el.innerHTML = msg ? `${ic('warn', 'sm')}${esc(msg)}` : ''; el.hidden = !msg; }
  return t.value;
}

/* ------------------------------------------------------------------ routing */
function parseHash() {
  const h = location.hash.replace(/^#\/?/, '');
  const p = h.split('/').map(decodeURIComponent);
  if (!h || p[0] === 'riwayat') return { name: 'list' };
  if (p[0] === 'baru') return { name: 'new' };
  if (p[0] === 'pengaturan') return { name: 'settings' };
  if (p[0] === 'rapat' && p[1]) return { name: 'meeting', id: p[1], view: p[2] || 'auto' };
  return { name: 'list' };
}
function go(hash) { if (location.hash === hash) route(); else location.hash = hash; }
const mhash = (id, view) => `#/rapat/${encodeURIComponent(id)}/${view}`;

window.addEventListener('hashchange', route);

async function route() {
  stopAudio();
  S.modal = S.modalNext || null; S.modalNext = null; if (!S.modal) S.prevOpen = false;
  const r = parseHash();
  S.route = r; S.loadErr = null; S.editTitle = false;
  // an undo belongs to the screen it was made on
  if (S.toast && S.toast.undo) { S.toast = null; clearTimeout(toast.h); }
  try {
    if (r.name === 'list') { await loadList(); }
    else if (r.name === 'new') { if (!S.s2) await initNew(); }
    else if (r.name === 'settings') { await loadSettings(); }
    else if (r.name === 'meeting') { await openMeeting(r); }
  } catch (e) { S.loadErr = e.message || String(e); }
  render();
}
// a screen that could not load gets a way out instead of an endless spinner
function loadingHTML() {
  if (S.loadErr) return `<div class="loading"><div class="lerr"><span class="glyph bad">${ic('warn', 'lg')}</span><b>${_t('load.fail')}</b><span class="muted">${esc(S.loadErr)}</span><div style="display:flex;gap:8px;justify-content:center"><button class="btn" data-go="#/riwayat">${ic('left')}${_t('load.back')}</button><button class="btn pri" data-act="reload">${_t('retry')}</button></div></div></div>`;
  return '<div class="loading"><span class="spinner lg"></span></div>';
}

async function loadList() {
  const d = await api(`/api/meetings?q=${encodeURIComponent(S.q)}&status=${S.fstat === 'all' ? '' : S.fstat}`);
  S.meetings = d.meetings; S.root = d.root;
}
async function loadState() { S.state = await api('/api/state'); setLang(S.state.ui_language); }

async function openMeeting(r) {
  const m = await api(`/api/meetings/${encodeURIComponent(r.id)}`);
  const prevId = S.m && S.m.id;
  S.m = m;
  if (prevId !== m.id) { S.vsel = 'latest'; S.ssel = 'latest'; S.s6q = ''; S.s6spk = 'all'; S.ed = null; S.sum = null; S.ctx = ''; S.repLang = null; }
  let view = r.view;
  if (view === 'auto') {
    view = { queued: 'progres', transcribing: 'progres', failed: 'progres', awaiting_review: 'tinjau', summarizing: 'meringkas' }[m.status] || (sugBusy(m) ? 'saran' : 'transkrip');
    history.replaceState(null, '', mhash(m.id, view));
    S.route.view = view;
  }
  if (view === 'transkrip') await loadVersion(S.vsel);
  if (view === 'ringkasan') await loadSummary(S.ssel);
  if (view === 'audio') await syncLoad(true);
  if (view === 'saran' && !sugBusy(m) && (m.suggest_job || {}).state !== 'failed') {
    view = 'edit'; history.replaceState(null, '', mhash(m.id, view)); S.route.view = view;
  }
  if (view === 'tinjau' || view === 'edit') { if (!S.ed || S.ed.mid !== m.id || S.ed.stale) await loadEditor(view); }
  if (view === 'bandingkan' && (!S.ed || S.ed.mid !== m.id)) await loadEditor(m.transcript_rev ? 'edit' : 'tinjau');
  if (view === 'bandingkan') await loadDiffLeft();
  if (view === 'riwayat-transkrip') await loadHist('tr');
  if (view === 'riwayat-ringkasan') await loadHist('sum');
}

/* ------------------------------------------------------------------ SSE */
let es = null;
function connectEvents() {
  es = new EventSource('/api/events');
  es.onmessage = ev => { let d; try { d = JSON.parse(ev.data); } catch (e) { return; } onEvent(d); };
}
let refreshT = null;
function onEvent(ev) {
  clearTimeout(refreshT);
  const cur = S.route.name === 'meeting' && S.m && S.m.id === ev.mid;
  if (ev.kind === 'progress' && cur && S.m) {
    const prev = S.m.progress || {};
    const durs = ev.duration_sec !== undefined && (ev.duration_sec !== S.m.duration_sec || ev.clean_sec !== S.m.clean_sec);
    S.m.progress = ev.progress;
    if (ev.duration_sec !== undefined) { S.m.duration_sec = ev.duration_sec; S.m.clean_sec = ev.clean_sec; }
    if (S.m.status === 'queued') S.m.status = 'transcribing';
    // the step list (✓ Decode audio, ✓ Remove silence, ...) only changes with the phase or durations
    if (S.route.view === 'progres' && (durs || prev.phase !== ev.progress.phase)) render(); else patchProgress();
  }
  if (ev.kind === 'log' && cur && S.m) { (S.m.log = S.m.log || []).push({ t: fmtClock(new Date()) + ':' + pad(new Date().getSeconds()), text: ev.text }); patchLog(); }
  if (ev.kind === 'suggest' && cur && ev.job) {
    S.m.suggest_job = ev.job;
    const v = S.route.view;
    if (ev.state === 'ready') {
      toast(_t(ev.job.partial ? 'sug.ready_partial' : 'sug.ready', { n: ev.count }), null, ev.job.partial ? 'info' : undefined);
      if (v === 'saran' || v === 'edit') { (async () => { await saveDraft(); if (S.ed) S.ed.stale = true; go(mhash(ev.mid, 'edit')); })(); return; }
    } else if (ev.state === 'failed' && v !== 'saran') toast(_t('sug.failed'), null, 'bad');
    if (v === 'saran' || v === 'edit') render();
  }
  refreshT = setTimeout(async () => {
    try {
      await loadState();
      if (S.route.name === 'list') await loadList();
      if (cur && (['status', 'done', 'queued', 'suggest'].includes(ev.kind) || (ev.kind === 'version' && S.route.view === 'audio'))) {
        const before = S.m.status;
        S.m = await api(`/api/meetings/${encodeURIComponent(ev.mid)}`);
        const v = S.route.view;
        if (before !== S.m.status) {
          if (S.m.status === 'awaiting_review' && v === 'progres') { S.ed = null; go(mhash(ev.mid, 'tinjau')); return; }
          if (S.m.status === 'done' && v === 'meringkas') { S.ssel = 'latest'; toast(_t('sum.done', { n: S.m.summary_count })); go(mhash(ev.mid, 'ringkasan')); return; }
          if (v === 'meringkas' && S.m.summary_error) { render(); return; }
          if (S.m.status === 'failed' && v === 'progres') { render(); return; }
        }
      }
      if (cur && S.route.view === 'audio') await syncLoad();
      render();
    } catch (e) { /* server restarting: ignore */ }
  }, 150);
}
function patchProgress() {
  const p = (S.m && S.m.progress) || {};
  const el = $('#pg-pct'); if (el) el.textContent = `${p.pct || 0}%`;
  const bar = $('#pg-bar'); if (bar) bar.style.width = `${p.pct || 0}%`;
  const part = $('#pg-part'); if (part) part.textContent = progTitle(p);
  const eta = $('#pg-eta'); if (eta) eta.textContent = etaText(p, S.m);
  const sj = $('#sj-bar'); if (sj) sj.style.width = `${p.pct || 0}%`;
}
function patchLog() { const el = $('#pg-log'); if (el) { el.innerHTML = logHTML(S.m.log); el.scrollTop = el.scrollHeight; } }

/* ------------------------------------------------------------------ shared bits */
const PILL = { queued: ['neutral', 'clock'], transcribing: ['info', 1], awaiting_review: ['warn', 'pencil'],
  awaiting_confirmation: ['warn', 'clock'], summarizing: ['info', 1], done: ['ok', 'doc'],
  transcript_only: ['neutral', 'doc'], failed: ['bad', 'x'] };
const statusName = s => _t('status.' + (PILL[s] ? s : 'queued'));
function pill(status, pct) {
  const m = PILL[status] || PILL.queued;
  return `<span class="pill p-${m[0]}">${m[1] === 1 ? '<span class="spinner" style="width:9px;height:9px;border-width:1.5px"></span>' : ic(m[1], 'sm')}${statusName(status)}${status === 'transcribing' && pct != null ? ` <span class="mono">${pct}%</span>` : ''}</span>`;
}
const claudePill = cs => `<span class="pill p-claude">${ic('spark', 'sm')}${_t('pill.ai')}${cs && cs.provider ? ` · ${esc(cs.provider)}` : ''}${cs && cs.accepted ? ` · ${_t('pill.ai_accepted', { n: cs.accepted })}` : ''}</span>`;
const stalePill = () => `<span class="pill p-warn">${ic('warn', 'sm')}${_t('pill.stale')}</span>`;
const v1Pill = () => `<span class="pill p-neutral">${_t('pill.v1')}</span>`;
function tb(l, r, back) { return `<header class="tb"><div class="tb-l">${back ? `<button class="iconb" data-go="${back}" aria-label="${_t('back')}">${ic('left')}</button>` : ''}${l}</div><div class="tb-r">${r || ''}</div></header>`; }
const ttl = (h, s) => `<div style="min-width:0"><h1>${h}</h1>${s ? `<div class="sub">${s}</div>` : ''}</div>`;
const sw = (act, on, label) => `<button class="sw" role="switch" aria-checked="${!!on}" data-act="${act}" aria-label="${esc(label)}"><span class="sr">${on ? _t('on') : _t('off')}</span></button>`;
const homeDir = p => String(p || '').replace(/^\/Users\/[^/]+/, '~');

function sidebar() {
  const r = S.route;
  const act = r.name === 'settings' ? 'set' : r.name === 'new' ? 'new' : 'list';
  const st = S.state || {};
  const cur = st.jobs && st.jobs.current;
  let job = '';
  if (cur) {
    const row = S.meetings.find(x => x.id === cur.mid) || (S.m && S.m.id === cur.mid ? S.m : null);
    const p = (row && row.progress) || {};
    const label = cur.kind === 'transcribe' ? _t('job.transcribe') : cur.kind === 'summary' ? _t('job.summary') : _t('job.suggest');
    job = `<button class="job" data-go="${mhash(cur.mid, 'auto')}"><span class="t"><span class="spinner" style="width:9px;height:9px;border-width:1.5px;color:var(--accent)"></span>${label}</span><span class="n">${esc(row ? row.title : cur.mid)}</span>${cur.kind === 'transcribe' ? `<div class="bar thin"><i id="sj-bar" style="width:${p.pct || 0}%"></i></div><span class="m">${p.chunks ? _t('job.part', { i: p.chunk, n: p.chunks, pct: p.pct || 0 }) : _t('job.prep')}</span>` : ''}</button>`;
  }
  const pend = st.jobs && st.jobs.pending && st.jobs.pending.length ? `<div class="sfoot" style="margin-top:6px">${ic('clock', 'sm')}<span>${_t('job.queued', { n: st.jobs.pending.length })}</span></div>` : '';
  return `<aside class="side">
  <button class="ni" data-go="#/riwayat" aria-current="${act === 'list'}">${ic('list')}${_t('nav.history')}<span class="ct">${S.meetings.length || ''}</span></button>
  <button class="ni" data-go="#/baru" aria-current="${act === 'new'}">${ic('plus')}${_t('nav.new')}</button>
  <button class="ni" data-go="#/pengaturan" aria-current="${act === 'set'}">${ic('gear')}${_t('nav.settings')}</button>
  ${job}${pend}
  <div class="sfoot">${ic('lock', 'sm')}<span>${_t('side.stored', { dir: esc(homeDir(S.root || (st.output_root || '~/Documents/Meeting Report'))) })}</span></div>
  ${st.version ? `<div class="sfoot" style="margin-top:4px">${ic('info', 'sm')}<span>${_t('side.version', { v: esc(st.version) })}</span></div>` : ''}
  </aside>`;
}

/* ------------------------------------------------------------------ S1 Riwayat */
function rowsHTML() {
  if (!S.meetings.length) return `<tr><td colspan="4" style="padding:30px;text-align:center;color:var(--fg-3)">${S.q ? _t('s1.no_match', { q: esc(S.q) }) : _t('s1.no_status')}</td></tr>`;
  return S.meetings.map(m => {
    const b = [m.stale ? stalePill() : '', m.claude ? claudePill() : '', m.v1 ? v1Pill() : ''].join('');
    const busy = ['queued', 'transcribing', 'failed'].includes(m.status);
    return `<tr class="rw" data-go="${mhash(m.id, 'auto')}" tabindex="0"><td><div class="tt">${esc(m.title)}${b}</div></td><td class="num">${fmtDate(m.created)}</td><td class="num">${busy ? '–' : fmtDur(m.duration_sec)}</td><td>${pill(m.status, m.progress && m.progress.pct)}</td></tr>`;
  }).join('');
}
function S1() {
  const right = `<button class="btn pri" data-go="#/baru">${ic('plus')}${_t('nav.new')}</button>`;
  if (!S.meetings.length && !S.q && S.fstat === 'all') {
    return tb(ttl(_t('s1.title')), right) + `<div class="pane empty" data-drop="1"><div class="drop"><div class="glyph">${ic('tray', 'lg')}</div><h2>${_t('s1.empty')}</h2><p>${_t('s1.empty_hint')}</p><button class="btn pri lg" data-go="#/baru">${ic('plus')}${_t('nav.new')}</button><p class="muted" style="font-size:12px">${_t('s1.formats')}</p></div></div>`;
  }
  const opts = [['all', _t('s1.all_status')], ...['transcribing', 'awaiting_review', 'done', 'transcript_only', 'failed'].map(k => [k, statusName(k)])];
  return tb(ttl(_t('s1.title')), right) +
  `<div class="pane s1" data-drop="1"><div class="s1-tools"><label class="srch" style="flex:1;max-width:380px"><span class="sr">${_t('search')}</span>${ic('search')}<input id="s1-q" class="field" style="width:100%" placeholder="${_t('s1.search_ph')}" value="${esc(S.q)}" data-in="q"></label>
  <select class="pop" id="s1-f" data-ch="fstat" aria-label="${_t('s1.filter')}">${opts.map(o => `<option value="${o[0]}"${S.fstat === o[0] ? ' selected' : ''}>${o[1]}</option>`).join('')}</select></div>
  <table class="tbl"><thead><tr><th style="width:52%">${_t('col.title')}</th><th>${_t('col.date')}</th><th>${_t('col.duration')}</th><th>${_t('col.status')}</th></tr></thead><tbody id="s1-rows">${rowsHTML()}</tbody></table>
  <div class="s1-foot">${ic('folder', 'sm')}${_t('s1.v1_note', { dir: esc(homeDir(S.root)) })}</div></div>`;
}

/* ------------------------------------------------------------------ S2 Rapat baru */
/* Whisper model choice: fast (turbo) or accurate (large-v3) */
const WM_NOTE = { cepat: 'wm.note_fast', akurat: 'wm.note_accurate' };
const wmList = () => (S.settings && S.settings.whisper_models) || (S.state && S.state.whisper_models) || [];
const wmOpt = (sel) => wmList().map(w => `<option value="${w.key}"${w.key === sel ? ' selected' : ''}>${w.label} · ${w.name}</option>`).join('');
function wmSmall(key) {
  const w = wmList().find(x => x.key === key);
  if (!w) return '';
  const dl = w.downloaded === false ? ` · ${_t('wm.download_once', { gb: dec(w.size_gb) })}` : '';
  return _t(WM_NOTE[key]) + dl;
}
async function initNew(file) {
  const s = await api('/api/settings');
  S.settings = s;
  const c = s.config;
  S.s2 = { file: null, title: '', lang: c.language || 'id', trim: c.remove_silence !== false,
    clean: c.save_clean_audio !== false, terms: c.vocabulary || '', model: c.whisper_model || 'cepat', parts: [], uploading: null, cleanNote: false, titleTouched: false };
  if (file) s2File(file);
  try { S.recent = (await api('/api/participants/recent')).meetings; } catch (e) { S.recent = []; }
}
const stem = n => String(n).replace(/\.[^.]+$/, '').replace(BAD_TG, '-').trim().slice(0, TITLE_MAX);
function s2File(f) {
  const s = S.s2;
  s.file = f;
  s.track = f.default_track != null ? f.default_track : null;
  if (!s.title) s.title = stem(f.name);
  // "Silence removed.m4a" (before v1.7 "Audio bersih.m4a") from an earlier run: its silences are already cut
  s.cleanNote = /^(audio bersih|silence removed)/i.test(f.name);
  if (s.cleanNote) { s.trim = false; s.clean = false; }
}
const fmtSize = b => b >= 1073741824 ? `${dec(b / 1073741824)} GB` : `${dec(b / 1048576)} MB`;
// what the New meeting screen knows about the file before Process
function fileCard(f) {
  const s = S.s2, pr = f.probe || {}, tr = pr.tracks || [];
  const head = [pr.video ? 'Video' : 'Audio', fmtSize(f.size)];
  if (tr.length) head.push(`${_t('file.sound', { codec: esc(String(tr[0].codec).toUpperCase()) })}${tr.length > 1 ? ` · ${_t('file.tracks', { n: tr.length })}` : ''}`);
  if (pr.duration) head.push(fmtDur(pr.duration));
  const trackSel = tr.length > 1 ? `<div class="frow"><label for="s2-track">${_t('file.track_label')}</label><select class="pop" id="s2-track" data-ch="s2track">${tr.map(k => `<option value="${k.n}"${s.track === k.n ? ' selected' : ''}>${_t('file.track', { n: k.n + 1 })}${k.label ? ` · ${esc(k.label)}` : ''} · ${k.channels === 1 ? 'mono' : k.channels === 2 ? 'stereo' : _t('file.channels', { n: k.channels || '?' })} · ${fmtDur(k.duration)}${k.n === f.default_track ? ` ${_t('file.longest')}` : ''}</option>`).join('')}<option value="mix"${s.track === 'mix' ? ' selected' : ''}>${_t('file.mix')}</option></select><span class="muted">${_t('file.mix_hint')}</span></div>` : '';
  const prob = pr.ok === false ? `<div class="fmsg">${ic('warn', 'sm')}${esc(pr.problem)}</div>` : '';
  const disk = f.disk && f.disk.low ? `<div class="fmsg">${ic('warn', 'sm')}${_t('file.disk_low', { free: fmtSize(f.disk.free), need: fmtSize(f.disk.need) })}</div>` : '';
  const vnote = pr.video && pr.ok !== false ? `<div class="fnote">${ic('info', 'sm')}${_t('file.video_note')}</div>` : '';
  return `<div class="group filecard"><div class="glyph">${ic(pr.video ? 'cmp' : 'wave', 'lg')}</div><div style="flex:1;min-width:0;display:grid;gap:3px"><div style="font-weight:600">${esc(f.name)}</div><div class="muted" style="font-size:12px">${head.join(' · ')} · ${esc(homeDir(f.path.replace(/\/[^/]+$/, '')))}</div>${prob}${disk}${vnote}${trackSel}</div><button class="btn" data-act="pickFile">${_t('file.change')}</button></div>`;
}
const fileBlocked = f => !f || (f.probe && f.probe.ok === false) || (f.disk && f.disk.low);
function S2() {
  const s = S.s2;
  if (!s) return loadingHTML();
  const f = s.file;
  const fileHTML = s.uploading ? `<div class="group filecard"><div class="glyph">${ic('wave', 'lg')}</div><div style="flex:1;min-width:0"><div style="font-weight:600">${esc(s.uploading.name)}</div><div class="bar thin" style="margin-top:6px"><i style="width:${s.uploading.pct}%"></i></div><div class="muted" style="font-size:12px">${_t('file.copying', { pct: s.uploading.pct })}</div></div></div>`
    : f ? fileCard(f)
    : `<div class="drop" style="max-width:none;padding:26px" data-drop="2"><div class="glyph">${ic('tray', 'lg')}</div><div style="font-weight:600">${_t('s2.drop')}</div><div class="muted" style="font-size:12px">m4a, mp3, wav, mp4</div><button class="btn" data-act="pickFile">${_t('s2.pick')}</button></div>`;
  return tb(ttl(_t('s2.title'), _t('s2.sub')), '') +
  `<div class="pane" style="display:flex;flex-direction:column"><div class="form" style="flex:1">
  <div><div class="fgl">${_t('s2.recording')}</div>${fileHTML}</div>
  <div><div class="fgl"><label for="s2-title">${_t('s2.title_label')}</label></div><div class="group" style="padding:8px 12px"><input class="field" id="s2-title" maxlength="${TITLE_MAX}" style="width:100%;border:0;box-shadow:none;background:transparent;padding:0" placeholder="${_t('s2.title_ph')}" value="${esc(s.title)}" data-in="s2title" aria-describedby="s2-title-msg"></div><div class="fmsg" id="s2-title-msg" role="status"${s.titleTouched && titleMsg(s.title) ? '' : ' hidden'}>${s.titleTouched && titleMsg(s.title) ? ic('warn', 'sm') + esc(titleMsg(s.title)) : ''}</div><div class="fnote">${_t('s2.title_note')}</div></div>
  <div><div class="fgl">${_t('s2.process')}</div><div class="group">
   <div class="row"><div class="lb">${_t('s2.model')}<small id="s2-model-note">${wmSmall(s.model)}</small></div><div class="rv"><select class="pop" id="s2-model" data-ch="s2model" aria-label="${_t('s2.model')}">${wmOpt(s.model)}</select></div></div>
   <div class="row"><div class="lb">${_t('s2.lang')}<small>${_t('s2.lang_hint')}</small></div><div class="rv"><select class="pop" id="s2-lang" data-ch="s2lang" aria-label="${_t('s2.lang')}">${LANG_KEYS.map(k => `<option value="${k}"${s.lang === k ? ' selected' : ''}>${langName(k)}</option>`).join('')}</select></div></div>
   <div class="row"><div class="lb">${_t('s2.trim')}<small>${s.cleanNote ? _t('s2.trim_done') : _t('s2.trim_hint', { s: String(S.settings.config.min_silence_sec || 2).replace('.', UI_LANG === 'id' ? ',' : '.') })}</small></div><div class="rv">${sw('s2trim', s.trim, _t('s2.trim'))}</div></div>
   <div class="row"><div class="lb">${_t('s2.clean')}<small>${_t('s2.clean_hint')}</small></div><div class="rv">${sw('s2clean', s.clean && s.trim, _t('s2.clean'))}</div></div>
  </div></div>
  <div><div class="fgl">${_t('s2.terms')}</div><div class="group" style="padding:10px 12px"><textarea class="field" id="s2-terms" rows="2" style="width:100%;border:0;padding:0;box-shadow:none;background:transparent" placeholder="${_t('s2.terms_ph')}" data-in="s2terms">${esc(s.terms)}</textarea><div class="muted" style="font-size:11.5px;margin-top:4px">${_t('s2.terms_hint')}</div></div></div>
  <div><div class="fgl">${ic('person', 'sm')}${_t('s2.parts')} <span style="font-weight:400">· ${_t('optional')}</span></div><div class="group" style="padding:10px 12px;display:grid;gap:8px">
   <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">${s.parts.map((p, i) => `<span class="pchip"><kbd>${i + 1}</kbd>${esc(p.name)}${p.role ? ` <span class="role">· ${esc(p.role)}</span>` : ''}<button data-act="s2rm" data-i="${i}" aria-label="${_t('remove_name', { name: esc(p.name) })}">${ic('x', 'sm')}</button></span>`).join('')}
   <input class="field" id="s2-add" placeholder="${_t('s2.add_ph')}" style="width:260px" data-enter="s2add"></div>
   <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">${S.recent.length ? `<select class="pop" id="s2-from" data-ch="s2from" aria-label="${_t('s2.from_label')}"><option value="">${_t('s2.from')}</option>${S.recent.map(r => `<option value="${esc(r.id)}">${esc(r.title)} (${_t('n_parts', { n: r.participants.length })})</option>`).join('')}</select>` : ''}<span class="muted" style="font-size:11.5px">${_t('s2.order_hint')}</span></div>
  </div></div>
  </div>
  <div class="footbar"><div class="priv">${ic('lock')}${_t('s2.private')}</div><button class="btn pri lg" data-act="process"${!fileBlocked(f) && !s.uploading && !titleMsg(s.title) ? '' : ' disabled'}>${_t('s2.process_btn')}</button></div></div>`;
}
async function uploadFile(file) {
  if (!S.s2) await initNew();
  S.s2.uploading = { name: file.name, pct: 0 };
  if (S.route.name !== 'new') go('#/baru'); else render();
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload');
  xhr.setRequestHeader('X-UI-Lang', UI_LANG);
  xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name).replace(/%20/g, ' '));
  xhr.upload.onprogress = e => { if (e.lengthComputable && S.s2) { S.s2.uploading.pct = Math.round(100 * e.loaded / e.total); render(); } };
  xhr.onload = () => {
    let d = null; try { d = JSON.parse(xhr.responseText); } catch (e) { /* bad json */ }
    S.s2.uploading = null;
    if (xhr.status === 200 && d) s2File(d);
    else toast((d && d.detail) || _t('file.copy_failed'), null, 'bad');
    render();
  };
  xhr.onerror = () => { S.s2.uploading = null; toast(_t('file.copy_failed'), null, 'bad'); render(); };
  xhr.send(file);
}

/* ------------------------------------------------------------------ S3 progres / S3b gagal */
function usedWm(m) {
  const k = (m && ((m.whisper_model && m.whisper_model.key) || (m.settings && m.settings.whisper_model))) || 'cepat';
  return wmList().find(x => x.key === k) || { key: k, label: _t(k === 'akurat' ? 'wm.accurate' : 'wm.fast'), name: k === 'akurat' ? 'large-v3' : 'large-v3-turbo' };
}
function progTitle(p) {
  if (p && p.phase === 'download') return _t('prog.download');
  if (!p || p.phase === 'decode') return _t('prog.decode');
  if (p.phase === 'finish') return _t('prog.finish');
  return _t('prog.part', { i: p.chunk, n: p.chunks });
}
function etaText(p, m) {
  const w = usedWm(m);
  const base = _t('prog.engine', { name: w.name, label: w.label.toLowerCase() });
  if (p && p.phase === 'download') return `${_t('prog.dl_once', { name: w.name })} · ${base}`;
  if (!p || p.eta == null) return `${_t('prog.eta_later')} · ${base}`;
  const mins = Math.max(1, Math.round(p.eta / 60));
  return `${_t('prog.eta', { n: mins })} · ${base}`;
}
function logHTML(log) { return (log || []).slice(-80).map(l => `<b>${esc(l.t)}</b> ${esc(l.text)}`).join('\n'); }
function S3() {
  const m = S.m, p = m.progress || {};
  const sub = `${m.duration_sec ? _t('prog.orig_dur', { d: fmtDur(m.duration_sec) }) + ' · ' : ''}${langName(m.language)}`;
  if (m.status === 'failed') return S3b();
  const queued = m.status === 'queued';
  const cleaned = m.clean_sec != null && m.duration_sec != null;
  const st = (done, run, txt, extra) => `<li><span class="stp${done ? ' done' : run ? ' run' : ''}">${done ? ic('check', 'sm') : run ? '<span class="spinner" style="width:10px;height:10px"></span>' : ''}</span>${run ? `<b>${txt}</b>` : done ? txt : `<span class="muted2">${txt}</span>`}${extra ? ` <span class="muted2">${extra}</span>` : ''}</li>`;
  const phase = p.phase || 'decode';
  return tb(ttl(esc(m.title), sub), `<button class="btn" data-act="cancelJob">${_t('cancel')}</button>`, '#/riwayat') +
  `<div class="pane"><div class="s3"><div style="display:grid;gap:14px"><div class="card">${queued ? `<div class="big"><h2>${_t('prog.wait')}</h2></div><div class="muted" style="font-size:12px">${_t('prog.wait_hint')}</div>` :
  `<div class="big"><h2 id="pg-part">${progTitle(p)}</h2><span class="pct" id="pg-pct">${p.pct || 0}%</span></div><div class="bar"><i id="pg-bar" style="width:${p.pct || 0}%"></i></div><div class="muted" style="font-size:12px;margin-top:8px" id="pg-eta">${etaText(p, m)}</div>`}
  <ul class="steps">${st(m.duration_sec != null, !queued && phase === 'decode' && m.duration_sec == null, _t('step.decode'), m.duration_sec ? fmtDur(m.duration_sec) : '')}
  ${st(cleaned, false, _t('step.trim'), cleaned ? _t('step.trimmed', { d: fmtDur(m.duration_sec - m.clean_sec) }) : '')}
  ${phase === 'download' ? st(false, true, _t('step.download', { name: usedWm(m).name }), _t('step.once')) : ''}
  ${st(phase === 'finish', !queued && phase === 'transcribe', _t('step.transcribe'), usedWm(m).label)}
  ${st(false, false, _t('step.review'))}${st(false, false, _t('step.summary'))}</ul></div>
  <div class="banner info">${ic('info')}<span class="grow">${_t('prog.can_close')}</span></div></div>
  <div><div class="fgl">${_t('log')}</div><div class="log" id="pg-log">${logHTML(m.log)}</div></div></div></div>`;
}
function S3b() {
  const m = S.m, e = m.error || {};
  const chunk = e.chunk, n = e.chunks;
  const head = e.cancelled ? _t('fail.cancelled') : (chunk && n ? _t('fail.stopped', { i: chunk, n }) : _t('fail.failed'));
  const steps = chunk && n ? `<ul class="steps" style="margin-left:52px">${chunk > 1 ? `<li><span class="stp done">${ic('check', 'sm')}</span>${chunk > 2 ? _t('fail.parts_saved', { n: chunk - 1 }) : _t('fail.part1_saved')}</li>` : ''}<li><span class="stp fail">${ic('x', 'sm')}</span><b>${e.cancelled ? _t('fail.part_not_run', { i: chunk }) : _t('fail.part_failed', { i: chunk })}</b></li>${chunk < n ? `<li><span class="stp"></span><span class="muted2">${_t('fail.parts_left', { a: chunk + 1, b: n })}</span></li>` : ''}</ul>` : '';
  return tb(ttl(esc(m.title), `${fmtDate(m.created)} · ${m.duration_sec ? fmtDur(m.duration_sec) + ' · ' : ''}${langName(m.language)}`), '', '#/riwayat') +
  `<div class="pane"><div class="s3"><div style="display:grid;gap:14px"><div class="card" style="border-color:var(--bad-line)"><div style="display:flex;gap:12px;align-items:flex-start"><div class="glyph" style="background:var(--bad-bg);color:var(--bad);width:40px;height:40px;border-radius:10px">${ic('warn', 'lg')}</div><div style="display:grid;gap:6px"><h2 style="margin:0;font-size:16px">${head}</h2><p style="margin:0;color:var(--fg-2);max-width:60ch">${esc(e.message || _t('fail.unknown'))}</p></div></div>
  ${steps}
  <div style="display:flex;gap:8px;margin:16px 0 0 52px;flex-wrap:wrap"><button class="btn pri" data-act="retry">${chunk && chunk > 1 ? _t('fail.retry_from', { i: chunk }) : _t('retry')}</button><button class="btn" data-go="#/baru">${_t('fail.other_file')}</button><button class="btn ghost" data-act="toggleLog">${S.logOpen ? _t('log.hide') : _t('log.show')}</button><button class="btn ghost dng" data-act="openM4">${ic('trash')}${_t('delete')}</button></div></div>
  <div class="banner info">${ic('info')}<span class="grow">${_t('fail.kept')}</span></div></div>
  <div>${S.logOpen ? `<div class="fgl">${_t('log')}</div><div class="log" id="pg-log">${logHTML(m.log)}\n<b>·</b> ${_t('log.no_text')}</div>` : ''}</div></div></div>`;
}

/* ------------------------------------------------------------------ editor (S4 / S4b) */
const canon = (segs, parts) => JSON.stringify({
  s: segs.map(s => [s.id, +(+s.start).toFixed(2), +(+s.end).toFixed(2), (s.text || '').trim(), s.speaker_id || null, !!s.secret, !!s.manual]),
  p: parts.map(p => [p.id, (p.name || '').trim(), (p.role || '').trim()])
});
const segOf = (s, gf) => ({ id: s.id, start: s.start, end: s.end, text: s.text, speaker_id: s.speaker_id || null, secret: !!s.secret,
  ...(s.manual ? { manual: true } : {}), ...(s.gap_fill || (gf && gf.has(s.id)) ? { gap_fill: true } : {}) });
async function loadEditor(view) {
  const m = S.m;
  const d = await api(`/api/meetings/${encodeURIComponent(m.id)}/editor`);
  const src = d.draft || d.base;
  const gf = new Set(d.gap_fill || []);
  const segs = src.segments.map(s => segOf(s, gf));
  const parts = clone(src.participants || []);
  const orig = {};
  d.base.segments.forEach(s => { orig[s.id] = s.text; });
  const sugs = [];
  // a local hint without a replacement word is not a suggestion: it shows only with the doubt-word marks
  d.local.forEach(x => { if (x.to) sugs.push({ ...x, st: 'open' }); });
  d.claude.forEach(x => sugs.push({ ...x, st: 'open' }));
  S.ed = {
    mid: m.id, mode: view === 'tinjau' || !m.transcript_rev ? 'review' : 'edit',
    base: d.base, baseKey: canon(d.base.segments.map(s => segOf(s)), d.base.participants || []),
    segs, parts, orig, sugs, low: d.low_words || {}, claudeTotal: d.claude.length,
    draftAt: d.draft ? d.draft.updated : null, fromDraft: !!d.draft, savedAt: null,
    sel: 0, play: -1, find: '', repl: '', hit: 0, onlyHits: false, doubt: false, autoNext: false,
    qp: null, ren: -1, stale: false, regions: null, minGap: 3, gapSkip: {}, cursor: null, flash: null,
  };
  loadGaps(m.id);
}
async function loadGaps(mid) {
  try {
    const g = await api(`/api/meetings/${encodeURIComponent(mid)}/gaps`);
    if (S.ed && S.ed.mid === mid && g.regions) { S.ed.regions = g.regions; S.ed.minGap = g.min_gap || 3; if (['tinjau', 'edit'].includes(S.route.view)) render(); }
  } catch (e) { /* gaps are only a hint */ }
}
// stretches where the recording has speech but no segment covers it (Usulan 3)
function edGaps(e) {
  if (!e.regions || !e.regions.length) return [];
  const segs = e.segs.slice().sort((a, b) => a.start - b.start);
  const cov = [];
  segs.forEach(s => { const l = cov[cov.length - 1]; if (l && s.start <= l[1] + 0.05) l[1] = Math.max(l[1], s.end); else cov.push([s.start, s.end]); });
  const out = []; let j = 0;
  e.regions.forEach(([a, b]) => {
    while (j < cov.length && cov[j][1] <= a) j++;
    let cur = a;
    for (let k = j; k < cov.length && cov[k][0] < b; k++) {
      if (cov[k][0] - cur > e.minGap) out.push([cur, cov[k][0]]);
      cur = Math.max(cur, cov[k][1]);
    }
    if (b - cur > e.minGap) out.push([cur, b]);
  });
  // a stretch that was already sent to Whisper again stays hidden: what is left there is
  // sound Whisper cannot read (music, noise, very quiet speech), not a new gap
  const tried = e.gapTried || [];
  return out.filter(g => !e.gapSkip[g[0].toFixed(1)] && !tried.some(([x, y]) => g[0] >= x - 1 && g[1] <= y + 1));
}
const normTxt = t => (t || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const edDirty = e => canon(cleanSegs(e.segs), e.parts) !== e.baseKey;
// an inserted segment that was never typed into is not content
const cleanSegs = segs => segs.filter(s => !(s.manual && !(s.text || '').trim()));
function edChanges(e) {
  const base = {}; e.base.segments.forEach(s => { base[s.id] = s; });
  const bp = {}; (e.base.participants || []).forEach(p => { bp[p.id] = p; });
  let edited = 0, tagged = 0, secret = 0, merged = 0;
  const segs = cleanSegs(e.segs);
  const ids = new Set(segs.map(s => s.id));
  segs.forEach(s => {
    const b = base[s.id];
    if (!b) { merged++; return; }
    if ((b.text || '').trim() !== (s.text || '').trim()) edited++;
    if ((b.speaker_id || null) !== (s.speaker_id || null)) tagged++;
    if (!!b.secret !== !!s.secret) secret++;
  });
  e.base.segments.forEach(s => { if (!ids.has(s.id)) merged++; });
  const added = e.parts.filter(p => !bp[p.id]).map(p => p.name);
  const renamed = e.parts.filter(p => bp[p.id] && (bp[p.id].name !== p.name || (bp[p.id].role || '') !== (p.role || ''))).map(p => p.name);
  const removed = Object.values(bp).filter(p => !e.parts.find(x => x.id === p.id)).map(p => p.name);
  const order = (e.base.participants || []).map(p => p.id).join() !== e.parts.filter(p => bp[p.id]).map(p => p.id).join() && !added.length && !removed.length ? 1 : 0;
  return { edited, tagged, secret, merged, added, renamed, removed, order, n: edited + tagged + secret + merged + added.length + renamed.length + removed.length + order };
}
function changeList(c) {
  const li = [];
  if (c.added && c.added.length) li.push(_t('chg.added', { n: c.added.length, names: c.added.map(esc).join(', ') }));
  if (c.renamed && c.renamed.length) li.push(_t('chg.renamed', { n: c.renamed.length }));
  if (c.removed && c.removed.length) li.push(_t('chg.removed', { n: c.removed.length }));
  if (c.order) li.push(_t('chg.order'));
  if (c.tagged) li.push(_t('chg.tagged', { n: num(c.tagged) }));
  if (c.edited) li.push(_t('chg.edited', { n: num(c.edited) }));
  if (c.merged) li.push(_t('chg.merged', { n: num(c.merged) }));
  if (c.secret) li.push(_t('chg.secret', { n: num(c.secret) }));
  return li;
}
function visibleSugs(e, seg) {
  return e.sugs.map((s, j) => ({ s, j })).filter(x => x.s.seg_id === seg.id && x.s.st === 'open' && x.s.to && (seg.text || '').includes(x.s.from));
}
function sugList(e) {
  const out = [];
  e.segs.forEach((g, i) => visibleSugs(e, g).forEach(({ j }) => out.push({ i, j })));
  return out;
}
function sugStep(d) {
  const e = S.ed, list = sugList(e); if (!list.length) return;
  const at = e.sugAt || { i: e.sel, j: -1 };
  const after = x => x.i > at.i || (x.i === at.i && x.j > at.j);
  const before = x => x.i < at.i || (x.i === at.i && x.j < at.j);
  const t = d > 0 ? (list.find(after) || list[0]) : (list.filter(before).pop() || list[list.length - 1]);
  e.sugAt = t; e.sel = t.i;
  render();
  const el = $(`#sgg-${t.j}`) || $(`#sg-${t.i}`);
  if (el) { el.scrollIntoView({ block: 'center' }); el.classList.add('pulse'); setTimeout(() => el.classList.remove('pulse'), 900); }
}
function doubtWords(e, seg) {
  const t = seg.text || '';
  return (e.low[seg.id] || []).filter(w => new RegExp(`(^|[^\\p{L}\\p{N}])${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}($|[^\\p{L}\\p{N}])`, 'iu').test(t));
}
function doubtCount(e) { return e.segs.reduce((a, g) => a + doubtWords(e, g).length, 0); }
function findHits(e) {
  if (!e.find) return [];
  const q = e.find.toLowerCase(), out = [];
  e.segs.forEach((g, i) => { const t = (g.text || '').toLowerCase(); let p = t.indexOf(q); while (p >= 0) { out.push({ i, p }); p = t.indexOf(q, p + q.length); } });
  return out;
}
// marks are built on the raw text per character, so search, suggestions and doubt words can overlap safely
function hlText(e, seg, i, X) {
  const t = seg.text || '';
  if (!t) return '';
  const f = new Array(t.length).fill('');
  const add = (a, len, c) => { for (let k = a; k < a + len && k < t.length; k++) if (!f[k].includes(c)) f[k] += ' ' + c; };
  visibleSugs(e, seg).forEach(({ s }) => { const p = t.indexOf(s.from); if (p >= 0) add(p, s.from.length, s.kind === 'claude' ? 'cl' : 'sl'); });
  if (e.doubt) doubtWords(e, seg).forEach(w => { const m = new RegExp(`(^|[^\\p{L}\\p{N}])(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})($|[^\\p{L}\\p{N}])`, 'iu').exec(t); if (m) add(m.index + m[1].length, m[2].length, 'rg'); });
  if (e.find && X) {
    const n = e.find.length;
    X.hits.forEach((h, k) => { if (h.i === i) add(h.p, n, k === X.cur ? 'fh cur' : 'fh'); });
  }
  let out = '', run = '', cls = null;
  const flush = () => { if (!run) return; out += cls ? `<mark class="${cls.trim()}">${esc(run)}</mark>` : esc(run); run = ''; };
  for (let k = 0; k < t.length; k++) { if (f[k] !== cls) { flush(); cls = f[k]; } run += t[k]; }
  flush();
  return out;
}
function partCount(e, pid) { return e.segs.filter(s => s.speaker_id === pid).length; }
function unassigned(e) { const ids = new Set(e.parts.map(p => p.id)); return e.segs.filter(s => !ids.has(s.speaker_id)).length; }
function edCtx(e) {
  const hits = findHits(e);
  if (e.hit >= hits.length) e.hit = hits.length ? hits.length - 1 : 0;
  return { hits, cur: hits.length ? e.hit : -1, audio: !!(S.m.audio && S.m.audio.asli) };
}
function segRow(e, g, i, X) {
  const on = i === e.sel;
  const changed = e.orig[g.id] != null && e.orig[g.id] !== g.text;
  const pOpts = `<option value=""${!g.speaker_id ? ' selected' : ''}>${_t('untagged')}</option>` + e.parts.map((p, k) => `<option value="${esc(p.id)}"${g.speaker_id === p.id ? ' selected' : ''}>${k < 9 ? (k + 1) + ' · ' : ''}${esc(p.name)}</option>`).join('');
  const flash = e.flash && e.flash.i === i;
  const pills = `${g.manual ? `<span class="pill p-neutral mini">${ic('ins', 'sm')}${_t('seg.manual')}</span>` : ''}${g.gap_fill ? `<span class="pill p-info mini">${ic('wave', 'sm')}${_t('seg.from_gap')}</span>` : ''}`;
  return `<div class="sg${on ? ' on' : ''}" data-act="selSeg" data-i="${i}" id="sg-${i}"><button class="ts" data-act="playSeg" data-i="${i}" title="${_t('play_from', { ts: fmtTs(g.start) })}">${fmtTs(g.start)}</button><select class="pop spk${g.speaker_id ? '' : ' none'}${flash ? ' flash' : ''}" data-ch="spk" data-i="${i}" aria-label="${_t('seg.speaker', { ts: fmtTs(g.start) })}"${e.parts.length ? '' : ' disabled'}>${pOpts}</select><div class="stext" contenteditable="plaintext-only" spellcheck="false" data-ed="${i}" data-ph="${_t('seg.type_ph')}">${hlText(e, g, i, X)}</div><div class="acts">${changed ? `<button class="iconb" data-act="revSeg" data-i="${i}" title="${_t('seg.revert_tip')}" aria-label="${_t('seg.revert')}">${ic('revert')}</button>` : ''}<button class="iconb" data-act="playSeg" data-i="${i}" title="${_t('seg.play_tip')}" aria-label="${_t('seg.play')}"${X.audio ? '' : ' disabled'}>${e.play === i ? '<span class="eq"><i></i><i></i><i></i></span>' : ic('play')}</button><button class="iconb del" data-act="delSeg" data-i="${i}" title="${_t('seg.del_tip')}" aria-label="${_t('seg.del', { ts: fmtTs(g.start) })}">${ic('trash')}</button></div>
    ${pills ? `<div class="meta2">${pills}</div>` : ''}
    ${on && e.parts.length ? `<div class="hint">${ic('person', 'sm')}<span>${_t('seg.keys', { keys: e.parts.slice(0, 9).map((p, j) => `<kbd>${j + 1}</kbd>`).join(' ') })}${e.parts.length > 9 ? _t('seg.keys_find') : _t('seg.keys_pick')}</span><span class="tagmsg" id="tagmsg" role="status">${flash ? `${ic('check', 'sm')}${esc(e.flash.text)}` : ''}</span></div>` : ''}
    ${g.secret ? `<div class="secret"><span class="pill p-neutral">${ic('lock', 'sm')}${_t('seg.secret')}</span><button class="btn ghost" style="height:20px;font-size:11px" data-act="secret" data-i="${i}">${_t('seg.unmark')}</button></div>` : ''}
    ${visibleSugs(e, g).map(({ s, j }) => `<div class="sgg${s.kind === 'claude' ? ' cl' : ''}" id="sgg-${j}"><span class="src ${s.kind === 'claude' ? 'c' : 'l'}">${ic(s.kind === 'claude' ? 'spark' : 'pencil', 'sm')}${s.kind === 'claude' ? _t('sug.ai') : _t('sug.local')}</span><span class="grow">${_t('sug.change', { from: `<s>${esc(s.from)}</s>`, to: `<b>${esc(s.to)}</b>` })} <span class="muted">· ${esc(s.reason)}</span></span><button class="btn" data-act="sugOk" data-j="${j}">${_t('accept')}</button><button class="btn ghost" data-act="sugNo" data-j="${j}">${_t('reject')}</button>${s.kind === 'local' ? `<button class="btn ghost" data-act="sugTerm" data-j="${j}">${_t('sug.add_term')}</button>` : ''}</div>`).join('')}
    </div>`;
}
function gapRow(g, k, X) {
  const [a, b] = g;
  const busy = S.gapBusy === a.toFixed(1);
  return `<div class="gaprow" id="gap-${k}"><span class="gi">${ic('warn', 'sm')}</span><span class="grow"><b>${_t('gap.title', { a: fmtTs(a), b: fmtTs(b) })}</b> · ${_t('gap.text', { n: Math.round(b - a) })}</span>${X.audio ? `<button class="btn" data-act="gapPlay" data-a="${a}" data-b="${b}">${ic('play', 'sm')}${_t('play')}</button><button class="btn" data-act="gapRe" data-a="${a}" data-b="${b}"${S.gapBusy ? ' disabled' : ''}>${busy ? '<span class="spinner" style="width:10px;height:10px"></span>' : ic('wave', 'sm')}${_t('gap.redo')}</button>` : ''}<button class="btn ghost" data-act="gapIns" data-a="${a}" data-b="${b}">${ic('ins', 'sm')}${_t('gap.insert')}</button><button class="btn ghost" data-act="gapSkip" data-a="${a}" title="${_t('gap.ignore_tip')}">${_t('gap.ignore')}</button></div>`;
}
function qpHTML(e) {
  if (!e.qp) return '';
  const list = qpList(e);
  if (e.qp.k >= list.length) e.qp.k = Math.max(0, list.length - 1);
  const g = e.segs[e.sel];
  return `<div class="qp" role="dialog" aria-label="${_t('qp.label', { ts: g ? fmtTs(g.start) : '' })}"><div class="qph">${ic('person', 'sm')}${_t('qp.title', { ts: g ? fmtTs(g.start) : '' })}</div><input class="field" id="qp-in" placeholder="${_t('qp.ph')}" value="${esc(e.qp.q)}" data-in="qp" autocomplete="off" aria-label="${_t('qp.search')}"><div class="qpl" role="listbox">${list.map((p, k) => `<button class="qpi${k === e.qp.k ? ' on' : ''}" role="option" aria-selected="${k === e.qp.k}" data-act="qpPick" data-id="${esc(p.id)}"><kbd>${p.n <= 9 ? p.n : '·'}</kbd><span class="grow">${esc(p.name)}${p.role ? ` <span class="role">${esc(p.role)}</span>` : ''}</span></button>`).join('') || `<div class="muted" style="padding:8px;font-size:12px">${_t('qp.none')}</div>`}</div><div class="muted" style="font-size:11px">${_t('qp.keys')}</div></div>`;
}
const qpList = e => e.parts.map((p, i) => ({ ...p, n: i + 1 })).filter(p => !e.qp.q || `${p.name} ${p.role || ''}`.toLowerCase().includes(e.qp.q.toLowerCase()));
function scrubHTML(kind, pos, len, id) {
  const pct = len ? Math.min(100, pos / len * 100).toFixed(2) : 0;
  return `<div class="aprog scrub" data-scrub="${kind}" data-len="${len || 0}" tabindex="0" role="slider" aria-label="${_t('audio.pos')}" aria-valuemin="0" aria-valuemax="${Math.round(len || 0)}" aria-valuenow="${Math.round(pos)}" aria-valuetext="${fmtDur(pos)}" title="${_t('audio.scrub_tip')}"><i id="${id}" style="width:${pct}%"></i><span class="tip" hidden></span></div>`;
}

function editorHTML() {
  const e = S.ed, m = S.m;
  if (!e) return loadingHTML();
  const X = edCtx(e);
  const isB = e.mode === 'edit';
  const dirty = edDirty(e);
  const nChg = dirty ? edChanges(e).n : 0;
  const open = e.sugs.filter(s => s.st === 'open' && s.to && (e.segs.find(g => g.id === s.seg_id) || { text: '' }).text.includes(s.from));
  const loc = open.filter(s => s.kind === 'local').length, cl = open.filter(s => s.kind === 'claude').length;
  const sl = sugList(e), sk = e.sugAt ? sl.findIndex(x => x.j === e.sugAt.j) : -1;
  const nDoubt = doubtCount(e);
  const nh = X.hits.length;
  const selSegO = e.segs[e.sel] || e.segs[0];
  const sm = m.summaries && m.summaries.length ? m.summaries[m.summaries.length - 1] : null;
  const claudeReview = e.claudeTotal > 0;
  const saveLabel = !dirty && claudeReview ? _t('ed.done_review') : _t('save');
  const saveDisabled = isB && !dirty && !claudeReview;
  const head = isB ? ttl(_t('ed.edit'), `${esc(m.title)} · ${_t('ed.tr_ver', { v: m.transcript_rev })}${sm ? ` · ${_t('ed.sum_from', { v: sm.based_on_rev })}` : ''}`)
    : ttl(_t('ed.review'), `${esc(m.title)} · ${_t('ed.draft')} · ${_t('n_segs', { n: e.segs.length, nn: num(e.segs.length) })} · ${_t('n_words', { n: words(e.segs), nn: num(words(e.segs)) })}`);
  const status = isB ? `<span class="cnt muted" style="font-size:12px" id="chg-lbl">${dirty ? _t('ed.unsaved', { n: nChg, nn: num(nChg) }) : _t('ed.no_changes')}</span>`
    : `<span class="muted" style="font-size:12px;display:inline-flex;gap:5px;align-items:center" id="chg-lbl">${e.savedAt ? `${ic('check', 'sm')}${_t('ed.draft_saved', { at: e.savedAt })}` : _t('ed.not_saved')}</span>`;
  const right = `${status}<button class="btn" data-act="openDiff">${ic('cmp')}${isB ? _t('cmp.versions') : _t('cmp.orig_edit')}</button><button class="btn" data-act="closeEd" title="${_t('ed.close_tip')}">${_t('close')}</button><button class="btn pri" data-act="save" id="save-btn"${saveDisabled ? ' disabled' : ''}>${saveLabel}</button>`;
  const un = unassigned(e);
  const total = e.segs.length;
  const draftBanner = e.fromDraft ? `<div class="banner info" style="margin:8px 14px 0">${ic('info')}<span class="grow">${e.draftAt ? _t('ed.resume_at', { at: fmtDT(e.draftAt) }) : _t('ed.resume')}</span><button class="btn ghost" data-act="dropDraft">${_t('ed.drop_draft')}</button></div>` : '';
  const sugFail = m.suggest_job && m.suggest_job.state === 'failed' ? `<div class="banner bad" style="margin:8px 14px 0">${ic('warn')}<span class="grow">${_t('sug.failed_msg', { msg: esc(m.suggest_job.error || '') })}</span></div>` : '';
  const gaps = edGaps(e);
  const gapBanner = gaps.length ? `<div class="banner warn" style="margin:8px 14px 0">${ic('warn')}<span class="grow"><b>${_t('gap.banner_n', { n: gaps.length })}</b> ${_t('gap.banner', { s: dec(e.minGap).replace(/[.,]0$/, '') })}</span><button class="btn" data-act="gapNext">${ic('down')}${_t('gap.next')}</button></div>` : '';
  // gap rows sit before the first segment that starts after the gap
  const gapAt = {};
  gaps.forEach((g, k) => { let pos = e.segs.findIndex(s => s.start >= g[1] - 0.05); if (pos < 0) pos = e.segs.length; (gapAt[pos] = gapAt[pos] || []).push(gapRow(g, k, X)); });
  const hitRows = e.onlyHits && e.find ? new Set(X.hits.map(h => h.i)) : null;
  let list = '';
  e.segs.forEach((g, i) => {
    if (!hitRows && gapAt[i]) list += gapAt[i].join('');
    if (hitRows && !hitRows.has(i)) return;
    list += segRow(e, g, i, X);
  });
  if (!hitRows && gapAt[e.segs.length]) list += gapAt[e.segs.length].join('');
  if (hitRows && !hitRows.size) list = `<div class="muted" style="padding:24px 16px">${_t('ed.no_hits', { q: esc(e.find) })}</div>`;
  const cursor = e.cursor != null ? e.cursor : (selSegO ? selSegO.start : 0);
  const len = m.duration_sec || 0;
  return tb(head, right, mhash(m.id, 'transkrip')) +
  `<div class="ed"><div class="ed-main">
  <div class="ebar"><label class="srch"><span class="sr">${_t('search')}</span>${ic('search')}<input class="field" id="ed-find" style="width:150px" placeholder="${_t('ed.find_ph')}" value="${esc(e.find)}" data-in="find" aria-describedby="find-cnt"></label><span class="fcount" id="find-cnt" aria-live="polite">${e.find ? (nh ? _t('x_of_n', { i: X.cur + 1, n: num(nh) }) : _t('none')) : ''}</span><button class="iconb" data-act="findNav" data-v="-1" aria-label="${_t('ed.prev_hit')}" title="${_t('ed.prev')}"${nh ? '' : ' disabled'}>${ic('up')}</button><button class="iconb" data-act="findNav" data-v="1" aria-label="${_t('ed.next_hit')}" title="${_t('ed.next')}"${nh ? '' : ' disabled'}>${ic('down')}</button><label class="chk" title="${_t('ed.only_hits_tip')}"><input type="checkbox" data-ch="onlyHits"${e.onlyHits ? ' checked' : ''}${e.find ? '' : ' disabled'}>${_t('ed.only_hits')}</label><input class="field" id="ed-repl" style="width:120px" placeholder="${_t('ed.repl_ph')}" value="${esc(e.repl)}" data-in="repl" aria-label="${_t('ed.repl_ph')}"><button class="btn" data-act="replOne" id="repl1-btn"${nh ? '' : ' disabled'}>${_t('ed.repl')}</button><button class="btn" data-act="replAll" id="repl-btn"${nh ? '' : ' disabled'}>${_t('ed.repl_all')}${nh ? ` (${nh})` : ''}</button></div>
  <div class="ebar"><button class="btn ghost" data-act="merge" title="${_t('ed.merge_tip')}">${ic('merge')}${_t('ed.merge')}</button><button class="btn ghost" data-act="split" title="${_t('ed.split_tip')}">${ic('split')}${_t('ed.split')}</button><button class="btn ghost" data-act="insSeg" title="${_t('ed.ins_tip')}">${ic('ins')}${_t('ed.ins')}</button><button class="btn ghost" data-act="delSeg" title="${_t('ed.del_tip')}">${ic('trash')}${_t('delete')}</button><span class="sepv"></span><button class="btn ghost" data-act="secret" id="sec-btn" title="${_t('ed.secret_tip')}">${ic('lock')}${selSegO && selSegO.secret ? _t('ed.unsecret') : _t('ed.secret')}</button></div>
  <div class="ebar" style="background:var(--panel)"><span class="pill p-warn">${ic('pencil', 'sm')}${_t('ed.n_local', { n: loc })}</span>${cl ? `<span class="pill p-claude">${ic('spark', 'sm')}${_t('ed.n_ai', { n: cl })}</span>` : ''}<span class="fcount" id="sug-cnt" aria-live="polite">${sl.length ? (sk >= 0 ? _t('sug.n_of', { i: sk + 1, n: num(sl.length) }) : _t('sug.count', { n: sl.length, nn: num(sl.length) })) : ''}</span><button class="iconb" data-act="sugNav" data-v="-1" aria-label="${_t('sug.prev')}" title="${_t('sug.prev')}"${sl.length ? '' : ' disabled'}>${ic('up')}</button><button class="iconb" data-act="sugNav" data-v="1" aria-label="${_t('sug.next')}" title="${_t('sug.next')}"${sl.length ? '' : ' disabled'}>${ic('down')}</button><button class="btn" data-act="acceptAll"${open.length ? '' : ' disabled'}>${_t('ed.accept_all')}</button><button class="btn ghost" data-act="rejectAll"${open.length ? '' : ' disabled'}>${_t('ed.reject_all')}</button><label class="chk" title="${_t('ed.doubt_tip')}"><input type="checkbox" data-ch="doubt"${e.doubt ? ' checked' : ''}${nDoubt ? '' : ' disabled'}>${_t('ed.doubt', { n: num(nDoubt) })}</label><span style="flex:1"></span>${m.claude_suggest ? claudePill(m.claude_suggest) : ''}${!claudeReview && (!isB || m.transcript_rev) ? (sugBusy(m) ? `<button class="btn" data-go="${mhash(m.id, 'saran')}"><span class="spinner" style="color:var(--accent)"></span>${_t('sug.busy')}</button>` : (isB ? `<button class="btn claude" data-act="openM1">${ic('spark')}${_t('ed.ask_ai')}</button>` : `<button class="btn claude" data-act="saveM1"${cleanSegs(e.segs).length ? '' : ' disabled'} title="${_t('ed.save_ask_tip')}">${ic('spark')}${_t('ed.ask_ai')}</button>`)) : ''}</div>
  ${draftBanner}${sugFail}${gapBanner}
  <div class="player"><button class="pbtn" id="pl-btn" data-act="playMain" aria-label="${e.play !== -1 ? _t('pause') : _t('play')}"${X.audio ? '' : ' disabled'}>${ic(e.play !== -1 ? 'pause' : 'play')}</button><span class="mono" style="font-size:12px" id="pl-ts">${fmtTs(cursor)}</span>${scrubHTML('asli', cursor, len, 'pl-bar')}<span class="mono muted" style="font-size:12px">${fmtDur(len)}</span><span class="muted" style="font-size:12px">${X.audio ? _t('src.orig') : _t('src.orig_missing')}</span></div>
  <div class="seglist" data-keep="seglist" id="seglist">${list}</div>${qpHTML(e)}</div>
  <aside class="eside"><h3>${_t('parts')} <span class="muted" style="font-weight:400">${_t('segments')}</span></h3><div class="plist">${e.parts.map((p, i) => `<div class="prow" data-pi="${i}" id="prow-${i}"><button class="grip" draggable="true" data-pi="${i}" id="grip-${i}" aria-label="${_t('ed.grip', { name: esc(p.name) })}" title="${_t('ed.grip_tip')}">${ic('grip', 'sm')}</button><kbd>${i < 9 ? i + 1 : '·'}</kbd>${e.ren === i ? `<input class="field" id="ren-${i}" value="${esc(p.name)}${p.role ? ', ' + esc(p.role) : ''}" data-enter="renOk" data-i="${i}" aria-label="${_t('ed.name_role')}">` : `<span class="nm" title="${esc(p.role || '')}">${esc(p.name)}${e.base.participants && e.base.participants.find(x => x.id === p.id) ? '' : `<span class="new">${_t('new')}</span>`}${p.role ? `<span class="role">${esc(p.role)}</span>` : ''}</span>`}<button class="iconb" style="width:22px;height:22px" data-act="ren" data-i="${i}" aria-label="${_t('ed.rename', { name: esc(p.name) })}">${ic('pencil', 'sm')}</button><span class="nb" id="pc-${i}">${num(partCount(e, p.id))}</span></div>`).join('') || `<span class="muted" style="font-size:12px">${_t('ed.no_parts')}</span>`}</div>
  ${e.parts.length > 1 ? `<span class="muted" style="font-size:11.5px">${_t('ed.order_hint')}</span>` : ''}
  <input class="field" id="ed-padd" placeholder="${_t('ed.add_ph')}" data-enter="padd" aria-label="${_t('ed.add')}">
  ${e.parts.length ? `<div style="display:grid;gap:6px;border-top:1px solid var(--line);padding-top:12px"><div style="font-size:12px"><b>${_t('ed.untagged')}</b> ${_t('x_of_n', { i: `<span class="mono" id="un-cnt">${num(un)}</span>`, n: num(total) })}</div><div class="bar thin"><i id="un-bar" style="width:${total ? (100 - un / total * 100).toFixed(1) : 0}%"></i></div><button class="btn" data-act="nextUn" id="next-un"${un ? '' : ' disabled'}>${ic('down')}${_t('ed.next_un')}</button><label class="chk"><input type="checkbox" data-ch="autoNext"${e.autoNext ? ' checked' : ''}>${_t('ed.auto_next')}</label><span class="muted" style="font-size:11.5px">${_t('ed.tag_optional')}</span></div>` : ''}
  <div class="sc" style="border-top:1px solid var(--line);padding-top:12px;margin-top:auto"><b style="color:var(--fg)">${_t('keys')}</b>${_t('ed.keys_list')}</div>
  </aside></div>`;
}
let draftT = null;
function edTouched(full) {
  const e = S.ed; if (!e) return;
  clearTimeout(draftT);
  draftT = setTimeout(saveDraft, 1200);
  if (full) render(); else patchEdStatus();
}
async function saveDraft() {
  const e = S.ed; if (!e) return;
  clearTimeout(draftT);
  try {
    if (edDirty(e)) await api(`/api/meetings/${encodeURIComponent(e.mid)}/draft`, { method: 'PUT', body: { segments: cleanSegs(e.segs), participants: e.parts } });
    else if (e.fromDraft) { await api(`/api/meetings/${encodeURIComponent(e.mid)}/draft`, { method: 'DELETE' }); }
    e.savedAt = fmtClock();
    patchEdStatus();
  } catch (err) { /* keep editing; the next change retries */ }
}
function patchEdStatus() {
  const e = S.ed; if (!e) return;
  const dirty = edDirty(e);
  const lbl = $('#chg-lbl');
  if (lbl) lbl.innerHTML = e.mode === 'edit' ? (dirty ? _t('ed.unsaved', { n: edChanges(e).n, nn: num(edChanges(e).n) }) : _t('ed.no_changes'))
    : (e.savedAt ? `${ic('check', 'sm')}${_t('ed.draft_saved', { at: e.savedAt })}` : _t('ed.not_saved'));
  const b = $('#save-btn');
  if (b) { const claudeReview = e.claudeTotal > 0; b.disabled = e.mode === 'edit' && !dirty && !claudeReview; b.textContent = !dirty && claudeReview ? _t('ed.done_review') : _t('save'); }
}
// redraw one row without touching the other ~1,500 (keys 1–9 stay instant)
function patchRow(i) {
  const e = S.ed, el = document.getElementById(`sg-${i}`), g = e && e.segs[i];
  if (!el || !g) return false;
  el.outerHTML = segRow(e, g, i, edCtx(e));
  return true;
}
function patchParts() {
  const e = S.ed; if (!e) return;
  e.parts.forEach((p, i) => { const c = document.getElementById(`pc-${i}`); if (c) c.textContent = num(partCount(e, p.id)); });
  const un = unassigned(e), total = e.segs.length;
  const uc = $('#un-cnt'); if (uc) uc.textContent = num(un);
  const ub = $('#un-bar'); if (ub) ub.style.width = `${total ? (100 - un / total * 100).toFixed(1) : 0}%`;
  const nb = $('#next-un'); if (nb) nb.disabled = !un;
}
function selSeg(i, scroll) {
  const e = S.ed; if (!e) return;
  const old = e.sel;
  e.sel = Math.max(0, Math.min(e.segs.length - 1, i));
  e.cursor = null;
  if (e.flash && e.flash.i !== e.sel) e.flash = null;
  if (!patchRow(old) || !patchRow(e.sel)) render();
  const g = e.segs[e.sel];
  const sb = $('#sec-btn'); if (sb && g) sb.innerHTML = `${ic('lock')}${g.secret ? _t('ed.unsecret') : _t('ed.secret')}`;
  if (e.play === -1 && g) setPlayer(g.start);
  if (scroll) { const el = $(`#sg-${e.sel}`); if (el) el.scrollIntoView({ block: 'nearest' }); }
}
function tagSel(pid) {
  const e = S.ed; const i = e.sel, g = e.segs[i]; if (!g) return;
  g.speaker_id = pid;
  const p = e.parts.find(x => x.id === pid);
  e.flash = { i, text: p ? _t('ed.tagged', { name: p.name }) : _t('ed.untag') };
  edTouched(false);
  patchRow(i); patchParts();
  clearTimeout(tagSel.h);
  tagSel.h = setTimeout(() => {
    if (!S.ed || !S.ed.flash || S.ed.flash.i !== i) return;
    S.ed.flash = null;
    const m = $('#tagmsg'); if (m) m.textContent = '';
    const sp = document.querySelector(`#sg-${i} .spk`); if (sp) sp.classList.remove('flash');
  }, 1800);
  if (e.autoNext && i < e.segs.length - 1) selSeg(i + 1, true);
}
function newId(e, prefix) {
  const ids = new Set(e.segs.map(s => s.id));
  let n = 1; while (ids.has(`${prefix}${pad(n).padStart(5, '0')}`)) n++;
  return `${prefix}${pad(n).padStart(5, '0')}`;
}
function focusSeg(i) {
  const el = document.querySelector(`[data-ed="${i}"]`); if (!el) return;
  el.scrollIntoView({ block: 'nearest' });
  el.focus();
  const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
  const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
}
function delSegAt(i) {
  const e = S.ed, g = e.segs[i]; if (!g) return;
  if (e.segs.length <= 1) { toast(_t('ed.min_one'), null, 'bad'); return; }
  const before = clone(e.segs), sel = e.sel;
  e.segs.splice(i, 1);
  e.sel = Math.min(i, e.segs.length - 1);
  edTouched(true);
  toast(_t('ed.seg_deleted', { ts: fmtTs(g.start) }), () => { e.segs = before; e.sel = sel; edTouched(true); });
}
function insertSeg(pos, st, en, text, extra) {
  const e = S.ed;
  const before = clone(e.segs), sel = e.sel;
  const seg = { id: newId(e, extra && extra.gap_fill ? 'g' : 'm'), start: +st.toFixed(2), end: +Math.max(st + 0.5, en).toFixed(2), text: text || '', speaker_id: null, secret: false, ...(extra || { manual: true }) };
  e.segs.splice(pos, 0, seg);
  e.sel = pos;
  return () => { e.segs = before; e.sel = sel; edTouched(true); };
}

/* ------------------------------------------------------------------ audio (F16) */
const audio = document.getElementById('audio');
let stopAt = null;
function stopAudio() { audio.pause(); stopAt = null; if (S.ed) S.ed.play = -1; S.playing = null; }
function setSrc(src) { if (audio.dataset.src !== src) { audio.src = src; audio.dataset.src = src; } }
function playRange(src, start, end, onEnd) {
  setSrc(src);
  stopAt = end != null ? { t: end, cb: onEnd } : null;
  const go2 = () => { try { audio.currentTime = start; } catch (e) { /* not seekable yet */ } audio.play().catch(() => toast(_t('audio.cannot_play'), null, 'bad')); };
  if (audio.readyState >= 1) go2(); else audio.addEventListener('loadedmetadata', go2, { once: true });
}
function seekTo(src, t, then) {
  setSrc(src);
  const go2 = () => { try { audio.currentTime = Math.max(0, t); } catch (e) { /* not seekable yet */ } if (then) then(); };
  if (audio.readyState >= 1) go2(); else audio.addEventListener('loadedmetadata', go2, { once: true });
}
function audioLen(kind) {
  const m = S.m; if (!m) return 0;
  if (audio.dataset.src === audioUrl(m.id, kind) && isFinite(audio.duration)) return audio.duration;
  return (kind === 'asli' ? m.duration_sec : m.clean_sec) || 0;
}
const inEditor = () => S.route.name === 'meeting' && ['tinjau', 'edit'].includes(S.route.view) && S.ed;
function setPlayer(t) {
  const len = audioLen('asli');
  const ts = $('#pl-ts'); if (ts) ts.textContent = fmtTs(t);
  const b = $('#pl-bar'); if (!b) return;
  b.style.width = `${len ? Math.min(100, t / len * 100).toFixed(2) : 0}%`;
  b.parentElement.setAttribute('aria-valuenow', Math.round(t)); b.parentElement.setAttribute('aria-valuetext', fmtDur(t));
}
function patchPlay() {
  const b = $('#pl-btn'), e = S.ed; if (!b || !e) return;
  b.innerHTML = ic(e.play !== -1 ? 'pause' : 'play'); b.setAttribute('aria-label', e.play !== -1 ? _t('pause') : _t('play'));
}
audio.addEventListener('timeupdate', () => {
  if (stopAt && audio.currentTime >= stopAt.t) { const cb = stopAt.cb; stopAt = null; audio.pause(); if (cb) cb(); }
  if (S.route.view === 'audio') patchAudio();
  if (inEditor() && S.m && audio.dataset.src === audioUrl(S.m.id, 'asli') && !S.scrub) setPlayer(audio.currentTime);
});
audio.addEventListener('error', () => { if (audio.dataset.src) toast(_t('audio.cannot_read'), null, 'bad'); });
audio.addEventListener('ended', () => { const e = S.ed; const old = e ? e.play : -1; if (e) e.play = -1; S.playing = null; if (inEditor()) { if (old >= 0) patchRow(old); patchPlay(); } else render(); });
function playSegment(i) {
  const e = S.ed, m = S.m;
  if (!m.audio || !m.audio.asli) { toast(_t('src.orig_lost'), null, 'bad'); return; }
  const old = e.play;
  if (old === i) { stopAudio(); patchRow(i); patchPlay(); return; }
  const g = e.segs[i]; if (!g) return;
  const oldSel = e.sel;
  e.play = i; e.sel = i; e.cursor = null;
  playRange(audioUrl(m.id, 'asli'), Math.max(0, g.start - 0.2), g.end + 0.3, () => { if (S.ed === e && e.play === i) { e.play = -1; patchRow(i); patchPlay(); } });
  [old, oldSel, i].filter((x, k, a) => x >= 0 && a.indexOf(x) === k).forEach(x => { if (!patchRow(x)) render(); });
  patchPlay();
}
/* draggable position bar, editor and Audio tab */
function scrubFrac(el, x) { const r = el.getBoundingClientRect(); return r.width ? Math.min(1, Math.max(0, (x - r.left) / r.width)) : 0; }
function scrubLen(el) { return audioLen(el.dataset.scrub) || +el.dataset.len || 0; }
function scrubSet(el, t) {
  const kind = el.dataset.scrub, len = scrubLen(el);
  const i = el.querySelector('i'); if (i) i.style.width = `${len ? Math.min(100, t / len * 100).toFixed(2) : 0}%`;
  el.setAttribute('aria-valuenow', Math.round(t)); el.setAttribute('aria-valuetext', fmtDur(t));
  if (inEditor()) { const ts = $('#pl-ts'); if (ts) ts.textContent = fmtTs(t); }
  else { const tt = $('#ap-t'); if (tt) tt.textContent = `${fmtTs(t)} / ${fmtTs(len)}`; }
}
function scrubCommit(kind, t) {
  const m = S.m; if (!m) return;
  const src = audioUrl(m.id, kind);
  if (inEditor()) {
    const e = S.ed, wasPlaying = e.play !== -1 && !audio.paused;
    if (!m.audio || !m.audio.asli) return;
    stopAt = null;
    // select the segment being spoken at that moment
    let best = -1;
    e.segs.forEach((s, k) => { if (s.start <= t + 0.05 && (best < 0 || s.start >= e.segs[best].start)) best = k; });
    const old = e.play;
    if (best >= 0 && best !== e.sel) {
      const os = e.sel; e.sel = best; patchRow(os); patchRow(best);
      const el = $(`#sg-${best}`); if (el) el.scrollIntoView({ block: 'nearest' });
    }
    e.cursor = t;
    if (wasPlaying) { e.play = -2; if (old >= 0) patchRow(old); seekTo(src, t, () => audio.play().catch(() => {})); }
    else seekTo(src, t);
    patchPlay();
  } else {
    const playing = audio.dataset.src === src && !audio.paused;
    stopAt = null;
    seekTo(src, t, () => { if (playing) audio.play().catch(() => {}); patchAudio(); });
  }
}
function nudge(kind, d) {
  const m = S.m; if (!m) return;
  const src = audioUrl(m.id, kind);
  let cur = 0;
  if (audio.dataset.src === src && audio.readyState >= 1) cur = audio.currentTime;
  else if (inEditor()) { const e = S.ed; cur = e.cursor != null ? e.cursor : (e.segs[e.sel] || { start: 0 }).start; }
  const len = audioLen(kind);
  const t = Math.max(0, len ? Math.min(len, cur + d) : cur + d);
  const el = document.querySelector(`[data-scrub="${kind}"]`); if (el) scrubSet(el, t);
  scrubCommit(kind, t);
}
document.addEventListener('pointerdown', ev => {
  const el = ev.target.closest && ev.target.closest('[data-scrub]'); if (!el || ev.button) return;
  ev.preventDefault(); el.focus();
  try { el.setPointerCapture(ev.pointerId); } catch (e) { /* old engine */ }
  S.scrub = { el, t: scrubFrac(el, ev.clientX) * scrubLen(el) };
  el.classList.add('drag'); scrubSet(el, S.scrub.t);
});
document.addEventListener('pointermove', ev => {
  const el = (S.scrub && S.scrub.el) || (ev.target.closest && ev.target.closest('[data-scrub]'));
  document.querySelectorAll('[data-scrub] .tip').forEach(t => { if (!el || !el.contains(t)) t.hidden = true; });
  if (!el) return;
  const f = scrubFrac(el, ev.clientX), t = f * scrubLen(el);
  const tip = el.querySelector('.tip'); if (tip) { tip.hidden = false; tip.style.left = `${(f * 100).toFixed(2)}%`; tip.textContent = fmtDur(t); }
  if (S.scrub) { S.scrub.t = t; scrubSet(el, t); }
});
document.addEventListener('pointerup', () => {
  if (!S.scrub) return;
  const { el, t } = S.scrub; S.scrub = null;
  el.classList.remove('drag');
  const tip = el.querySelector('.tip'); if (tip) tip.hidden = true;
  scrubCommit(el.dataset.scrub, t);
});

/* ------------------------------------------------------------------ diff (S4c) */
async function loadDiffLeft() {
  const e = S.ed, m = S.m;
  const opts = diffLeftOptions();
  if (!opts.find(o => o[0] === S.diff.left)) S.diff.left = 'whisper';
  const rev = S.diff.left === 'saved' ? m.transcript_rev : S.diff.left === 'whisper' ? 0 : +S.diff.left.slice(1);
  S.diff.L = await api(`/api/meetings/${encodeURIComponent(m.id)}/transcript?rev=${rev}`);
  S.diff.cur = 0;
  if (!e) return;
}
function diffLeftOptions() {
  const m = S.m, o = [];
  o.push(['whisper', _t('cmp.whisper_file')]);
  if (m.transcript_rev) o.push(['saved', _t('cmp.last_saved', { v: m.transcript_rev })]);
  (m.versions || []).filter(v => v.rev >= 1 && v.rev < m.transcript_rev).reverse().forEach(v => o.push(['v' + v.rev, `${_t('ver.n', { v: v.rev })} · ${fmtDT(v.created)}`]));
  return o;
}
function nameMap(parts) { const n = {}; (parts || []).forEach(p => { n[p.id] = p.name; }); return n; }
function segTxt(names, tags) { return s => (tags && s.speaker_id && names[s.speaker_id] ? `[${names[s.speaker_id]}] ` : '') + (s.secret ? '🔒 ' : '') + (s.text || ''); }
function toks(t) {
  const g = [];
  t.forEach(([w, c]) => { const l = g[g.length - 1]; if (l && l.c === c) l.w.push(w); else g.push({ c, w: [w] }); });
  return g.map(x => x.c ? `<mark class="wd">${esc(x.w.join(' '))}</mark>` : esc(x.w.join(' '))).join(' ');
}
function lineHTML(lt, rt, ln, rn, ltm, rtm) {
  const lc = lt != null && lt !== rt, rc = rt != null && lt !== rt;
  let lh = lt != null ? esc(lt) : '', rh = rt != null ? esc(rt) : '';
  if (lt != null && rt != null && lt !== rt) { const w = D.wdiff(lt, rt); lh = toks(w[0]); rh = toks(w[1]); }
  const tl = ltm ? `<span class="tm">${ltm}</span>  ` : '', tr = rtm ? `<span class="tm">${rtm}</span>  ` : '';
  if (S.diff.mode === 'inline') {
    let o = '';
    if (lc) o += `<div class="dl inl"><span class="ln c-del">${ln}</span><span class="ln c-del"></span><span class="sg2 c-del">−</span><span class="c-del">${tl}${lh}</span></div>`;
    if (rc) o += `<div class="dl inl"><span class="ln c-add"></span><span class="ln c-add">${rn}</span><span class="sg2 c-add">+</span><span class="c-add">${tr}${rh}</span></div>`;
    if (!lc && !rc) o += `<div class="dl inl"><span class="ln">${ln}</span><span class="ln">${rn}</span><span class="sg2"></span><span>${tl}${lh}</span></div>`;
    return o;
  }
  const Ls = lt != null ? `<span class="ln${lc ? ' c-del' : ''}">${ln}</span><span class="sg2${lc ? ' c-del' : ''}">${lc ? '−' : ''}</span><span class="${lc ? 'c-del' : ''}">${tl}${lh}</span>` : '<span class="ln c-pad"></span><span class="sg2 c-pad"></span><span class="c-pad"></span>';
  const Rs = rt != null ? `<span class="ln c-mid${rc ? ' c-add' : ''}">${rn}</span><span class="sg2${rc ? ' c-add' : ''}">${rc ? '+' : ''}</span><span class="${rc ? 'c-add' : ''}">${tr}${rh}</span>` : '<span class="ln c-mid c-pad"></span><span class="sg2 c-pad"></span><span class="c-pad"></span>';
  return `<div class="dl">${Ls}${Rs}</div>`;
}
function segDiffBody(L, R, opts) {
  const nL = nameMap(L.participants), nR = nameMap(R.participants);
  const txtL = segTxt(nL, S.diff.tags), txtR = segTxt(nR, S.diff.tags);
  // segBlocks compares with one function, so tag each segment with its side first
  L.segments.forEach(s => { s.__side = 'L'; }); R.segments.forEach(s => { s.__side = 'R'; });
  const blocks2 = D.segBlocks(L.segments, R.segments, s => (s.__side === 'L' ? txtL : txtR)(s));
  let ci = 0; const out = []; const changed = [];
  let stats = { text: 0, tag: 0, merged: 0 };
  // reverted blocks become "same"; keep them visible where they were, keyed by segment id
  const revs = opts.editable ? (S.diff.revs || []) : [];
  const revOf = new Map(), anchors = new Map();
  revs.forEach((r, k) => { r.ids.forEach(id => revOf.set(id, k)); if (!r.ids.length) anchors.set(r.anchor || '^', k); });
  const revLab = k => `<div class="dlab">${ic('revert', 'sm')}<span>${_t('cmp.reverted')}</span><button class="btn" data-act="unrev" data-k="${k}">${_t('undo')}</button></div>`;
  const gone = k => `<div class="dblk rev"><div class="dl"><span class="muted" style="grid-column:1/-1;padding:4px 10px">${_t('cmp.extra_removed')}</span></div>${revLab(k)}</div>`;
  if (anchors.has('^')) out.push(gone(anchors.get('^')));
  blocks2.forEach((b, bi) => {
    if (b.kind === 'same') {
      const line = r => lineHTML(txtL(r.l), txtR(r.r), r.li + 1, r.ri + 1, fmtTs(r.l.start), fmtTs(r.r.start));
      let run = [], runK = null;
      const flush = () => {
        if (!run.length) return;
        if (runK != null) out.push(`<div class="dblk rev">${run.map(line).join('')}${revLab(runK)}</div>`);
        else if (S.diff.only) out.push(`<div class="fold">⋯ ${_t('cmp.same', { n: run.length, nn: num(run.length) })} ⋯</div>`);
        else out.push(`<div class="dblk">${run.map(line).join('')}</div>`);
        run = [];
      };
      b.rows.forEach(r => {
        const k = revOf.has(r.r.id) ? revOf.get(r.r.id) : null;
        if (k !== runK) { flush(); runK = k; }
        run.push(r);
        if (anchors.has(r.r.id)) { flush(); out.push(gone(anchors.get(r.r.id))); runK = null; }
      });
      flush();
      return;
    }
    b.rows.forEach(r => {
      if (r.l && r.r && r.l.id === r.r.id) {
        if ((r.l.text || '') !== (r.r.text || '')) stats.text++;
        if ((r.l.speaker_id || null) !== (r.r.speaker_id || null) || nL[r.l.speaker_id] !== nR[r.r.speaker_id]) stats.tag++;
      } else stats.merged++;
    });
    const idx = ci++; changed.push(bi);
    const lines = b.rows.map(r => lineHTML(r.l ? txtL(r.l) : null, r.r ? txtR(r.r) : null, r.l ? r.li + 1 : '', r.r ? r.ri + 1 : '', r.l ? fmtTs(r.l.start) : '', r.r ? fmtTs(r.r.start) : '')).join('');
    const lab = opts.editable ? `<div class="dlab"><button class="btn" data-act="rev" data-i="${bi}">${ic('revert', 'sm')}${_t('cmp.revert')}</button></div>` : '';
    out.push(`<div class="dblk${idx === S.diff.cur ? ' cur' : ''}" id="blk-${idx}">${lines}${lab}</div>`);
  });
  if (!changed.length) out.unshift(`<div class="center muted" style="padding:30px">${S.diff.tags ? _t('cmp.no_diff') : _t('cmp.no_diff_text')}</div>`);
  return { body: out.join(''), n: changed.length, stats, blocks: blocks2 };
}
function navBar(n) {
  const cur = Math.min(S.diff.cur, Math.max(0, n - 1));
  return `<span class="nv"><button class="iconb" data-act="dnav" data-v="-1" aria-label="${_t('cmp.prev')}">${ic('up')}</button><span class="mono">${n ? cur + 1 : 0} / ${n}</span><button class="iconb" data-act="dnav" data-v="1" aria-label="${_t('cmp.next')}">${ic('down')}</button></span>`;
}
const legend = () => `<span class="leg"><i class="d">−</i>${_t('cmp.removed')}</span><span class="leg"><i class="a">+</i>${_t('cmp.added')}</span>`;
const modeSeg = () => `<div class="segc" role="group" aria-label="${_t('cmp.view')}"><button data-act="dmode" data-v="side" aria-pressed="${S.diff.mode === 'side'}">${ic('cmp', 'sm')}${_t('cmp.side')}</button><button data-act="dmode" data-v="inline" aria-pressed="${S.diff.mode === 'inline'}">${ic('list', 'sm')}Inline</button></div>`;
function statsLine(st, n, verb) {
  return `<b style="color:var(--fg)">${_t(verb, { n, nn: num(n) })}</b>${st.text ? `<span>${_t('cmp.st_text', { n: num(st.text) })}</span>` : ''}${st.tag ? `<span>${_t('cmp.st_tag', { n: num(st.tag) })}</span>` : ''}${st.merged ? `<span>${_t('cmp.st_merged', { n: num(st.merged) })}</span>` : ''}`;
}
function S4c() {
  const e = S.ed, m = S.m;
  if (!e || !S.diff.L) return loadingHTML();
  S.diff.revs = S.diff.revs || [];
  const L = clone(S.diff.L), R = { segments: clone(cleanSegs(e.segs)), participants: clone(e.parts) };
  const r = segDiffBody(L, R, { editable: true });
  S.diff.blocks = r.blocks;
  const opts = diffLeftOptions();
  const leftLbl = (opts.find(o => o[0] === S.diff.left) || opts[0])[1];
  const back = mhash(m.id, e.mode === 'edit' ? 'edit' : 'tinjau');
  return tb(ttl(_t('cmp.title'), esc(m.title)), `<button class="btn" data-go="${back}">${_t('cmp.back_ed')}</button>`, back) +
  `<div class="pane" style="display:flex;flex-direction:column"><div class="dtool"><label>${_t('cmp.left')} <select class="pop" id="d-left" data-ch="dleft">${opts.map(o => `<option value="${o[0]}"${S.diff.left === o[0] ? ' selected' : ''}>${esc(o[1])}</option>`).join('')}</select></label><label>${_t('cmp.right')} <span class="pill p-neutral">${ic('pencil', 'sm')}${_t('cmp.draft_now')}</span></label><span style="flex:1"></span>${modeSeg()}</div>
  <div class="dsum">${statsLine(r.stats, r.n, 'cmp.n_changed')}${legend()}
  <label style="display:inline-flex;gap:6px;align-items:center"><input type="checkbox" id="d-only" data-ch="donly"${S.diff.only ? ' checked' : ''}>${_t('cmp.only')}</label><label style="display:inline-flex;gap:6px;align-items:center"><input type="checkbox" id="d-tags" data-ch="dtags"${S.diff.tags ? ' checked' : ''}>${_t('cmp.tags')}</label>${navBar(r.n)}</div>
  ${S.diff.mode === 'side' ? `<div class="dhead"><div>${ic('doc', 'sm')}${esc(leftLbl)}</div><div>${ic('pencil', 'sm')}${_t('cmp.draft_unsaved')}</div></div>` : `<div class="dhead" style="grid-template-columns:1fr"><div>${_t('cmp.vs', { a: esc(leftLbl), b: _t('cmp.draft_now') })}</div></div>`}
  <div class="diff" style="flex:1;overflow:auto" data-keep="diff">${r.body}</div></div>`;
}

/* ------------------------------------------------------------------ S6 detail */
function dhead(tab) {
  const m = S.m;
  const tabs = [['transkrip', _t('tab.transcript')], ['ringkasan', _t('tab.summary')], ['audio', _t('tab.audio')]];
  const docx = (m.files || []).find(f => f === 'Summary.docx' || f === 'Ringkasan.docx');
  return `<div class="dh"><div class="dh-top"><div style="min-width:0">${S.editTitle ? `<div class="ttl-edit"><input class="field" id="ttl-in" maxlength="${TITLE_MAX}" style="font-size:17px;height:32px;width:420px" value="${esc(m.title)}" data-enter="ttlOk" data-in="ttlin" aria-label="${_t('s2.title_label')}" aria-describedby="ttl-msg"><button class="btn pri" data-act="ttlSave">${_t('save')}</button><button class="btn ghost" data-act="ttlCancel">${_t('cancel_short')}</button></div><div class="fmsg" id="ttl-msg" role="status" hidden></div><div class="fnote">${_t('dh.title_note')}</div>` : `<h1>${esc(m.title)}<button class="iconb" data-act="editTitle" aria-label="${_t('dh.edit_title')}">${ic('pencil', 'sm')}</button></h1>`}
  <div class="meta"><span class="mono">${fmtDate(m.created)}</span>·<span class="mono">${fmtDur(m.duration_sec)}${m.clean_sec && m.settings && m.settings.remove_silence !== false ? ` (${_t('dh.no_silence', { d: fmtDur(m.clean_sec) })})` : ''}</span>·<span>${langName(m.language)}</span>${m.whisper_model ? `·<span title="${_t('s2.model')}">Whisper ${esc(m.whisper_model.name)}</span>` : ''}·<span>${_t('n_segs', { n: m.counts.total, nn: num(m.counts.total) })}</span>${m.claude_suggest ? claudePill(m.claude_suggest) : ''}${m.v1 ? v1Pill() : ''}</div></div>
  <div style="display:flex;gap:6px;flex:none"><button class="btn" data-go="${mhash(m.id, 'edit')}"${m.job ? ' disabled' : ''}>${ic('pencil')}${_t('ed.edit')}</button><button class="btn ghost" data-act="finder">${ic('folder')}${_t('dh.finder')}</button>${docx ? `<button class="btn ghost" data-act="finder" data-file="${esc(docx)}">${ic('dl')}${_t('dh.show_docx')}</button>` : ''}<button class="btn ghost dng" data-act="openM4">${ic('trash')}${_t('delete')}</button></div></div>
  <div class="tabs" role="tablist">${tabs.map(t => `<button class="tab" role="tab" data-go="${mhash(m.id, t[0])}" aria-selected="${tab === t[0]}">${t[1]}${t[0] === 'ringkasan' && m.stale ? `${ic('warn', 'sm')}<span class="sr">${_t('stale')}</span>` : ''}</button>`).join('')}</div></div>`;
}
async function loadVersion(sel) {
  const m = S.m;
  const rev = sel === 'latest' ? m.transcript_rev : sel === 'whisper' ? 0 : +String(sel).slice(1);
  S.ver = await api(`/api/meetings/${encodeURIComponent(m.id)}/transcript?rev=${rev}`);
}
function S6() {
  const m = S.m, v = S.ver;
  if (!v) return dhead('transkrip') + loadingHTML();
  const names = nameMap(v.participants);
  const parts = v.participants || [];
  const segs = v.segments || [];
  const ids = new Set(parts.map(p => p.id));
  const un = segs.filter(s => !ids.has(s.speaker_id)).length;
  const old = S.vsel !== 'latest';
  const vers = [];
  const used = {}; (m.summaries || []).forEach(s => { used[s.based_on_rev] = s.ver; });
  for (let r = m.transcript_rev; r >= 1; r--) vers.push(`<option value="${r === m.transcript_rev ? 'latest' : 'v' + r}"${S.vsel === (r === m.transcript_rev ? 'latest' : 'v' + r) ? ' selected' : ''}>${_t('ver.n', { v: r })}${r === m.transcript_rev ? ` ${_t('ver.latest')}` : ''}${used[r] ? ` · ${_t('ver.used_by', { v: used[r] })}` : ''}</option>`);
  vers.push(`<option value="whisper"${S.vsel === 'whisper' ? ' selected' : ''}>${_t('ver.whisper')}</option>`);
  const q = S.s6q.toLowerCase();
  const rows = segs.filter(s => (!q || (s.text || '').toLowerCase().includes(q)) && (S.s6spk === 'all' || (S.s6spk === 'none' ? !ids.has(s.speaker_id) : s.speaker_id === S.s6spk)));
  const hasAudio = m.audio && m.audio.asli;
  const rowsHTML = rows.slice(0, 3000).map(s => `<div class="rline${S.hl === s.id ? ' hl' : ''}" id="rl-${esc(s.id)}"><button class="ts" data-act="tsPlay" data-id="${esc(s.id)}"${hasAudio ? '' : ' disabled'}>${fmtTs(s.start)}</button><span class="who${names[s.speaker_id] ? '' : ' none'}">${names[s.speaker_id] ? esc(names[s.speaker_id]) : parts.length ? _t('untagged') : '—'}</span><span>${esc(s.text)}${s.secret ? ` <span class="pill p-neutral" style="height:18px">${ic('lock', 'sm')}${_t('ed.secret')}</span>` : ''}</span><button class="iconb" data-act="tsPlay" data-id="${esc(s.id)}" aria-label="${_t('play')}"${hasAudio ? '' : ' disabled'}>${S.playing === s.id ? '<span class="eq"><i></i><i></i><i></i></span>' : ic('play', 'sm')}</button></div>`).join('') || `<div class="muted" style="padding:20px">${_t('s6.no_match')}</div>`;
  const total = segs.length || 1;
  return dhead('transkrip') + `<div class="dbody"><div class="dmain" data-keep="s6">
  ${old ? `<div class="banner">${ic('eye')}<span class="grow"><b>${_t('s6.viewing', { v: S.vsel === 'whisper' ? _t('ver.whisper') : _t('ver.n_low', { v: S.vsel.slice(1) }) })}</b> · ${_t('read_only')}</span><button class="btn" data-act="cmpLatest">${_t('s6.cmp_latest')}</button><button class="btn" data-act="hrestore" data-k="tr" data-v="${S.vsel === 'whisper' ? 0 : S.vsel.slice(1)}">${_t('s6.restore')}</button></div>` : ''}
  ${!old && parts.length && un > 0 ? `<div class="banner info">${ic('person')}<span class="grow">${_t('s6.untagged', { a: `<b class="mono">${num(un)}</b>`, n: segs.length, nn: num(segs.length) })}</span><button class="btn" data-go="${mhash(m.id, 'edit')}">${_t('s6.tag')}</button></div>` : ''}
  ${!old && m.has_draft ? `<div class="banner warn">${ic('pencil')}<span class="grow">${_t('s6.draft')}</span><button class="btn" data-go="${mhash(m.id, 'edit')}">${_t('s6.continue')}</button></div>` : ''}
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><select class="pop" id="s6-ver" data-ch="s6ver" aria-label="${_t('s6.ver')}">${vers.join('')}</select><button class="btn ghost" data-go="${mhash(m.id, 'riwayat-transkrip')}"${(m.versions || []).length > 1 ? '' : ' disabled'}>${ic('cmp')}${_t('cmp.versions')}</button><span style="flex:1"></span><label class="srch"><span class="sr">${_t('s6.search')}</span>${ic('search')}<input class="field" id="s6-q" style="width:200px" placeholder="${_t('s6.search')}…" value="${esc(S.s6q)}" data-in="s6q"></label><select class="pop" id="s6-spk" data-ch="s6spk" aria-label="${_t('s6.filter')}"><option value="all">${_t('s6.all')}</option>${parts.map(p => `<option value="${esc(p.id)}"${S.s6spk === p.id ? ' selected' : ''}>${esc(p.name)}</option>`).join('')}${parts.length ? `<option value="none"${S.s6spk === 'none' ? ' selected' : ''}>${_t('untagged')}</option>` : ''}</select></div>
  <div id="s6-rows">${rowsHTML}</div></div>
  <aside class="eside"><h3>${_t('parts')}</h3>${parts.length ? parts.map(p => { const c = segs.filter(s => s.speaker_id === p.id).length; return `<div style="display:grid;gap:4px;font-size:12.5px"><div style="display:flex;justify-content:space-between;gap:6px"><span>${esc(p.name)}${p.role ? `<span class="muted" style="display:block;font-size:11px">${esc(p.role)}</span>` : ''}</span><span class="mono muted">${num(c)}</span></div><div class="bar thin"><i style="width:${(c / total * 100).toFixed(1)}%"></i></div></div>`; }).join('') +
  `<div style="display:grid;gap:4px;font-size:12.5px"><div style="display:flex;justify-content:space-between"><span class="muted">${_t('untagged')}</span><span class="mono muted">${num(un)}</span></div><div class="bar thin"><i style="width:${(un / total * 100).toFixed(1)}%;background:var(--fg-3)"></i></div></div>` : `<span class="muted" style="font-size:12px">${m.v1 ? _t('s6.v1_no_parts') : _t('s6.no_parts')} ${_t('s6.add_in_ed')}</span>`}
  <span class="muted" style="font-size:11.5px">${_t('s6.parts_hint')}</span></aside></div>`;
}

/* ------------------------------------------------------------------ S6b ringkasan */
async function loadSummary(sel) {
  const m = S.m;
  if (!m.summary_count) { S.sum = null; return; }
  const ver = sel === 'latest' ? m.summary_count : +sel;
  S.sum = await api(`/api/meetings/${encodeURIComponent(m.id)}/summaries/${ver}`);
}
function inline(t) {
  let h = esc(t);
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*(.+?)\*\*(?!\*)/g, '<b>$1</b>');
  h = h.replace(/(^|[^\w])_([^_]+)_(?!\w)/g, '$1<i>$2</i>');
  h = h.replace(/(^|[^*])\*([^*\s][^*]*)\*(?!\*)/g, '$1<i>$2</i>');
  h = h.replace(/\[(\d{2}:\d{2}:\d{2})(?:[–-](\d{2}:\d{2}:\d{2}))?\]/g, (all, a, b) => `<button class="ts" data-act="tsJump" data-t="${a}">${a}</button>${b ? `–<button class="ts" data-act="tsJump" data-t="${b}">${b}</button>` : ''}`);
  return h;
}
function mdToHtml(md) {
  const L = (md || '').split('\n');
  const out = []; let para = [], list = null, table = null;
  const flushP = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; } };
  const flushL = () => { if (list) { out.push(`<${list.t}${list.start > 1 ? ` start="${list.start}"` : ''}>${list.items.map(x => `<li>${inline(x)}</li>`).join('')}</${list.t}>`); list = null; } };
  const flushT = () => {
    if (table) {
      const rows = table.filter(r => !/^\|[\s:|-]+\|$/.test(r.trim())).map(r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim()));
      const [h, ...b] = rows;
      out.push(`<table><thead><tr>${h.map(c => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${b.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
      table = null;
    }
  };
  const flush = () => { flushP(); flushL(); flushT(); };
  let sec = false;
  L.forEach(raw => {
    const t = raw.trim();
    if (t.startsWith('|')) { flushP(); flushL(); (table = table || []).push(t); return; } else flushT();
    // NOTE: a blank line between items keeps the list open (loose list), so numbering does not restart at 1
    if (!t) { flushP(); return; }
    let mm;
    if (t.startsWith('# ')) { flush(); out.push(`<h1>${inline(t.slice(2))}</h1>`); return; }
    if (t.startsWith('## ')) { flush(); if (sec) out.push('</section>'); out.push(`<section><h2>${inline(t.slice(3))}</h2>`); sec = true; return; }
    if (t.startsWith('### ')) { flush(); out.push(`<h3>${inline(t.slice(4))}</h3>`); return; }
    if (t === '---') { flush(); if (sec) { out.push('</section>'); sec = false; } out.push('<hr>'); return; }
    if ((mm = t.match(/^[-*]\s+(.*)$/))) { flushP(); if (!list || list.t !== 'ul') { flushL(); list = { t: 'ul', items: [] }; } list.items.push(mm[1]); return; }
    if ((mm = t.match(/^(\d+)[.)]\s+(.*)$/))) { flushP(); if (!list || list.t !== 'ol') { flushL(); list = { t: 'ol', start: +mm[1], items: [] }; } list.items.push(mm[2]); return; }
    flushL(); para.push(t);
  });
  flush(); if (sec) out.push('</section>');
  return out.join('');
}
function S6b() {
  const m = S.m;
  if (!m.summary_count) return S6d();
  const s = S.sum;
  if (!s) return dhead('ringkasan') + loadingHTML();
  const view = s.info.ver, latest = view === m.summary_count;
  const vs = (m.summaries || []).slice().reverse().map(x => `<option value="${x.ver === m.summary_count ? 'latest' : x.ver}"${x.ver === view ? ' selected' : ''}>${_t('sum.ver', { v: x.ver })}${x.ver === m.summary_count ? ` ${_t('ver.latest')}` : ''} · ${_t('sum.from_tr', { v: x.based_on_rev })}</option>`).join('');
  const red = s.info.redaction || {};
  const masked = Object.values(red.counts || {}).reduce((a, b) => a + b, 0);
  const err = m.summary_error ? `<div class="banner bad">${ic('warn')}<span class="grow"><b>${_t('sum.last_failed')}</b> ${esc(m.summary_error)}</span><button class="btn" data-go="#/pengaturan">${_t('nav.settings')}</button><button class="btn pri" data-act="openM2b">${_t('retry')}</button></div>` : '';
  return dhead('ringkasan') + `<div class="dbody one"><div class="dmain">${err}
  ${!latest ? `<div class="banner">${ic('eye')}<span class="grow"><b>${_t('sum.viewing', { v: view })}</b> · ${_t('read_only')}</span><button class="btn" data-act="scmpLatest">${_t('s6.cmp_latest')}</button><button class="btn" data-act="hrestore" data-k="sum" data-v="${view}">${_t('s6.restore')}</button></div>` :
  (m.stale ? `<div class="banner warn">${ic('warn')}<span class="grow"><b>${_t('sum.stale')}</b> ${_t('sum.stale_text', { a: s.info.based_on_rev, b: m.transcript_rev })}${m.stale_text ? ` (${esc(m.stale_text)})` : ''}.</span><button class="btn pri" data-act="openM2b">${_t('sum.update')}</button></div>` : '')}
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><select class="pop" id="s6b-ver" data-ch="sver" aria-label="${_t('sum.ver_label')}">${vs}</select><span class="muted" style="font-size:12px">${fmtDT(s.info.created)} · ${esc(s.info.model || '')}${s.info.source === 'restore' ? ` · ${_t('sum.restored')}` : ''}${s.info.source === 'v1' ? ` · ${_t('sum.from_v1')}` : ''}</span><button class="btn ghost" data-go="${mhash(m.id, 'riwayat-ringkasan')}"${m.summary_count > 1 ? '' : ' disabled'}>${ic('cmp')}${_t('cmp.versions')}</button><span style="flex:1"></span><button class="btn ghost" data-act="copy">${ic('doc')}${_t('copy')}</button><button class="btn" data-act="openM2b"${m.job ? ' disabled' : ''}>${ic('send')}${_t('sum.redo')}</button></div>
  <article class="doc">${mdToHtml(s.md)}
  <div class="dfoot">${ic('lock', 'sm')}${_t('sum.made_from', { v: s.info.based_on_rev })}${red.withheld ? ` · ${_t('sum.withheld', { n: red.withheld })}` : ''}${masked ? ` · ${_t('sum.masked', { n: masked })}` : ''}</div>
  </article></div></div>`;
}
function S6d() {
  const m = S.m;
  const err = m.summary_error ? `<div class="banner bad" style="justify-self:stretch;text-align:left">${ic('warn')}<span class="grow">${esc(m.summary_error)}</span></div>` : '';
  return dhead('ringkasan') + `<div class="dbody one"><div class="dmain"><div class="center"><div class="s5" style="width:470px"><div class="glyph">${ic('doc', 'lg')}</div><h2>${_t('sum.none')}</h2><p>${_t(AI().local ? 'sum.none_local' : 'sum.none_cloud', { ai: toAI() })}</p>${err}
  <div style="justify-self:stretch;text-align:left"><div class="fgl">${_t('sum.ctx')}</div><textarea class="field" id="ctx-d" rows="2" style="width:100%" placeholder="${_t('sum.ctx_ph')}" data-in="ctx">${esc(S.ctx)}</textarea></div>
  <button class="btn pri lg" data-act="openM2b"${m.job ? ' disabled' : ''}>${_t('sum.make')}</button></div></div></div></div>`;
}

/* ------------------------------------------------------------------ S6c audio */
function S6c() {
  const m = S.m;
  // NOTE: audio already playing from this meeting wins over the saved choice, so label and sound agree
  const loaded = kKind();
  if (loaded && !audio.paused && loaded !== kSrc()) kUseSrc(loaded, false);
  const src = kSrc();
  const lost = m.audio.asli ? '' : `<div class="banner warn">${ic('warn')}<span class="grow">${_t('src.orig_lost')}${m.source_name ? ` (${esc(m.source_name)})` : ''}. ${_t('au.lost_hint')}</span></div>`;
  if (!src) return dhead('audio') + `<div class="dbody one"><div class="dmain kmain">${lost}<div class="banner">${ic('info')}<span class="grow">${_t('au.none')}</span></div><div id="sync-slot"></div></div></div>`;
  const on = audio.dataset.src === audioUrl(m.id, src);
  const playing = on && !audio.paused;
  const pos = on ? audio.currentTime : 0, len = audioLen(src);
  const why = {
    asli: m.audio.asli ? '' : _t('src.orig_lost'),
    bersih: !m.audio.bersih ? _t('au.no_clean') : K.data && K.mid === m.id && !kMapUsable() ? _t('au.map_bad_follow') : '',
  };
  const opt = (k, label) => `<button data-act="asrc" data-a="${k}" aria-pressed="${src === k}"${why[k] ? ` disabled title="${esc(why[k])}"` : ''}>${label}</button>`;
  const sub = src === 'bersih'
    ? `${ic('check', 'sm')}${m.duration_sec && m.clean_sec ? _t('au.removed', { d: fmtDur(m.duration_sec - m.clean_sec) }) + ' · ' : ''}${esc(m.audio.clean_file || 'Silence removed.m4a')} <button class="btn ghost" data-act="finder" data-file="${esc(m.audio.clean_file || 'Silence removed.m4a')}" style="height:22px">${ic('folder', 'sm')}${_t('au.show_finder')}</button>`
    : `${ic('info', 'sm')}${_t('au.full')}${m.source_name ? ` · ${esc(m.source_name)}` : ''}${why.bersih ? ` · ${esc(why.bersih)}` : ''}`;
  const dock = `<div class="adock" role="region" aria-label="${_t('au.player')}"><div class="top"><button class="pbtn" data-act="aplay" data-a="${src}" aria-label="${playing ? _t('pause') : _t('play')}">${ic(playing ? 'pause' : 'play')}</button><div class="segc" role="group" aria-label="${_t('au.source')}">${opt('asli', _t('src.orig'))}${opt('bersih', _t('src.clean'))}</div><span class="mono muted aclock" id="ap-t">${fmtTs(pos)} / ${fmtTs(len)}</span><span class="grow"></span><select class="pop" data-ch="arate" aria-label="${_t('au.speed')}">${[1, 1.25, 1.5, 2].map(r => `<option value="${r}"${audio.playbackRate === r ? ' selected' : ''}>${String(r).replace('.', UI_LANG === 'id' ? ',' : '.')}×</option>`).join('')}</select></div>${scrubHTML(src, pos, len, 'ap-b')}<div class="asub">${sub}</div></div>`;
  return dhead('audio') + `<div class="dbody one"><div class="dmain kmain">${lost}<div id="sync-slot"></div>${dock}</div></div>`;
}
function patchAudio() {
  const m = S.m, k = kSrc(); if (!m || !k || audio.dataset.src !== audioUrl(m.id, k)) return;
  const t = $('#ap-t'), b = $('#ap-b');
  const len = isFinite(audio.duration) ? audio.duration : 0;
  if (t) t.textContent = `${fmtTs(audio.currentTime)} / ${fmtTs(len)}`;
  if (b && !S.scrub) { b.style.width = `${len ? (audio.currentTime / len * 100).toFixed(2) : 0}%`; b.parentElement.setAttribute('aria-valuenow', Math.round(audio.currentTime)); b.parentElement.setAttribute('aria-valuetext', fmtDur(audio.currentTime)); }
}

/* ------------------------------------------------------------------ Interactive Transcript (v1.6) */
const KLEAD = 0.08;   // NOTE: Whisper word times run a little late
const K = { mid: null, data: null, pending: null, el: null, list: null, rows: [], ord: [], starts: null, cut: [],
  cur: -1, curW: -1, past: -1, follow: true, word: true, scroll: 0, progUntil: 0, raf: 0, io: null,
  mapBad: false, err: null, loading: null, src: null, srcMid: null, ask: null };
try { K.word = localStorage.getItem('mn-sync-word') !== '0'; } catch (e) { /* storage blocked */ }
const kToks = t => String(t || '').split(/\s+/).filter(Boolean);
function kRows() { return (K.data && K.data.map && K.data.map.rows) || []; }
function kMapUsable() { return kRows().length > 0 && !K.mapBad; }
function kToOrig(t) {
  const rows = kRows(); if (!rows.length) return t;
  let lo = 0, hi = rows.length - 1, r = 0;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (rows[m][0] <= t) { r = m; lo = m + 1; } else hi = m - 1; }
  const row = rows[r]; return row[1] + Math.min(Math.max(t - row[0], 0), row[2]);
}
function kToClean(o) {
  const rows = kRows(); if (!rows.length) return o;
  let lo = 0, hi = rows.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (rows[m][1] <= o) { r = m; lo = m + 1; } else hi = m - 1; }
  if (r < 0) return rows[0][0];
  const row = rows[r];
  if (o <= row[1] + row[2]) return row[0] + (o - row[1]);
  return r + 1 < rows.length ? rows[r + 1][0] : row[0] + row[2];
}
function kKind() {
  const m = S.m; if (!m) return null;
  if (audio.dataset.src === audioUrl(m.id, 'bersih')) return 'bersih';
  if (audio.dataset.src === audioUrl(m.id, 'asli')) return 'asli';
  return null;
}
const kSrcKey = mid => `mn-audio-src:${mid}`;
// NOTE: the silence-removed audio is the default only when its time map fits the file
function kSrc() {
  const m = S.m; if (!m || !m.audio) return null;
  if (K.srcMid !== m.id) {
    let v = null;
    try { v = localStorage.getItem(kSrcKey(m.id)); } catch (e) { /* storage blocked */ }
    K.src = v || 'auto'; K.srcMid = m.id;
  }
  const canB = m.audio.bersih && (!K.data || K.mid !== m.id || kMapUsable());
  if (K.src === 'asli' && m.audio.asli) return 'asli';
  if (K.src !== 'asli' && canB) return 'bersih';
  return m.audio.asli ? 'asli' : m.audio.bersih ? 'bersih' : null;
}
function kUseSrc(kind, save) {
  const m = S.m; if (!m) return;
  K.src = kind; K.srcMid = m.id;
  if (save) { try { localStorage.setItem(kSrcKey(m.id), kind); } catch (e) { /* ignore */ } }
  if (K.data && K.mid === m.id) { K.cur = -1; K.curW = -1; K.past = -1; kBuild(); }
}
function kSetSrc(kind) {
  const m = S.m; if (!m || kind === kSrc()) return;
  const o = kPos(), was = !!kKind() && !audio.paused;
  kUseSrc(kind, true);
  if (kind !== kSrc()) { render(); return; }
  if (o != null) {
    stopAt = null;
    const t = kind === 'bersih' ? kToClean(o) + 0.001 : o;
    seekTo(audioUrl(m.id, kind), t, () => { if (was) audio.play().catch(() => toast(_t('audio.cannot_play'), null, 'bad')); karUpdate(true); patchAudio(); });
  }
  render();
}
function kPos() {
  const k = kKind(); if (!k || audio.readyState < 1) return null;
  if (k === 'asli') return audio.currentTime;
  return kMapUsable() ? kToOrig(audio.currentTime) : null;
}
async function syncLoad(quiet) {
  const m = S.m; if (!m) return;
  const mid = m.id;
  let d;
  try { d = await api(`/api/meetings/${encodeURIComponent(mid)}/transcript-sync`); K.err = null; }
  catch (e) { if (K.mid !== mid) { K.mid = mid; K.data = null; K.el = null; } K.err = e.status === 409 ? _t('k.no_tr') : e.message; return; }
  if (!S.m || S.m.id !== mid) return;
  if (K.mid !== mid || !K.data) { kAdopt(mid, d); return; }
  if (d.rev === K.data.rev && d.rev_hash === K.data.rev_hash) return;
  const sameText = JSON.stringify(d.segments.map(s => [s.id, s.text, s.start])) === JSON.stringify(K.data.segments.map(s => [s.id, s.text, s.start]));
  if (sameText) { kAdopt(mid, d); if (!quiet) toast(_t('k.updated', { v: d.rev }), null, 'info'); return; }
  // NOTE: new text waits while audio plays, so words do not jump under the listener
  if (kKind() && !audio.paused) { K.pending = d; kPatchTool(); return; }
  kAdopt(mid, d); if (!quiet) toast(_t('k.updated', { v: d.rev }), null, 'info');
}
function kAdopt(mid, d) {
  const keepId = K.data && K.cur >= 0 && K.data.segments[K.cur] ? K.data.segments[K.cur].id : null;
  const keepTop = K.list && keepId ? (() => { const r = K.rows[K.cur]; return r ? r.offsetTop - K.list.scrollTop : null; })() : null;
  if (K.mid !== mid) { K.follow = true; K.scroll = 0; K.mapBad = false; }
  K.mid = mid; K.data = d; K.pending = null; K.cur = -1; K.curW = -1; K.past = -1;
  K.anchor = keepId && keepTop != null ? { id: keepId, top: keepTop } : null;
  kBuild();
}
function kVerText(d) {
  const when = d.created ? ` · ${_t('k.saved', { at: fmtDT(d.created) })}` : '';
  return d.rev ? `${_t('k.tr_v', { v: d.rev })}${when}` : `${_t('k.tr_whisper')}${when}`;
}
function kToolHTML() {
  const d = K.data, m = S.m;
  const notes = [];
  if (m && m.has_draft) notes.push(`<span class="knote">${ic('pencil', 'sm')}${_t('k.draft')}</span>`);
  if (!d.has_words) notes.push(`<span class="knote est" title="${_t('k.est_tip')}">≈ ${_t('k.est')}</span>`);
  if (m && m.audio && m.audio.bersih && !kMapUsable()) notes.push(`<span class="knote warn">${ic('warn', 'sm')}${K.mapBad ? _t('k.map_bad') : _t('k.map_none')}. ${_t('k.follow_orig')}</span>`);
  const pend = K.pending ? `<div class="banner warn kpend">${ic('info')}<span class="grow"><b>${_t('k.pend', { v: K.pending.rev })}</b> ${_t('k.pend_text', { v: d.rev })}</span><button class="btn pri" data-k="loadPending">${_t('k.load', { v: K.pending.rev })}</button></div>` : '';
  const src = kSrc();
  const lab = src ? `<span class="ksrc">${ic('wave', 'sm')}${_t('k.following', { src: src === 'bersih' ? _t('src.clean') : _t('src.orig') })}</span>` : '';
  return `<div class="khead"><h3>Interactive Transcript</h3><span>${_t('k.lead')}</span></div><div class="ktool">${lab}<span class="kver">${ic('doc', 'sm')}${esc(kVerText(d))}</span>${notes.join('')}<span class="grow"></span><label class="kopt"><input type="checkbox" data-k="word"${K.word ? ' checked' : ''}> ${_t('k.word')} <kbd>W</kbd></label><label class="kopt"><input type="checkbox" data-k="follow"${K.follow ? ' checked' : ''}> ${_t('k.follow')} <kbd>F</kbd></label></div>${pend}`;
}
function kPatchTool() { if (!K.el) return; const t = K.el.querySelector('.ktop'); if (t) t.innerHTML = kToolHTML(); }
function kBuild() {
  const d = K.data, segs = d.segments;
  const names = nameMap(d.participants), hasParts = (d.participants || []).length > 0;
  const rows = kRows();
  K.cut = segs.map(s => rows.length > 0 && !rows.some(r => r[1] < s.end - 0.05 && r[1] + r[2] > s.start + 0.05));
  const clean = kSrc() === 'bersih' && kMapUsable();
  const html = segs.map((s, i) => {
    const prev = segs[i - 1];
    const cont = prev && (prev.speaker_id || null) === (s.speaker_id || null) && (!!names[prev.speaker_id] === !!names[s.speaker_id]);
    const nm = names[s.speaker_id];
    const who = hasParts ? `<span class="who${nm ? '' : ' none'}"><span class="av" aria-hidden="true">${nm ? esc(nm.trim()[0] || '?') : '?'}</span><span class="nm">${nm ? esc(nm) : _t('untagged')}</span></span>` : '';
    const extra = (s.secret ? ` <span class="pill p-neutral klock">${ic('lock', 'sm')}${_t('ed.secret')}</span>` : '') + (clean && K.cut[i] ? ` <span class="kcut">${ic('info', 'sm')}${_t('k.not_in_clean')}</span>` : '') + (s.est && d.has_words ? ` <span class="kest" title="${_t('k.seg_est')}">≈</span>` : '');
    const cutSec = clean && prev ? (s.start - prev.end) - (kToClean(s.start) - kToClean(prev.end)) : 0;
    const gap = cutSec > 1 ? `<div class="kgap" aria-hidden="true">${_t('k.gap', { n: Math.round(cutSec) })}</div>` : '';
    const off = clean && K.cut[i];
    const at = clean && !off ? kToClean(s.start) : s.start;
    const tip = !clean ? _t('play_from', { ts: fmtTs(s.start) }) : off ? `${_t('k.not_in_clean')} · ${_t('k.in_orig', { ts: fmtTs(s.start) })}` : _t('k.in_orig_cap', { ts: fmtTs(s.start) });
    return gap + `<div class="kseg${cont ? ' cont' : ''}${hasParts ? '' : ' noparts'}${off ? ' cut' : ''}" role="listitem" data-i="${i}"><button class="ts" data-i="${i}" title="${tip}">${fmtTs(at)}</button>${who}<span class="txt">${esc(kToks(s.text).join(' '))}</span>${extra ? `<span class="kx">${extra}</span>` : ''}</div>`;
  }).join('') || `<div class="muted" style="padding:20px">${_t('k.empty')}</div>`;
  const el = document.createElement('div');
  el.className = 'card tsync';
  el.innerHTML = `<div class="ktop">${kToolHTML()}</div><div class="kwrap"><div class="klist" role="list" aria-label="${_t('k.list')}">${html}</div><button class="btn pri kfollow" data-k="followOn" hidden></button></div><div class="khint">${_t('k.hints')}</div>`;
  K.el = el; K.list = el.querySelector('.klist');
  K.list.classList.toggle('noword', !K.word);
  K.rows = [...K.list.querySelectorAll('.kseg')];
  K.ord = segs.map((s, i) => i).sort((a, b) => segs[a].start - segs[b].start);
  K.starts = Float64Array.from(K.ord.map(i => segs[i].start));
  K.expanded = new Uint8Array(segs.length);
  if (K.io) K.io.disconnect();
  // NOTE: word spans only near the viewport keep a 3-hour transcript light
  K.io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) kExpand(+e.target.dataset.i); }), { root: K.list, rootMargin: '900px 0px' }) : null;
  if (K.io) K.rows.forEach(r => K.io.observe(r)); else K.rows.forEach((r, i) => kExpand(i));
  const user = () => { if (K.follow) kSetFollow(false); };
  K.list.addEventListener('wheel', user, { passive: true });
  K.list.addEventListener('touchmove', user, { passive: true });
  K.list.addEventListener('scroll', () => { K.scroll = K.list.scrollTop; if (performance.now() > K.progUntil && K.follow) kSetFollow(false); else kFollowBtn(); }, { passive: true });
  K.list.addEventListener('click', ev => {
    const sel = window.getSelection && window.getSelection(); if (sel && String(sel).trim()) return;
    const row = ev.target.closest('.kseg'); if (!row) return;
    const i = +row.dataset.i, s = K.data.segments[i];
    const w = ev.target.closest('.w');
    const t = w && s.w[+w.dataset.k] ? s.w[+w.dataset.k][0] : s.start;
    kSeek(t, true, i);
  });
  el.addEventListener('click', ev => {
    const b = ev.target.closest('[data-k]'); if (!b || b.tagName === 'INPUT') return;
    if (b.dataset.k === 'followOn') kSetFollow(true);
    if (b.dataset.k === 'loadPending' && K.pending) { kAdopt(K.mid, K.pending); render(); }
  });
  el.addEventListener('change', ev => {
    const k = ev.target.dataset.k;
    if (k === 'word') kSetWord(ev.target.checked);
    if (k === 'follow') kSetFollow(ev.target.checked);
  });
}
function kExpand(i) {
  if (K.expanded[i]) return;
  const r = K.rows[i], s = K.data.segments[i]; if (!r || !s) return;
  K.expanded[i] = 1;
  r.querySelector('.txt').innerHTML = kToks(s.text).map((t, k) => `<span class="w" data-k="${k}">${esc(t)}</span>`).join(' ');
}
function kMount() {
  if (S.route.name !== 'meeting' || S.route.view !== 'audio') return;
  const slot = document.getElementById('sync-slot'); if (!slot) return;
  if (K.err || !K.el || K.mid !== (S.m && S.m.id)) {
    slot.innerHTML = K.err ? `<div class="banner">${ic('info')}<span class="grow">${esc(K.err)}</span></div>` : '<div class="loading"><span class="spinner"></span></div>';
    return;
  }
  kPatchTool();
  const old = document.querySelector('.tsync'); if (old && old !== K.el) old.remove();
  slot.replaceWith(K.el);
  K.progUntil = performance.now() + 300;
  if (K.anchor) {
    const i = K.data.segments.findIndex(s => s.id === K.anchor.id);
    if (i >= 0) K.scroll = Math.max(0, K.rows[i].offsetTop - K.anchor.top);
    K.anchor = null;
  }
  K.list.scrollTop = K.scroll;
  karUpdate(true);
}
function kSetFollow(f) {
  K.follow = f;
  const c = K.el && K.el.querySelector('[data-k="follow"]'); if (c) c.checked = f;
  if (f) kScroll();
  kFollowBtn();
}
function kSetWord(on) {
  K.word = on; try { localStorage.setItem('mn-sync-word', on ? '1' : '0'); } catch (e) { /* ignore */ }
  if (K.list) K.list.classList.toggle('noword', !on);
  const c = K.el && K.el.querySelector('[data-k="word"]'); if (c) c.checked = on;
  K.curW = -2; karUpdate();
}
function kVisible(i) {
  const r = K.rows[i]; if (!r) return true;
  const a = r.offsetTop, b = a + r.offsetHeight;
  return b > K.list.scrollTop + 8 && a < K.list.scrollTop + K.list.clientHeight - 8;
}
function kFollowBtn() {
  const b = K.el && K.el.querySelector('.kfollow'); if (!b) return;
  if (K.follow || K.cur < 0 || kVisible(K.cur)) { b.hidden = true; return; }
  const below = K.rows[K.cur].offsetTop > K.list.scrollTop + K.list.clientHeight / 2;
  b.textContent = `${_t('k.follow')} ${below ? '↓' : '↑'}`;
  b.hidden = false;
}
function kScroll() {
  if (!K.list || K.cur < 0 || !K.list.isConnected) return;
  const r = K.rows[K.cur];
  const top = Math.max(0, r.offsetTop - K.list.clientHeight * 0.3);
  if (Math.abs(top - K.list.scrollTop) < 4) return;
  K.progUntil = performance.now() + 900;
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const far = Math.abs(top - K.list.scrollTop) > K.list.clientHeight * 3;
  K.list.scrollTo({ top, behavior: reduce || far ? 'auto' : 'smooth' });
}
function kFind(o) {
  let lo = 0, hi = K.starts.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (K.starts[m] <= o) { r = m; lo = m + 1; } else hi = m - 1; }
  return r < 0 ? -1 : K.ord[r];
}
function karUpdate(force) {
  if (!K.el || !K.el.isConnected || !K.data) return;
  const o = kKind() === kSrc() ? kPos() : null;
  const i = o == null ? -1 : kFind(o + KLEAD);
  if (i !== K.cur || force) {
    if (K.cur >= 0 && K.rows[K.cur]) { K.rows[K.cur].classList.remove('on'); K.rows[K.cur].removeAttribute('aria-current'); }
    const np = i < 0 ? -1 : i;
    if (np !== K.past) {
      const a = Math.min(np, K.past) + 1, b = Math.max(np, K.past);
      for (let k = Math.max(0, a - 1); k <= b && k < K.rows.length; k++) K.rows[k].classList.toggle('past', k < np);
      K.past = np;
    }
    K.cur = i; K.curW = -2;
    if (i >= 0) {
      const r = K.rows[i]; kExpand(i); r.classList.add('on'); r.setAttribute('aria-current', 'true');
      if (K.follow) kScroll();
    }
    kFollowBtn();
  }
  let w = -1;
  if (K.word && i >= 0) {
    const s = K.data.segments[i];
    if (o + KLEAD <= s.end + 0.05) for (let k = 0; k < s.w.length; k++) { if (s.w[k][0] <= o + KLEAD) w = k; else break; }
  }
  if (w !== K.curW) {
    const prev = K.list.querySelector('.w.on'); if (prev) prev.classList.remove('on');
    if (i >= 0) {
      const s = K.data.segments[i], heard = w >= 0 ? w : o + KLEAD > s.end ? s.w.length : 0;
      K.rows[i].querySelectorAll('.w').forEach((el, k) => el.classList.toggle('done', k < heard));
      if (w >= 0) { const el = K.rows[i].querySelector(`.w[data-k="${w}"]`); if (el) el.classList.add('on'); }
    }
    K.curW = w;
  }
}
function kLoop() {
  cancelAnimationFrame(K.raf);
  const step = () => { if (audio.paused || S.route.view !== 'audio') return; karUpdate(); K.raf = requestAnimationFrame(step); };
  K.raf = requestAnimationFrame(step);
}
function kSeek(o, play, i) {
  const m = S.m; if (!m) return;
  let kind = kSrc();
  if (!kind) { toast(_t('au.none'), null, 'bad'); return; }
  let moved = false;
  if (kind === 'bersih' && i != null && K.cut[i]) {
    if (!m.audio.asli) { toast(_t('k.cut_lost'), null, 'bad'); return; }
    if (!(K.ask && K.ask.i === i && performance.now() < K.ask.until)) {
      K.ask = { i, until: performance.now() + 5000 };
      toast(_t('k.cut_ask'), null, 'info');
      return;
    }
    K.ask = null; kUseSrc('asli', true); kind = 'asli'; moved = true;
  }
  const src = audioUrl(m.id, kind), t = kind === 'bersih' ? kToClean(o) + 0.001 : o;
  const wasPlaying = !audio.paused;
  stopAt = null;
  if (!K.follow) kSetFollow(true);
  seekTo(src, t, () => {
    if (play || wasPlaying) audio.play().catch(() => toast(_t('audio.cannot_play'), null, 'bad'));
    karUpdate(true); patchAudio();
  });
  if (moved || audio.dataset.src !== src || (play && !wasPlaying)) setTimeout(render, 60);
}
function kStep(d) {
  if (!K.data || !K.data.segments.length) return;
  const o = kPos();
  const segs = K.data.segments;
  let j;
  if (K.cur < 0) j = 0;
  else if (d < 0 && o != null && o - segs[K.cur].start > 1) j = K.cur;
  else {
    const skip = kSrc() === 'bersih' && kMapUsable();
    let p = K.ord.indexOf(K.cur) + d;
    while (skip && p >= 0 && p < K.ord.length && K.cut[K.ord[p]]) p += d;
    j = K.ord[Math.max(0, Math.min(K.ord.length - 1, p))];
  }
  kSeek(segs[j].start, false, j);
}
audio.addEventListener('play', () => { if (S.route.view === 'audio') kLoop(); });
audio.addEventListener('pause', () => {
  cancelAnimationFrame(K.raf);
  if (S.route.view !== 'audio') return;
  karUpdate();
  if (K.pending) { const d = K.pending; kAdopt(K.mid, d); toast(_t('k.updated', { v: d.rev }), null, 'info'); render(); }
});
audio.addEventListener('seeked', () => { if (S.route.view === 'audio') karUpdate(true); });
audio.addEventListener('loadedmetadata', () => {
  const m = S.m; if (!m || !K.data || audio.dataset.src !== audioUrl(m.id, 'bersih')) return;
  const mp = K.data.map;
  // NOTE: a re-run keeps an older silence-removed audio file, so the map must match this file
  const bad = !!(mp && mp.clean_sec && isFinite(audio.duration) && Math.abs(audio.duration - mp.clean_sec) > 0.5);
  if (bad !== K.mapBad) { K.mapBad = bad; kBuild(); if (S.route.view === 'audio') render(); }
});

/* ------------------------------------------------------------------ S5 meringkas */
function S5() {
  const m = S.m, p = m.progress || {};
  if (m.status !== 'summarizing') {
    if (m.summary_error) {
      return tb(ttl(esc(m.title), _t('job.summary')), '', mhash(m.id, 'transkrip')) + `<div class="pane" style="display:flex"><div class="center"><div class="s5"><div class="glyph" style="background:var(--bad-bg);color:var(--bad)">${ic('warn', 'lg')}</div><h2>${_t('s5.fail')}</h2><p>${esc(m.summary_error)} ${_t('s5.tr_same')}</p><div style="display:flex;gap:8px"><button class="btn" data-go="#/pengaturan">${_t('s5.open_settings')}</button><button class="btn pri" data-act="openM2b">${_t('retry')}</button></div></div></div></div>`;
    }
    return loadingHTML();
  }
  const done = ['restore'].includes(p.phase);
  return tb(ttl(esc(m.title), _t('job.summary')), '', '#/riwayat') + `<div class="pane" style="display:flex"><div class="center"><div class="s5"><span class="spinner lg" style="color:var(--accent)"></span><h2>${_t('s5.making')}</h2><p>${_t('s5.hint')}</p>
  <ul class="steps"><li><span class="stp done">${ic('check', 'sm')}</span>${_t('s5.masked', { a: num(p.masked), b: num(p.withheld) })}</li><li><span class="stp done">${ic('check', 'sm')}</span>${AI().local ? _t('s5.words_local', { n: num(p.words) }) : _t('s5.words_sent', { n: num(p.words), p: esc(AI().provider_short) })}</li><li><span class="stp ${done ? 'done' : 'run'}">${done ? ic('check', 'sm') : '<span class="spinner" style="width:10px;height:10px"></span>'}</span>${done ? '' : '<b>'}${_t('s5.waiting', { m: esc(p.model || '') })}${done ? '' : '</b>'}</li><li><span class="stp ${done ? 'run' : ''}">${done ? '<span class="spinner" style="width:10px;height:10px"></span>' : ''}</span><span class="${done ? '' : 'muted2'}">${_t('s5.restore')}</span></li></ul></div></div></div>`;
}

/* ------------------------------------------------------------------ S5s saran AI */
const sugBusy = m => ['queued', 'running'].includes((m.suggest_job || {}).state);
const sugElapsed = j => { const t = Math.max(0, Math.round((Date.now() - Date.parse(j.at)) / 1000)); return `${Math.floor(t / 60)}:${pad(t % 60)}`; };
function S5s() {
  const m = S.m, j = m.suggest_job || {}, back = mhash(m.id, 'edit');
  const head = tb(ttl(_t('sug.ai'), esc(m.title)), '', back);
  if (j.state === 'failed') {
    return head + `<div class="pane" style="display:flex"><div class="center"><div class="s5"><div class="glyph" style="background:var(--bad-bg);color:var(--bad)">${ic('warn', 'lg')}</div><h2>${_t('sug.fail')}</h2><p>${esc(j.error || '')} ${_t('s5.tr_same')}</p><div style="display:flex;gap:8px"><button class="btn" data-go="#/pengaturan">${_t('s5.open_settings')}</button><button class="btn pri" data-act="openM1">${_t('retry')}</button></div></div></div></div>`;
  }
  if (!sugBusy(m)) return loadingHTML();
  const match = j.phase === 'match';
  const run = '<span class="spinner" style="width:10px;height:10px"></span>';
  const steps = j.state === 'queued' ? `<li><span class="stp run">${run}</span><b>${_t('sug.queued')}</b></li>`
    : `<li><span class="stp done">${ic('check', 'sm')}</span>${_t('s5.masked', { a: num(j.masked), b: num(j.withheld) })}</li><li><span class="stp done">${ic('check', 'sm')}</span>${AI().local ? _t('s5.words_local', { n: num(j.words) }) : _t('s5.words_sent', { n: num(j.words), p: esc(AI().provider_short) })}</li><li><span class="stp ${match ? 'done' : 'run'}">${match ? ic('check', 'sm') : run}</span>${match ? '' : '<b>'}${_t('sug.waiting', { m: esc(j.model || '') })}${match ? '' : '</b>'} <span class="muted2 mono" id="sug-el">${sugElapsed(j)}</span></li><li><span class="stp ${match ? 'run' : ''}">${match ? run : ''}</span><span class="${match ? '' : 'muted2'}">${_t('sug.match')}</span></li>`;
  return head + `<div class="pane" style="display:flex"><div class="center"><div class="s5"><span class="spinner lg" style="color:var(--accent)"></span><h2>${_t('sug.asking', { p: esc(AI().provider_short) })}</h2><p>${_t('sug.asking_hint')}</p>
  <ul class="steps">${steps}</ul></div></div></div>`;
}
setInterval(() => {
  const el = S.route.view === 'saran' && S.m && S.m.suggest_job && S.m.suggest_job.at && document.getElementById('sug-el');
  if (el) el.textContent = sugElapsed(S.m.suggest_job);
}, 1000);

/* ------------------------------------------------------------------ S6e / S6f riwayat versi */
async function loadHist(kind) {
  const m = S.m;
  const H = kind === 'tr' ? S.hist : S.shist;
  const latest = kind === 'tr' ? m.transcript_rev : m.summary_count;
  const first = kind === 'tr' ? 0 : 1;
  if (H.mid !== m.id || H.left == null || H.left > latest) { H.mid = m.id; H.right = 'latest'; H.left = Math.max(first, latest - 1); }
  const R = H.right === 'latest' ? latest : H.right;
  if (H.left >= R) H.left = Math.max(first, R - 1);
  if (kind === 'tr') {
    const [a, b] = await Promise.all([H.left, R].map(r => api(`/api/meetings/${encodeURIComponent(m.id)}/transcript?rev=${r}`)));
    H.L = a; H.R = b;
  } else {
    const [a, b] = await Promise.all([H.left, R].map(v => api(`/api/meetings/${encodeURIComponent(m.id)}/summaries/${v}`)));
    H.L = a; H.R = b;
  }
  H.Rn = R;
  S.diff.cur = 0;
}
function histList(kind) {
  const m = S.m;
  if (kind === 'tr') return (m.versions || []).map(v => ({ n: v.rev, label: v.rev === 0 ? _t('ver.whisper') : 'v' + v.rev, date: v.created, note: v.note, used: v.used_by_summary }));
  return (m.summaries || []).map(s => ({ n: s.ver, label: 'v' + s.ver, date: s.created, base: s.based_on_rev, note: s.note }));
}
function vlong(kind, n) {
  const it = histList(kind).find(x => x.n === n) || { label: String(n) };
  const name = kind === 'tr' ? (n === 0 ? _t('ver.whisper') : _t('ver.n', { v: n })) : _t('h.sum_v', { v: n });
  return `${name} · ${fmtDT(it.date)}${kind === 'sum' ? ` · ${_t('sum.from_tr', { v: it.base })}` : (it.used ? ` · ${_t('ver.used_by', { v: it.used })}` : '')}${it.note ? ` · ${esc(it.note)}` : ''}`;
}
function picker(kind, side) {
  const H = kind === 'tr' ? S.hist : S.shist;
  const list = histList(kind);
  const latest = list.length ? list[list.length - 1].n : 0;
  const R = H.Rn, L = H.left;
  const cur = side === 'left' ? L : R;
  return `<div class="vline"><span class="vlab">${side === 'left' ? _t('cmp.left') : _t('cmp.right')}</span>${list.map((v, i) => {
    const dis = side === 'left' ? v.n >= R : v.n <= L;
    return `${i ? '<span class="vcon"></span>' : ''}<button class="vpt" data-act="hpick" data-k="${kind}" data-s="${side}" data-v="${v.n}" aria-pressed="${cur === v.n}"${dis ? ' disabled' : ''}><span class="dot"></span>${esc(v.label)}<span class="vd">${fmtDT(v.date)}${v.n === latest ? ' · ' + _t('h.latest') : ''}</span></button>`;
  }).join('')}</div>`;
}
const rbtn = (kind, n) => `<button class="btn" style="height:22px;font-size:11.5px" data-act="hrestore" data-k="${kind}" data-v="${n}">${ic('revert', 'sm')}${_t('h.restore', { v: kind === 'tr' ? (n === 0 ? _t('ver.whisper') : 'v' + n) : _t('h.sum_v_low', { v: n }) })}</button>`;
function sumDiffBody(a, b) {
  const blocks = D.sumBlocks(a, b);
  let ci = 0; const out = [];
  blocks.forEach(sec => {
    if (!sec.changed) {
      if (S.diff.only) out.push(`<div class="fold">⋯ ${_t('h.sec_same', { s: esc(sec.title) })} ⋯</div>`);
      else out.push(`<div class="dblk"><div class="dsec">${esc(sec.title)} · ${_t('h.unchanged')}</div>${sec.rows.map(r => lineHTML(r.l, r.r, r.li + 1, r.ri + 1)).join('')}</div>`);
      return;
    }
    let hid = 0;
    const lines = sec.rows.map(r => { if (S.diff.only && r.l === r.r) { hid++; return ''; } return lineHTML(r.l, r.r, r.l != null ? r.li + 1 : '', r.r != null ? r.ri + 1 : ''); }).join('');
    const idx = ci++;
    out.push(`<div class="dblk${idx === S.diff.cur ? ' cur' : ''}" id="blk-${idx}"><div class="dsec">${esc(sec.title)}</div>${lines}${hid ? `<div class="fold">⋯ ${_t('h.lines_same', { n: hid, nn: num(hid) })} ⋯</div>` : ''}</div>`);
  });
  return { body: out.join(''), n: ci, total: blocks.length };
}
function histScreen(kind) {
  const m = S.m, H = kind === 'tr' ? S.hist : S.shist;
  const back = mhash(m.id, kind === 'tr' ? 'transkrip' : 'ringkasan');
  if (!H.L || !H.R) return loadingHTML();
  const list = histList(kind);
  const latestN = list.length ? list[list.length - 1].n : 0;
  const latest = H.Rn === latestN;
  let r, sl;
  if (kind === 'tr') { r = segDiffBody(clone(H.L), clone(H.R), { editable: false }); sl = statsLine(r.stats, r.n, 'h.n_diff'); }
  else { r = sumDiffBody(H.L.md, H.R.md); sl = `<b style="color:var(--fg)">${_t('h.parts_changed', { n: r.total, a: r.n })}</b>`; }
  const rTag = latest ? `<span class="pill p-ok">${ic('check', 'sm')}${_t('h.latest')}</span>` : rbtn(kind, H.Rn);
  const hdr = S.diff.mode === 'side' ? `<div class="dhead"><div>${ic('doc', 'sm')}<span class="grow">${vlong(kind, H.left)}</span>${rbtn(kind, H.left)}</div><div>${ic('doc', 'sm')}<span class="grow">${vlong(kind, H.Rn)}</span>${rTag}</div></div>`
    : `<div class="dhead" style="grid-template-columns:1fr"><div style="flex-wrap:wrap"><span>${vlong(kind, H.left)}</span>${rbtn(kind, H.left)}<span class="muted">${_t('h.vs')}</span><span>${vlong(kind, H.Rn)}</span>${rTag}</div></div>`;
  return tb(ttl(kind === 'tr' ? _t('h.tr_title') : _t('h.sum_title'), `${esc(m.title)} · ${_t('read_only')}`), modeSeg(), back) +
  `<div class="pane" style="display:flex;flex-direction:column"><div class="vbox">${picker(kind, 'left')}${picker(kind, 'right')}</div>
  <div class="dsum">${sl}${legend()}<label style="display:inline-flex;gap:6px;align-items:center"><input type="checkbox" id="h-only" data-ch="donly"${S.diff.only ? ' checked' : ''}>${_t('cmp.only')}</label>${kind === 'tr' ? `<label style="display:inline-flex;gap:6px;align-items:center"><input type="checkbox" id="h-tags" data-ch="dtags"${S.diff.tags ? ' checked' : ''}>${_t('cmp.tags')}</label>` : ''}${navBar(r.n)}</div>
  ${hdr}<div class="diff${kind === 'sum' ? ' prose' : ''}" style="flex:1;overflow:auto" data-keep="diff">${r.body}</div>
  <div class="rofoot"><span>${ic('lock', 'sm')} ${_t('h.ro_note')}</span><span>${latest ? _t('h.ro_latest') : _t('h.ro_old')}</span></div></div>`;
}

/* ------------------------------------------------------------------ S7 pengaturan */
async function loadSettings() {
  const [s, l] = await Promise.all([api('/api/settings'), api('/api/send-log?limit=8')]);
  S.settings = s; S.sendlog = l.sends;
}
function S7() {
  const s = S.settings; if (!s) return loadingHTML();
  const c = s.config;
  const f = Object.entries(s.categories);
  const ai = s.ai, pv = ai.providers.find(p => p.id === ai.provider) || ai.providers[0];
  const pname = id => ((ai.providers.find(p => p.id === id) || {}).short) || id;
  const keyRow = S.keyEdit && pv.key ? `<div class="keyin"><input class="field" type="password" id="key-in" style="flex:1" placeholder="${pv.prefix ? esc(pv.prefix) + '…' : 'API key'}" autocomplete="off" data-enter="keySave" aria-label="API key ${esc(pv.short)}"><button class="btn pri" data-act="keySave">${_t('set.key_save')}</button><button class="btn ghost" data-act="keyTog">${_t('cancel_short')}</button></div>` : '';
  const log = S.sendlog.length ? `<table class="sendlog">${S.sendlog.map(x => `<tr><td>${fmtDT(x.at)}</td><td>${x.kind === 'suggest' ? _t('sug.ai') : _t('tab.summary')} · ${esc(x.meeting || '')} · ${esc(pname(x.provider || 'anthropic'))}${x.model ? ` ${esc(x.model)}` : ''} · ${_t('set.log_words', { n: x.words, nn: num(x.words) })} · ${_t('set.log_masked', { n: num(x.masked) })}${x.withheld ? ` · ${_t('set.log_withheld', { n: num(x.withheld) })}` : ''}</td></tr>`).join('')}</table>` : `<span class="muted" style="font-size:12px">${_t('set.log_empty')}</span>`;
  const CONF = [['anthropic', 'yes'], ['openai', 'yes'], ['gemini', 'yes'], ['compat', 'dep'], ['ollama', 'no']];
  const urlRow = pv.id === 'compat' || pv.id === 'ollama' ? `<div class="row"><div class="lb"><label for="ai-url">${_t('set.url')}</label><small>${pv.id === 'ollama' ? _t('set.url_ollama') : _t('set.url_compat')}</small></div><div class="rv"><input class="field mono" id="ai-url" style="width:280px" value="${esc(pv.base_url)}" placeholder="https://…/v1" data-ch="aiurl" spellcheck="false"></div></div>` : '';
  const keyStatus = pv.key ? `<div class="row"><div class="lb">${pv.has_key ? `<span class="conn">${ic('check', 'sm')}${_t('set.key_saved', { p: esc(pv.short) })}</span><small>${_t('set.key_saved_hint')}</small>` : `<span>${_t('set.key_none', { p: esc(pv.short) })}</span><small>${_t('set.key_none_hint')}</small>`}</div><div class="rv">${S.keyMsg ? `<span class="conn">${S.keyMsg}</span>` : ''}<button class="btn" data-act="testConn"${pv.has_key ? '' : ' disabled'}>${_t('set.test')}</button><button class="btn" data-act="keyTog">${pv.has_key ? _t('set.key_change') : _t('set.key_add')}</button>${pv.has_key ? `<button class="btn ghost dng" data-act="keyDel">${_t('delete')}</button>` : ''}</div></div>${keyRow}`
    : `<div class="row"><div class="lb"><span class="conn">${ic('lock', 'sm')}${_t('set.no_key')}</span><small>${_t('set.no_key_hint')}</small></div><div class="rv">${S.keyMsg ? `<span class="conn">${S.keyMsg}</span>` : ''}<button class="btn" data-act="testConn">${_t('set.test')}</button></div></div>`;
  return tb(ttl(_t('nav.settings')), '') + `<div class="pane set"><div class="form">
  <div><div class="fgl">${ic('spark', 'sm')}${_t('set.ai')}</div><div class="group">
   <div class="row"><div class="lb"><label for="ai-prov">${_t('set.prov')}</label><small>${_t('set.prov_hint')}</small></div><div class="rv"><select class="pop" id="ai-prov" data-ch="aiprov">${ai.providers.map(p => `<option value="${p.id}"${p.id === pv.id ? ' selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div></div>
   ${urlRow}${keyStatus}
   <div class="row"><div class="lb"><label for="ai-model">Model</label><small>${pv.models.length ? _t('set.model_pick') : _t('set.model_type')}</small></div><div class="rv"><input class="field mono" id="ai-model" list="ai-models" style="width:220px" value="${esc(pv.model)}" data-ch="aimodel" spellcheck="false" autocomplete="off"><datalist id="ai-models">${pv.models.map(x => `<option value="${esc(x)}"></option>`).join('')}</datalist></div></div>
   ${pv.id === 'gemini' ? `<div class="row"><div class="lb"><span style="color:var(--warn);display:inline-flex;gap:6px;align-items:center">${ic('warn', 'sm')}${_t('set.gemini')}</span><small>${_t('set.gemini_hint')}</small></div></div>` : ''}
  </div>
  <details class="conf"><summary>${ic('lock', 'sm')}${_t('set.conf')}</summary><table class="ctab"><thead><tr><th>${_t('set.prov')}</th><th>${_t('set.conf_out')}</th><th>${_t('set.conf_note')}</th></tr></thead><tbody>${CONF.map(r => `<tr${r[0] === pv.id ? ' class="on"' : ''}><td>${esc(pname(r[0]))}${r[0] === pv.id ? ` <span class="pill p-info mini">${_t('set.in_use')}</span>` : ''}</td><td>${r[1] === 'no' ? ic('lock', 'sm') : ic('send', 'sm')}${_t('set.out_' + r[1])}</td><td>${_t('set.conf_' + r[0])}</td></tr>`).join('')}</tbody></table><p class="muted" style="font-size:11.5px;margin:6px 2px 0">${_t('set.conf_foot')}</p></details></div>
  <div><div class="fgl">${_t('set.view')}</div><div class="group"><div class="row"><div class="lb"><label for="s7-ui">${_t('set.ui_lang')}</label><small>${_t('set.ui_lang_hint')}</small></div><div class="rv"><select class="pop" id="s7-ui" data-ch="uilang">${[['', _t('set.follow_os')], ['id', 'Bahasa Indonesia'], ['en', 'English']].map(o => `<option value="${o[0]}"${((S.state || {}).ui_language || '') === o[0] ? ' selected' : ''}>${o[1]}</option>`).join('')}</select></div></div>
   <div class="row"><div class="lb">${_t('set.theme')}<small>${_t('set.theme_hint')}</small></div><div class="rv"><div class="segc" role="group" aria-label="${_t('set.theme')}">${[['system', _t('set.th_system')], ['light', _t('set.th_light')], ['dark', _t('set.th_dark')]].map(t => `<button data-act="theme" data-v="${t[0]}" aria-pressed="${theme === t[0]}">${t[1]}</button>`).join('')}</div></div></div></div></div>
  <div><div class="fgl">${_t('set.defaults')}</div><div class="group"><div class="row"><div class="lb">${_t('s2.lang')}</div><div class="rv"><select class="pop" data-ch="cfg" data-k="language" aria-label="${_t('s2.lang')}">${LANG_KEYS.map(k => `<option value="${k}"${c.language === k ? ' selected' : ''}>${langName(k)}</option>`).join('')}</select></div></div>
   <div class="row"><div class="lb"><label for="s7-rep">${_t('rep.label')}</label><small>${_t('rep.set_hint')}</small></div><div class="rv"><select class="pop" id="s7-rep" data-ch="cfg" data-k="report_language">${['', 'id', 'en'].map(k => `<option value="${k}"${(c.report_language || '') === k ? ' selected' : ''}>${k ? langName(k) : _t('rep.same')}</option>`).join('')}</select></div></div>
   <div class="row"><div class="lb">${_t('s2.model')}<small>${wmSmall(c.whisper_model || 'cepat')}</small></div><div class="rv"><select class="pop" data-ch="cfg" data-k="whisper_model" aria-label="${_t('s2.model')}">${wmOpt(c.whisper_model || 'cepat')}</select></div></div>
   <div class="row"><div class="lb">${_t('set.sil')}</div><div class="rv"><input class="field mono" id="s7-sil" value="${String(c.min_silence_sec).replace('.', UI_LANG === 'id' ? ',' : '.')}" style="width:56px;text-align:right" data-ch="cfgnum" data-k="min_silence_sec" aria-label="${_t('set.seconds')}"> ${_t('set.seconds_low')}</div></div>
   <div class="row"><div class="lb">${_t('set.wordconf')}<small>${_t('set.wordconf_hint')}</small></div><div class="rv">${sw('wordconf', c.word_confidence, _t('set.wordconf'))}</div></div>
   <div class="row"><div class="lb">${_t('set.terms')}<small>${_t('set.terms_hint')}</small></div><div class="rv" style="flex:1"><input class="field" id="s7-terms" style="width:100%" value="${esc(c.vocabulary)}" data-ch="cfg" data-k="vocabulary" aria-label="${_t('set.terms')}"></div></div></div></div>
  <div><div class="fgl">${ic('lock', 'sm')}${_t('set.filter')}</div><div class="group">
   <div class="row" style="align-items:flex-start"><div class="lb">${_t('set.mask')}<small>${_t('set.mask_hint')}</small></div><div class="rv fgrid">${f.map(x => `<button class="ftog" data-act="ftog" data-f="${x[0]}" aria-pressed="${!!c.redact[x[0]]}"><span class="bx">${c.redact[x[0]] ? ic('check', 'sm') : ''}</span>${_t('cat.' + x[0]) !== 'cat.' + x[0] ? _t('cat.' + x[0]) : esc(x[1])}</button>`).join('')}</div></div>
   <div class="row" style="align-items:flex-start"><div class="lb">${_t('set.words')}<small>${_t('set.words_hint')}</small></div><div class="rv" style="flex:1"><textarea class="field" id="s7-words" rows="3" style="width:100%" data-ch="cfg" data-k="sensitive_words" aria-label="${_t('set.words')}">${esc(c.sensitive_words)}</textarea></div></div></div></div>
  <div><div class="fgl">${_t('set.storage')}</div><div class="group"><div class="row"><div class="lb">${_t('set.folder')}<small class="mono">${esc(homeDir(s.output_root))}</small></div><div class="rv"><button class="btn" data-act="openRoot">${ic('folder')}${_t('open')}</button></div></div>
   <div class="row" style="align-items:flex-start"><div class="lb">${_t('set.log')}<small>${_t('set.log_hint')}</small></div><div class="rv" style="flex:1;max-width:420px">${log}</div></div></div></div>
  <div class="muted" style="font-size:11.5px;padding:0 4px">Meeting Report ${esc((S.state || {}).version || '')} · ${_t('set.local_server')}</div>
  </div></div>`;
}
async function saveCfg(patch, quiet) {
  try {
    S.settings = await api('/api/settings', { method: 'PUT', body: patch });
    await loadState();
    if (!quiet) toast(_t('set.saved'));
    render();
  } catch (e) { fail(e); }
}

/* ------------------------------------------------------------------ sheets */
function filtHTML() {
  const p = S.prev;
  if (!p) return `<div class="filt"><div class="fh">${ic('lock')}<span class="grow">${_t('f.checking')}</span></div></div>`;
  const mark = t => esc(t).replace(/‹[A-Z]+_\d+›/g, x => `<span class="tok">${x}</span>`);
  return `<div class="filt"><div class="fh">${ic('lock')}<span class="grow">${_t('f.summary', { a: num(p.withheld), b: num(p.masked) })}</span><button class="btn ghost" data-act="prev">${ic('eye')}${S.prevOpen ? _t('f.prev_close') : _t('f.prev_open')}</button></div>${S.prevOpen ? `<div class="prev">${mark(p.header)}\n\n${mark(p.transcript)}${p.context ? `\n\n${_t('f.context')}: ${mark(p.context)}` : ''}</div>` : ''}</div>`;
}
const repLang = () => S.repLang || (S.m && S.m.report_lang) || 'id';
const repRow = () => `<div class="row" style="padding:0;border:0"><div class="lb"><label for="rep-lang">${_t('rep.label')}</label><small>${_t('rep.hint')}</small></div><div class="rv"><select class="pop" id="rep-lang" data-ch="replang">${['id', 'en'].map(k => `<option value="${k}"${repLang() === k ? ' selected' : ''}>${langName(k)}</option>`).join('')}</select></div></div>`;
const keyWarn = () => (S.state && !S.state.api_key) ? `<div class="banner warn">${ic('key')}<span class="grow">${_t('f.no_key', { p: esc(AI().provider_short) })}</span><button class="btn" data-act="toSettings">${_t('s5.open_settings')}</button></div>` : '';
const sendTxt = n => AI().local ? _t('f.send_local', { n, m: esc(AI().model) }) : _t('f.send_cloud', { n, p: esc(AI().provider_name), m: esc(AI().model) });
async function loadPreview() {
  S.prev = null; render();
  try { S.prev = await post(`/api/meetings/${encodeURIComponent(S.m.id)}/preview`, { context: S.ctx, ...(S.modal === 'm1' ? {} : { report_language: repLang() }) }); } catch (e) { fail(e); }
  render();
}
function sheet() {
  const m = S.m || {};
  const nWords = S.prev ? num(S.prev.words) : '…';
  if (S.modal === 'm1') return `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sh-t"><h2 id="sh-t"><span class="ico" style="background:var(--claude-bg);color:var(--claude)">${ic('spark', 'lg')}</span>${AI().local ? _t('m1.title_local') : _t('m1.title', { p: esc(AI().provider_short) })}</h2>
  ${S.m1Back ? `<div class="ok">${ic('check', 'sm')}${_t('m1.saved_back', { v: m.transcript_rev })}</div>` : ''}<p>${sendTxt(nWords)} ${_t('m1.body', { v: m.transcript_rev })}</p>${keyWarn()}${filtHTML()}
  <p>${_t('m1.note', { pill: `<b style="color:var(--claude)">${ic('spark', 'sm')} ${_t('pill.ai')}</b>` })}</p>
  <div class="acts"><button class="btn lg" data-act="close">${S.m1Back ? _t('m1.cancel_back') : _t('cancel_short')}</button><button class="btn pri lg" data-act="sendM1"${S.state && S.state.api_key ? '' : ' disabled'}>${_t('m1.send')}</button></div></div>`;
  if (S.modal === 'm2') return `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sh-t"><button class="iconb sh-x" data-act="onlyT" aria-label="${_t('close')}" title="${_t('close_esc')}">${ic('x')}</button><div class="ok">${ic('check', 'sm')}<span class="grow">${_t('m2.saved_opt', { v: m.transcript_rev })}</span><button class="btn ghost" data-act="backEd">${ic('left', 'sm')}${_t('cmp.back_ed')}</button></div><h2 id="sh-t">${_t('m2.title')}</h2>
  <p>${_t('m2.body')} ${sendTxt(nWords)}</p>${keyWarn()}
  <div><div class="fgl">${_t('sum.ctx')}</div><textarea class="field" id="ctx-m2" rows="2" style="width:100%" placeholder="${_t('m2.ctx_ph')}" data-in="ctx">${esc(S.ctx)}</textarea></div>${repRow()}${filtHTML()}
  <div class="acts">${m.claude_suggest ? `<span class="sp">${claudePill(m.claude_suggest)}</span>` : `<button class="btn lg claude sp" data-act="openM1">${ic('spark')}${_t('m2.ai_first')}</button>`}<button class="btn lg" data-act="onlyT">${_t('m2.only_t')}</button><button class="btn pri lg" data-act="startSum"${S.state && S.state.api_key ? '' : ' disabled'}>${_t('sum.make')}</button></div></div>`;
  if (S.modal === 'm2b') {
    const re = m.summary_count > 0;
    return `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sh-t"><h2 id="sh-t"><span class="ico" style="background:var(--accent-soft);color:var(--accent)">${ic('send', 'lg')}</span>${re ? (m.stale ? _t('m2b.t_update') : _t('m2b.t_redo')) : _t('m2b.t_make')}</h2>
    <p>${sendTxt(nWords)} ${_t('m2b.base', { v: m.transcript_rev })}</p>${re ? `<p>${_t('m2b.keep', { a: m.summary_count, b: m.summary_count + 1 })}</p>` : ''}${keyWarn()}
    <div><div class="fgl">${_t('sum.ctx')}</div><textarea class="field" id="ctx-m2b" rows="2" style="width:100%" placeholder="${re ? _t('m2b.ph_re') : _t('m2b.ph')}" data-in="ctx">${esc(S.ctx)}</textarea></div>${repRow()}${filtHTML()}
    <div class="acts"><button class="btn lg" data-act="close">${_t('cancel_short')}</button><button class="btn pri lg" data-act="startSum"${S.state && S.state.api_key ? '' : ' disabled'}>${re ? (m.stale ? _t('sum.update') : _t('sum.redo')) : _t('m2b.make')}</button></div></div>`;
  }
  if (S.modal === 'm4') return `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sh-t"><h2 id="sh-t"><span class="ico" style="background:var(--bad-bg);color:var(--bad)">${ic('trash', 'lg')}</span>${_t('m4.title')}</h2>
  <p>${_t('m4.body', { id: `<b class="mono" style="font-size:12px">${esc(m.id)}</b>`, src: m.source_name ? ` (${esc(m.source_name)})` : '' })}</p><p class="muted">${_t('m4.undo')}</p>
  <div class="acts"><button class="btn lg" data-act="close">${_t('cancel_short')}</button><button class="btn lg danger" data-act="del">${ic('trash')}${_t('m4.do')}</button></div></div>`;
  if (S.modal === 'm5') {
    const li = changeList(S.lastSave || {});
    const sm = (m.summaries || [])[m.summaries.length - 1] || {};
    return `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sh-t"><div class="ok">${ic('check', 'sm')}${_t('m.tr_saved', { v: m.transcript_rev })}</div><h2 id="sh-t"><span class="ico" style="background:var(--warn-bg);color:var(--warn)">${ic('warn', 'lg')}</span>${_t('m2b.t_update')}</h2>
    <p>${_t('m5.body', { a: sm.based_on_rev, b: m.transcript_rev })}</p><ul class="chg">${li.map(x => `<li>${x}</li>`).join('') || `<li>${_t('m5.small')}</li>`}</ul>
    <p class="muted">${_t('m5.later_note')}</p>
    <div class="acts"><button class="btn lg" data-act="later">${_t('m5.later')}</button><button class="btn pri lg" data-act="openM2b">${_t('sum.update')}</button></div></div>`;
  }
  return '';
}

/* ------------------------------------------------------------------ render */
function screenHTML() {
  const r = S.route;
  if (r.name === 'list') return S1();
  if (r.name === 'new') return S2();
  if (r.name === 'settings') return S7();
  if (r.name === 'meeting') {
    if (!S.m || S.m.id !== r.id) return loadingHTML();
    switch (r.view) {
      case 'progres': return S3();
      case 'tinjau': case 'edit': return editorHTML();
      case 'bandingkan': return S4c();
      case 'meringkas': return S5();
      case 'saran': return S5s();
      case 'ringkasan': return S6b();
      case 'audio': return S6c();
      case 'riwayat-transkrip': return histScreen('tr');
      case 'riwayat-ringkasan': return histScreen('sum');
      default: return S6();
    }
  }
  return S1();
}
function render() {
  const app = $('#app');
  const ae = document.activeElement;
  const fid = ae && ae.id && app.contains(ae) ? ae.id : null;
  const sel = fid && ae.selectionStart != null ? [ae.selectionStart, ae.selectionEnd] : null;
  const keep = {};
  app.querySelectorAll('[data-keep]').forEach(el => { keep[el.dataset.keep] = el.scrollTop; });
  app.innerHTML = `<div class="win">${sidebar()}<main class="content">${screenHTML()}</main>${S.modal ? `<div class="scrim"${S.modal === 'm2' ? '' : ' data-act="close"'}></div>${sheet()}` : ''}${toastHTML()}</div>`;
  app.querySelectorAll('[data-keep]').forEach(el => { if (keep[el.dataset.keep] != null) el.scrollTop = keep[el.dataset.keep]; });
  if (fid) { const el = document.getElementById(fid); if (el) { el.focus(); if (sel && el.setSelectionRange) try { el.setSelectionRange(sel[0], sel[1]); } catch (e) { /* not text */ } } }
  const ren = app.querySelector('[id^="ren-"]'); if (ren && !fid) ren.focus();
  const ti = $('#ttl-in'); if (ti && !fid) { ti.focus(); ti.setSelectionRange(ti.value.length, ti.value.length); }
  kMount();
}

/* ------------------------------------------------------------------ actions */
const curMid = () => S.m && S.m.id;
const A = {
  close() { const back = S.m1Back; S.modal = null; S.prevOpen = false; S.m1Back = false; if (back) go(mhash(curMid(), 'edit')); else render(); },
  backEd() { S.modal = null; S.prevOpen = false; go(mhash(curMid(), 'edit')); },
  async saveM1() { await saveTranscript(true); },
  toSettings() { S.modal = null; go('#/pengaturan'); },
  undo() { const u = S.toast && S.toast.undo; S.toast = null; patchToast(); if (u) u(); },
  reload() { route(); },
  async pickFile() {
    try {
      const f = await post('/api/pick-file');
      if (f.cancel) return;
      if (!f.audio) toast(_t('a.not_audio'));
      s2File(f); render();
    } catch (e) { fail(e); }
  },
  s2trim() { S.s2.trim = !S.s2.trim; render(); },
  s2clean() { S.s2.clean = !S.s2.clean; render(); },
  s2rm(el) { S.s2.parts.splice(+el.dataset.i, 1); render(); },
  async process(el) {
    const s = S.s2;
    const bad = titleMsg(s.title);
    if (bad) { s.titleTouched = true; render(); const t = $('#s2-title'); if (t) t.focus(); return; }
    el.disabled = true;
    try {
      const r = await post('/api/meetings', { source_path: s.file.path, title: s.title, language: s.lang, remove_silence: s.trim,
        save_clean_audio: s.clean && s.trim, vocabulary: s.terms, participants: s.parts, audio_track: s.track, whisper_model: s.model });
      S.s2 = null;
      await loadState();
      go(mhash(r.id, 'progres'));
    } catch (e) { el.disabled = false; fail(e); }
  },
  async cancelJob() { try { await post(`/api/meetings/${encodeURIComponent(curMid())}/cancel`); toast(_t('a.stop_after')); } catch (e) { fail(e); } },
  async retry() { try { await post(`/api/meetings/${encodeURIComponent(curMid())}/retry`); S.m = await api(`/api/meetings/${encodeURIComponent(curMid())}`); render(); } catch (e) { fail(e); } },
  toggleLog() { S.logOpen = !S.logOpen; render(); },
  openM4() { S.modal = 'm4'; render(); },
  async del() {
    try { await api(`/api/meetings/${encodeURIComponent(curMid())}`, { method: 'DELETE' }); S.modal = null; S.m = null; toast(_t('a.trashed')); go('#/riwayat'); } catch (e) { fail(e); }
  },
  async finder(el) { try { await post(`/api/meetings/${encodeURIComponent(curMid())}/reveal`, { file: el.dataset.file || '' }); } catch (e) { fail(e); } },
  async openRoot() { try { await post('/api/reveal-root'); } catch (e) { fail(e); } },
  editTitle() { S.editTitle = true; render(); },
  ttlSave() { const t = $('#ttl-in'); if (t) saveTitle(t.value.trim()); },
  ttlCancel() { S.editTitle = false; render(); },
  // editor
  selSeg(el, ev) { if (ev.target.closest('select,button,.stext')) { if (ev.target.closest('.stext')) { S.ed.sel = +el.dataset.i; markSel(); } return; } selSeg(+el.dataset.i); },
  playSeg(el, ev) { ev.stopPropagation(); playSegment(+el.dataset.i); },
  playMain() {
    const e = S.ed, m = S.m;
    if (e.play !== -1) { const old = e.play; stopAudio(); if (old >= 0) patchRow(old); patchPlay(); return; }
    if (e.cursor == null) { playSegment(e.sel); return; }
    e.play = -2;
    playRange(audioUrl(m.id, 'asli'), e.cursor, null);
    patchPlay();
  },
  delSeg(el, ev) { if (ev) ev.stopPropagation(); const e = S.ed; delSegAt(el && el.dataset.i != null ? +el.dataset.i : e.sel); },
  insSeg() {
    const e = S.ed, i = e.sel, g = e.segs[i], nx = e.segs[i + 1];
    const st = g ? g.end : 0, en = nx && nx.start > st ? nx.start : st + 3;
    const undo = insertSeg(i + 1, st, en);
    edTouched(true); focusSeg(i + 1);
    toast(_t('a.ins'), undo, 'info');
  },
  gapPlay(el) {
    const a = +el.dataset.a, b = +el.dataset.b, e = S.ed;
    if (!S.m.audio || !S.m.audio.asli) return;
    const old = e.play; e.play = -2; if (old >= 0) patchRow(old);
    playRange(audioUrl(S.m.id, 'asli'), Math.max(0, a - 0.5), b + 0.5, () => { if (S.ed === e) { e.play = -1; patchPlay(); } });
    patchPlay();
  },
  async gapRe(el) {
    const a = +el.dataset.a, b = Math.min(+el.dataset.b, +el.dataset.a + 600), e = S.ed, mid = curMid();
    S.gapBusy = a.toFixed(1); render();
    try {
      const r = await post(`/api/meetings/${encodeURIComponent(mid)}/retranscribe`, { start: a, end: b });
      S.gapBusy = null;
      if (S.ed !== e) return;
      (e.gapTried = e.gapTried || []).push([a, b]);
      // drop what is already in the transcript nearby (same words within 3 s), so a second
      // try or Whisper re-hearing a neighbouring line never adds a duplicate
      const fresh = r.segments.filter(x => !e.segs.some(s => normTxt(s.text) === normTxt(x.text) && s.start <= x.end + 3 && s.end >= x.start - 3));
      if (!fresh.length) {
        render();
        toast(r.segments.length ? _t('a.gap_dup') : _t('a.gap_none'), null, 'info');
        return;
      }
      const before = clone(e.segs), sel = e.sel, triedBefore = e.gapTried.slice(0, -1);
      fresh.forEach(x => {
        let pos = e.segs.findIndex(s => s.start > x.start); if (pos < 0) pos = e.segs.length;
        insertSeg(pos, x.start, x.end, x.text, { gap_fill: true });
      });
      e.sel = e.segs.findIndex(s => s.gap_fill && s.start >= fresh[0].start - 0.01);
      edTouched(true);
      const el2 = $(`#sg-${e.sel}`); if (el2) el2.scrollIntoView({ block: 'center' });
      const skipped = r.segments.length - fresh.length;
      toast(_t('a.gap_added', { n: fresh.length, nn: num(fresh.length), skip: skipped ? _t('a.gap_skipped', { n: skipped, nn: num(skipped) }) : '' }), () => { e.segs = before; e.sel = sel; e.gapTried = triedBefore; edTouched(true); });
    } catch (err) { S.gapBusy = null; render(); fail(err); }
  },
  gapIns(el) {
    const a = +el.dataset.a, b = +el.dataset.b, e = S.ed;
    let pos = e.segs.findIndex(s => s.start >= b - 0.05); if (pos < 0) pos = e.segs.length;
    const undo = insertSeg(pos, a, b);
    edTouched(true); focusSeg(pos);
    toast(_t('a.ins_gap'), undo, 'info');
  },
  gapSkip(el) { S.ed.gapSkip[(+el.dataset.a).toFixed(1)] = true; render(); },
  gapNext() { const all = document.querySelectorAll('.gaprow'); if (!all.length) return; const e = S.ed; e.gapK = ((e.gapK ?? -1) + 1) % all.length; const g = all[e.gapK]; { g.scrollIntoView({ block: 'center' }); g.classList.add('pulse'); setTimeout(() => g.classList.remove('pulse'), 900); } },
  findNav(el) { findStep(+el.dataset.v); },
  sugNav(el) { sugStep(+el.dataset.v); },
  qpPick(el) { const e = S.ed; e.qp = null; render(); tagSel(el.dataset.id); },
  revSeg(el, ev) { ev.stopPropagation(); const e = S.ed, g = e.segs[+el.dataset.i]; g.text = e.orig[g.id]; edTouched(true); },
  secret(el, ev) { ev.stopPropagation(); const e = S.ed; const g = e.segs[el.dataset.i != null ? +el.dataset.i : e.sel]; if (g) { g.secret = !g.secret; edTouched(true); } },
  merge() {
    const e = S.ed, i = e.sel; if (i >= e.segs.length - 1) { toast(_t('a.merge_last')); return; }
    const a = e.segs[i], b = e.segs[i + 1];
    const before = clone(e.segs);
    a.text = `${a.text.trim()} ${b.text.trim()}`.trim(); a.end = b.end; a.secret = a.secret || b.secret;
    if (!a.speaker_id) a.speaker_id = b.speaker_id;
    e.segs.splice(i + 1, 1);
    edTouched(true);
    toast(_t('a.merged'), () => { e.segs = before; edTouched(true); });
  },
  split() {
    const e = S.ed, i = e.sel, g = e.segs[i]; if (!g) return;
    let pos = null;
    const s = window.getSelection();
    const el = document.querySelector(`[data-ed="${i}"]`);
    if (s && s.rangeCount && el && el.contains(s.anchorNode)) {
      const r = document.createRange(); r.selectNodeContents(el); r.setEnd(s.anchorNode, s.anchorOffset); pos = r.toString().length;
    }
    const text = g.text;
    if (pos == null || pos <= 0 || pos >= text.length) { const mid = Math.floor(text.length / 2); const sp = text.indexOf(' ', mid); pos = sp > 0 ? sp : mid; }
    const t1 = text.slice(0, pos).trim(), t2 = text.slice(pos).trim();
    if (!t1 || !t2) { toast(_t('a.split_where')); return; }
    const before = clone(e.segs);
    const cut = g.start + (g.end - g.start) * (t1.length / Math.max(1, text.length));
    let nid = g.id + 'b', k = 2; const ids = new Set(e.segs.map(x => x.id)); while (ids.has(nid)) nid = g.id + 'b' + (k++);
    e.segs.splice(i + 1, 0, { id: nid, start: +cut.toFixed(2), end: g.end, text: t2, speaker_id: g.speaker_id, secret: g.secret });
    g.text = t1; g.end = +cut.toFixed(2);
    edTouched(true);
    toast(_t('a.split'), () => { e.segs = before; edTouched(true); });
  },
  replAll() {
    const e = S.ed; if (!e.find) return;
    const before = clone(e.segs);
    const re = new RegExp(e.find.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    let n = 0; e.segs.forEach(g => { g.text = g.text.replace(re, () => { n++; return e.repl; }); });
    e.find = ''; e.hit = 0; edTouched(true);
    toast(_t('a.replaced', { n, nn: num(n) }), () => { e.segs = before; edTouched(true); });
  },
  replOne() {
    const e = S.ed, hits = findHits(e), h = hits[e.hit]; if (!h) return;
    const g = e.segs[h.i], before = g.text;
    g.text = g.text.slice(0, h.p) + e.repl + g.text.slice(h.p + e.find.length);
    if (e.hit >= findHits(e).length) e.hit = 0;
    edTouched(true); findStep(0);
    toast(_t('a.replaced', { n: 1, nn: num(1) }), () => { g.text = before; edTouched(true); });
  },
  sugOk(el, ev) { ev.stopPropagation(); applySug(+el.dataset.j); edTouched(true); },
  sugNo(el, ev) { ev.stopPropagation(); S.ed.sugs[+el.dataset.j].st = 'no'; edTouched(true); },
  async sugTerm(el, ev) {
    ev.stopPropagation(); const s = S.ed.sugs[+el.dataset.j];
    applySug(+el.dataset.j);
    try { await post('/api/vocabulary', { term: s.to }); toast(_t('a.term_added', { t: s.to })); } catch (e) { fail(e); }
    edTouched(true);
  },
  acceptAll() { const e = S.ed; e.sugs.forEach((s, j) => { if (s.st === 'open' && s.to) applySug(j); }); edTouched(true); },
  rejectAll() { S.ed.sugs.forEach(s => { if (s.st === 'open') s.st = 'no'; }); edTouched(true); },
  ren(el) { S.ed.ren = +el.dataset.i; render(); },
  nextUn() {
    const e = S.ed; const ids = new Set(e.parts.map(p => p.id));
    for (let k = 1; k <= e.segs.length; k++) { const i = (e.sel + k) % e.segs.length; if (!ids.has(e.segs[i].speaker_id)) { selSeg(i, true); return; } }
  },
  async dropDraft() {
    try { await api(`/api/meetings/${encodeURIComponent(S.ed.mid)}/draft`, { method: 'DELETE' }); S.m.has_draft = false; await loadEditor(S.route.view); toast(_t('a.draft_dropped')); render(); } catch (e) { fail(e); }
  },
  async closeEd() { stopAudio(); await saveDraft(); const dirty = S.ed && edDirty(S.ed); S.ed = null; S.m = await api(`/api/meetings/${encodeURIComponent(curMid())}`); if (dirty) toast(_t('a.draft_kept')); go(mhash(curMid(), 'transkrip')); },
  openDiff() { saveDraft(); S.diff.revs = []; go(mhash(curMid(), 'bandingkan')); },
  async save() { await saveTranscript(); },
  openM1() { S.modal = 'm1'; S.prevOpen = false; loadPreview(); },
  async sendM1() {
    try {
      await post(`/api/meetings/${encodeURIComponent(curMid())}/suggest`, { confirmed: true });
      S.modal = null; S.m1Back = false;
      await saveDraft();
      go(mhash(curMid(), 'saran'));
    } catch (e) { fail(e); }
  },
  async onlyT() { S.modal = null; toast(_t('a.only_t')); go(mhash(curMid(), 'transkrip')); },
  async startSum(el) {
    el.disabled = true;
    try {
      await post(`/api/meetings/${encodeURIComponent(curMid())}/summary`, { confirmed: true, context: S.ctx, report_language: repLang() });
      S.modal = null; S.ctx = ''; S.repLang = null;
      S.m = await api(`/api/meetings/${encodeURIComponent(curMid())}`);
      go(mhash(curMid(), 'meringkas'));
    } catch (e) { el.disabled = false; fail(e); }
  },
  openM2b() { S.modal = 'm2b'; S.prevOpen = false; loadPreview(); },
  later() { S.modal = null; toast(_t('a.stale')); go(mhash(curMid(), 'transkrip')); },
  prev() { S.prevOpen = !S.prevOpen; render(); },
  // detail
  tsPlay(el) {
    const m = S.m, id = el.dataset.id;
    const s = (S.ver.segments || []).find(x => x.id === id); if (!s) return;
    if (S.playing === id) { stopAudio(); render(); return; }
    S.playing = id;
    playRange(audioUrl(m.id, 'asli'), Math.max(0, s.start - 0.2), s.end + 0.3, () => { S.playing = null; render(); });
    render();
  },
  async tsJump(el) {
    const t = tsec(el.dataset.t);
    S.vsel = 'latest'; S.s6q = ''; S.s6spk = 'all';
    await loadVersion('latest');
    const segs = S.ver.segments || [];
    let best = segs[0];
    segs.forEach(s => { if (s.start <= t + 0.5) best = s; });
    S.hl = best && best.id;
    go(mhash(curMid(), 'transkrip'));
    setTimeout(() => { const r = document.getElementById('rl-' + S.hl); if (r) r.scrollIntoView({ block: 'center' }); }, 60);
  },
  cmpLatest() { const H = S.hist; H.mid = curMid(); H.right = 'latest'; H.left = S.vsel === 'whisper' ? 0 : +S.vsel.slice(1); go(mhash(curMid(), 'riwayat-transkrip')); },
  scmpLatest() { const H = S.shist; H.mid = curMid(); H.right = 'latest'; H.left = S.sum.info.ver; go(mhash(curMid(), 'riwayat-ringkasan')); },
  async hrestore(el) {
    const kind = el.dataset.k, v = +el.dataset.v, mid = curMid();
    try {
      if (kind === 'tr') {
        const r = await post(`/api/meetings/${encodeURIComponent(mid)}/restore`, { rev: v });
        S.m = r.meeting; S.vsel = 'latest'; S.ed = null;
        toast(r.changed ? _t('a.restored', { a: v === 0 ? _t('ver.whisper') : _t('ver.n', { v }), v: r.rev }) : _t('a.restored_same'));
        if (r.changed && S.m.summary_count) { S.lastSave = (S.m.stale_changes || {}); }
        if (S.route.view === 'riwayat-transkrip') { S.hist.right = 'latest'; await loadHist('tr'); render(); } else go(mhash(mid, 'transkrip'));
      } else {
        const r = await post(`/api/meetings/${encodeURIComponent(mid)}/summaries/${v}/restore`);
        S.m = r.meeting; S.ssel = 'latest';
        toast(_t('a.restored', { a: _t('h.sum_v', { v }), v: r.ver }));
        if (S.route.view === 'riwayat-ringkasan') { S.shist.right = 'latest'; await loadHist('sum'); render(); } else { await loadSummary('latest'); go(mhash(mid, 'ringkasan')); }
      }
    } catch (e) { fail(e); }
  },
  async hpick(el) {
    const kind = el.dataset.k, side = el.dataset.s, v = +el.dataset.v;
    const H = kind === 'tr' ? S.hist : S.shist;
    const list = histList(kind); const latest = list[list.length - 1].n;
    if (side === 'left') H.left = v; else H.right = v === latest ? 'latest' : v;
    try { await loadHist(kind); } catch (e) { fail(e); }
    render();
  },
  async copy() { try { await navigator.clipboard.writeText(S.sum.md); toast(_t('a.copied')); } catch (e) { toast(_t('a.copy_fail')); } },
  aplay(el) {
    const kind = el.dataset.a, src = audioUrl(curMid(), kind);
    if (audio.dataset.src === src && !audio.paused) { audio.pause(); render(); return; }
    const was = S.route.view === 'audio' ? kKind() : null;
    if (was && was !== kind && kPos() != null) {
      const o = kPos(); stopAt = null;
      seekTo(src, kind === 'bersih' ? kToClean(o) + 0.001 : o, () => audio.play().catch(() => toast(_t('audio.cannot_play'))));
      setTimeout(render, 50); return;
    }
    if (audio.dataset.src !== src) { audio.src = src; audio.dataset.src = src; }
    stopAt = null; audio.play().catch(() => toast(_t('audio.cannot_play'))); setTimeout(render, 50);
  },
  asrc(el) { kSetSrc(el.dataset.a); },
  // diff
  dmode(el) { S.diff.mode = el.dataset.v; render(); },
  dnav(el) {
    const n = document.querySelectorAll('.dblk[id^="blk-"]').length; if (!n) return;
    S.diff.cur = (S.diff.cur + +el.dataset.v + n) % n; render();
    const b = document.getElementById('blk-' + S.diff.cur); if (b) b.scrollIntoView({ block: 'center' });
  },
  rev(el) {
    const e = S.ed, block = S.diff.blocks[+el.dataset.i]; if (!block) return;
    const strip = s => { const x = { ...s }; delete x.__side; return x; };
    const rights = block.rows.filter(r => r.r).map(r => strip(clone(r.r)));
    const res = D.revertBlock(e.segs, block, S.diff.blocks);
    e.segs = res.map(strip);
    const anchor = res.start > 0 ? e.segs[res.start - 1].id : null;
    S.diff.revs.push({ ids: res.ids.slice(), rights, anchor });
    // revert speaker names too when the left side had them
    const L = S.diff.L; (L.participants || []).forEach(p => { if (e.segs.some(s => s.speaker_id === p.id) && !e.parts.find(x => x.id === p.id)) e.parts.push(clone(p)); });
    edTouched(true);
  },
  unrev(el) {
    const e = S.ed, k = +el.dataset.k, r = S.diff.revs[k]; if (!r) return;
    let pos;
    if (r.ids.length) {
      const idset = new Set(r.ids);
      pos = e.segs.findIndex(s => idset.has(s.id));
      e.segs = e.segs.filter(s => !idset.has(s.id));
      if (pos < 0) pos = e.segs.length;
    } else pos = r.anchor ? e.segs.findIndex(s => s.id === r.anchor) + 1 : 0;
    const ids = new Set(e.segs.map(s => s.id));
    e.segs.splice(pos, 0, ...r.rights.map(s => (ids.has(s.id) ? { ...s, id: `${s.id}-u` } : s)));
    S.diff.revs.splice(k, 1);
    edTouched(true);
  },
  // settings
  theme(el) { applyTheme(el.dataset.v); saveCfg({ theme: el.dataset.v }); },
  ftog(el) { const c = S.settings.config; const r = { ...c.redact, [el.dataset.f]: !c.redact[el.dataset.f] }; saveCfg({ redact: r }); },
  wordconf() { saveCfg({ word_confidence: !S.settings.config.word_confidence }); },
  keyTog() { S.keyEdit = !S.keyEdit; S.keyMsg = ''; render(); setTimeout(() => { const k = $('#key-in'); if (k) k.focus(); }, 30); },
  async keySave() {
    const k = $('#key-in'); if (!k || !k.value.trim()) return;
    const provider = S.settings.ai.provider;
    try { await post('/api/settings/api-key', { key: k.value.trim(), provider }); k.value = ''; S.keyEdit = false; S.keyMsg = ''; await loadSettings(); await loadState(); toast(_t('a.key_saved')); render(); } catch (e) { fail(e); }
  },
  async keyDel() {
    const provider = S.settings.ai.provider;
    try { await api(`/api/settings/api-key?provider=${encodeURIComponent(provider)}`, { method: 'DELETE' }); await loadSettings(); await loadState(); toast(_t('a.key_deleted')); render(); } catch (e) { fail(e); }
  },
  async testConn() {
    S.keyMsg = `<span class="spinner"></span> ${_t('a.testing')}`; render();
    try { const r = await post('/api/settings/test-key', { provider: S.settings.ai.provider }); S.keyMsg = r.ok ? `${ic('check', 'sm')}${esc(r.message || _t('a.connected'))}` : `${ic('warn', 'sm')}${esc(r.message)}`; } catch (e) { S.keyMsg = `${ic('warn', 'sm')}${esc(e.message)}`; }
    render();
  },
};
function applySug(j) {
  const e = S.ed, s = e.sugs[j]; if (!s || !s.to) return;
  const g = e.segs.find(x => x.id === s.seg_id); if (!g) return;
  const i = g.text.indexOf(s.from);
  if (i >= 0) g.text = g.text.slice(0, i) + s.to + g.text.slice(i + s.from.length);
  s.st = 'ok';
}
function findStep(d) {
  const e = S.ed, hits = findHits(e); if (!hits.length) return;
  e.hit = ((e.hit + d) % hits.length + hits.length) % hits.length;
  e.sel = hits[e.hit].i;
  render();
  const m = document.querySelector('#seglist mark.fh.cur') || $(`#sg-${e.sel}`);
  if (m) m.scrollIntoView({ block: 'center' });
}
async function saveTitle(v) {
  const msg = titleMsg(v), el = $('#ttl-msg');
  if (msg) { if (el) { el.innerHTML = ic('warn', 'sm') + esc(msg); el.hidden = false; } return; }
  if (v === S.m.title) { S.editTitle = false; render(); return; }
  try {
    const old = S.m.id;
    const m = await api(`/api/meetings/${encodeURIComponent(old)}`, { method: 'PATCH', body: { title: v } });
    S.m = m; S.editTitle = false;
    if (m.id !== old) { S.route.id = m.id; history.replaceState(null, '', mhash(m.id, S.route.view)); }
    toast(m.id !== old ? _t('a.title_folder') : _t('a.title'));
    render();
  } catch (e) { if (el) { el.innerHTML = ic('warn', 'sm') + esc(e.message); el.hidden = false; } else fail(e); }
}
function moveParticipant(from, to) {
  const e = S.ed; if (!e || from === to || to < 0 || to >= e.parts.length) return false;
  const [p] = e.parts.splice(from, 1); e.parts.splice(to, 0, p);
  edTouched(true);
  return true;
}
function markSel() { document.querySelectorAll('.sg.on').forEach(x => x.classList.remove('on')); const el = $(`#sg-${S.ed.sel}`); if (el) el.classList.add('on'); }
async function saveTranscript(thenSuggest) {
  const e = S.ed, m = S.m; if (!e) return;
  clearTimeout(draftT);
  const dirty = edDirty(e);
  const claudeSugs = e.sugs.filter(s => s.kind === 'claude');
  const claude = claudeSugs.length ? { accepted: claudeSugs.filter(s => s.st === 'ok').length, rejected: claudeSugs.filter(s => s.st !== 'ok').length } : null;
  try {
    if (e.mode === 'edit' && !dirty) {
      if (!claude) return;
      S.m = await post(`/api/meetings/${encodeURIComponent(m.id)}/claude-review`, claude);
      S.ed = null; toast(_t('a.sug_done_none')); go(mhash(m.id, 'transkrip'));
      return;
    }
    const local = edChanges(e);
    stopAudio();
    const r = await post(`/api/meetings/${encodeURIComponent(m.id)}/save`, { segments: cleanSegs(e.segs), participants: e.parts, claude });
    S.m = r.meeting; S.ed = null; S.vsel = 'latest';
    if (e.mode === 'review' && thenSuggest) { S.modalNext = 'm1'; S.m1Back = true; S.prevOpen = false; S.prev = null; go(mhash(m.id, 'transkrip')); loadPreview(); return; }
    if (e.mode === 'review') { S.modalNext = 'm2'; S.prevOpen = false; S.prev = null; go(mhash(m.id, 'transkrip')); loadPreview(); return; }
    if (!r.changed) { toast(_t('a.no_change')); go(mhash(m.id, 'transkrip')); return; }
    if (S.m.summary_count) { S.lastSave = local; S.modalNext = 'm5'; go(mhash(m.id, 'transkrip')); return; }
    toast(_t('m.tr_saved', { v: r.rev })); go(mhash(m.id, 'transkrip'));
  } catch (err) { fail(err); }
}

/* ------------------------------------------------------------------ events */
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-act],[data-go]');
  if (!el || el.disabled) return;
  if (el.dataset.act) { const fn = A[el.dataset.act]; if (fn) fn(el, ev); return; }
  ev.preventDefault(); go(el.dataset.go);
});
document.addEventListener('input', ev => {
  const t = ev.target;
  if (t.dataset && t.dataset.ed != null) {
    const e = S.ed; const g = e && e.segs[+t.dataset.ed]; if (!g) return;
    g.text = t.textContent.replace(/\s+/g, ' ').trim();
    edTouched(false);
    return;
  }
  const k = t.dataset && t.dataset.in; if (!k) return;
  if (k === 'q') { S.q = t.value; clearTimeout(A._qT); A._qT = setTimeout(async () => { await loadList(); const tb2 = $('#s1-rows'); if (tb2) tb2.innerHTML = rowsHTML(); }, 200); }
  else if (k === 's2title') {
    S.s2.titleTouched = true;
    S.s2.title = titleInput(t, 's2-title-msg');
    const b = document.querySelector('[data-act="process"]'); if (b) b.disabled = fileBlocked(S.s2.file) || !!S.s2.uploading || !!titleMsg(S.s2.title);
  }
  else if (k === 'ttlin') titleInput(t, 'ttl-msg');
  else if (k === 'qp') { const e = S.ed; e.qp.q = t.value; e.qp.k = 0; const q = document.querySelector('.qp'); if (q) { const v = t.value; q.outerHTML = qpHTML(e); const n = $('#qp-in'); if (n) { n.focus(); n.setSelectionRange(v.length, v.length); } } }
  else if (k === 's2terms') S.s2.terms = t.value;
  else if (k === 'find') { S.ed.find = t.value; S.ed.hit = 0; render(); }
  else if (k === 'repl') S.ed.repl = t.value;
  else if (k === 's6q') { S.s6q = t.value; render(); }
  else if (k === 'ctx') { S.ctx = t.value; clearTimeout(A._cT); A._cT = setTimeout(async () => { if (S.modal && S.prevOpen) { try { S.prev = await post(`/api/meetings/${encodeURIComponent(S.m.id)}/preview`, { context: S.ctx, ...(S.modal === 'm1' ? {} : { report_language: repLang() }) }); render(); } catch (e) { /* ignore */ } } }, 500); }
});
document.addEventListener('change', async ev => {
  const t = ev.target, k = t.dataset && t.dataset.ch; if (!k) return;
  try {
    if (k === 'fstat') { S.fstat = t.value; await loadList(); render(); }
    else if (k === 's2lang') S.s2.lang = t.value;
    else if (k === 's2model') { S.s2.model = t.value; const n = document.getElementById('s2-model-note'); if (n) n.textContent = wmSmall(t.value); }
    else if (k === 's2track') S.s2.track = t.value === 'mix' ? 'mix' : +t.value;
    else if (k === 's2from') { const r = S.recent.find(x => x.id === t.value); if (r) { S.s2.parts = r.participants.map(p => ({ name: p.name, role: p.role || '' })); render(); } }
    else if (k === 'spk') { const e = S.ed; const i = +t.dataset.i; if (e.sel !== i) selSeg(i); tagSel(t.value || null); }
    else if (k === 'onlyHits') { S.ed.onlyHits = t.checked; render(); }
    else if (k === 'doubt') { S.ed.doubt = t.checked; render(); }
    else if (k === 'autoNext') { S.ed.autoNext = t.checked; }
    else if (k === 'aiprov') { S.keyEdit = false; S.keyMsg = ''; await saveCfg({ ai_provider: t.value }, true); toast(_t('a.provider', { p: S.settings.ai.provider_name })); }
    else if (k === 'replang') { S.repLang = t.value; await loadPreview(); }
    else if (k === 'uilang') { setLang(t.value); await saveCfg({ ui_language: t.value }, true); toast(_t('set.saved')); }
    else if (k === 'aimodel') { const v = t.value.trim(); if (v) await saveCfg({ ai_models: { [S.settings.ai.provider]: v } }); }
    else if (k === 'aiurl') { const v = t.value.trim(); if (v && !/^https?:\/\//.test(v)) { toast(_t('a.url_bad'), null, 'bad'); return; } const base = v.replace(/\/+$/, '').replace(/(\/(chat\/completions|completions|responses|models|messages))+$/i, ''); if (base !== v.replace(/\/+$/, '')) { t.value = base; toast(_t('a.url_fixed', { u: base }), null, 'info'); } await saveCfg({ ai_base_url: { [S.settings.ai.provider]: base } }); }
    else if (k === 'dleft') { S.diff.left = t.value; await loadDiffLeft(); render(); }
    else if (k === 'donly') { S.diff.only = t.checked; render(); }
    else if (k === 'dtags') { S.diff.tags = t.checked; render(); }
    else if (k === 's6ver') { S.vsel = t.value; await loadVersion(S.vsel); render(); }
    else if (k === 's6spk') { S.s6spk = t.value; render(); }
    else if (k === 'sver') { S.ssel = t.value; await loadSummary(S.ssel); render(); }
    else if (k === 'arate') { audio.playbackRate = +t.value; }
    else if (k === 'cfg') { await saveCfg({ [t.dataset.k]: t.value }); }
    else if (k === 'cfgnum') { const v = parseFloat(t.value.replace(',', '.')); if (v > 0 && v < 30) await saveCfg({ [t.dataset.k]: v }); else toast(_t('a.num_range', { a: dec(0.5), b: 30 }), null, 'bad'); }
  } catch (e) { fail(e); }
});
function parsePerson(v) { const i = v.indexOf(','); return i > 0 ? { name: v.slice(0, i).trim(), role: v.slice(i + 1).trim() } : { name: v.trim(), role: '' }; }
document.addEventListener('keydown', ev => {
  const t = ev.target;
  if (ev.key === 'Enter' && t.dataset && t.dataset.enter) {
    ev.preventDefault();
    const v = t.value.trim(), k = t.dataset.enter;
    if (k === 's2add' && v) { S.s2.parts.push(parsePerson(v)); t.value = ''; render(); }
    if (k === 'padd' && v) { const e = S.ed; let n = e.parts.length + 1; const ids = new Set(e.parts.map(p => p.id)); while (ids.has('p' + n)) n++; e.parts.push({ id: 'p' + n, ...parsePerson(v) }); t.value = ''; edTouched(true); }
    if (k === 'renOk') { const e = S.ed, p = e.parts[+t.dataset.i]; if (v) Object.assign(p, parsePerson(v)); e.ren = -1; edTouched(true); }
    if (k === 'ttlOk') saveTitle(v);
    if (k === 'keySave') A.keySave();
    return;
  }
  // search box: Enter next hit, Shift+Enter previous
  if (t.id === 'ed-find' && ev.key === 'Enter') { ev.preventDefault(); findStep(S.ed.find && findHits(S.ed).length ? (ev.shiftKey ? -1 : 1) : 0); setTimeout(() => { const f = $('#ed-find'); if (f) f.focus(); }, 0); return; }
  if (t.id === 'ed-find' && ev.key === 'Escape') { S.ed.find = ''; S.ed.hit = 0; render(); return; }
  // quick participant picker (P)
  if (t.id === 'qp-in') {
    const e = S.ed, list = qpList(e);
    if (ev.key === 'Escape') { ev.preventDefault(); e.qp = null; render(); return; }
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { ev.preventDefault(); e.qp.k = Math.max(0, Math.min(list.length - 1, e.qp.k + (ev.key === 'ArrowDown' ? 1 : -1))); const q = document.querySelector('.qp'); if (q) { q.outerHTML = qpHTML(e); const n = $('#qp-in'); if (n) n.focus(); } return; }
    if (ev.key === 'Enter') { ev.preventDefault(); const p = list[e.qp.k]; e.qp = null; render(); if (p) tagSel(p.id); return; }
    return;
  }
  // participant order: arrow keys on the grip handle
  if (t.classList && t.classList.contains('grip') && (ev.key === 'ArrowUp' || ev.key === 'ArrowDown')) {
    ev.preventDefault(); const i = +t.dataset.pi, j = i + (ev.key === 'ArrowUp' ? -1 : 1);
    if (moveParticipant(i, j)) setTimeout(() => { const g = $(`#grip-${j}`); if (g) g.focus(); }, 0);
    return;
  }
  if (ev.key === 'Escape') {
    if (S.modal) { A.close(); return; }
    if (S.ed && S.ed.qp) { S.ed.qp = null; render(); return; }
    if (t.dataset && t.dataset.ed != null) { t.blur(); render(); return; }
    if (S.editTitle) { S.editTitle = false; render(); return; }
    if (S.ed && S.ed.ren >= 0) { S.ed.ren = -1; render(); return; }
  }
  const inEd = S.route.name === 'meeting' && (S.route.view === 'tinjau' || S.route.view === 'edit') && S.ed;
  if ((ev.metaKey || ev.ctrlKey) && ev.key === 's' && inEd) { ev.preventDefault(); if (t.blur) t.blur(); saveTranscript(); return; }
  if ((ev.metaKey || ev.ctrlKey) && ev.key === 'f' && inEd) { ev.preventDefault(); const f = $('#ed-find'); if (f) { f.focus(); f.select(); } return; }
  const typing = t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName);
  // ← → move the audio position: editor, Audio tab, or a focused position bar
  if ((ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') && !typing && !S.modal && !ev.metaKey && !ev.ctrlKey && !ev.altKey && S.m && S.route.name === 'meeting') {
    const d = (ev.key === 'ArrowLeft' ? -1 : 1) * (ev.shiftKey ? 30 : 5);
    const kind = t.dataset && t.dataset.scrub ? t.dataset.scrub : inEd ? 'asli' : S.route.view === 'audio' ? kSrc() : null;
    if (kind && (kind !== 'asli' || (S.m.audio && S.m.audio.asli))) { ev.preventDefault(); nudge(kind, d); return; }
  }
  if (S.route.name === 'meeting' && S.route.view === 'audio' && S.m && K.data && !typing && !S.modal && !ev.metaKey && !ev.ctrlKey && !ev.altKey) {
    const k = ev.key;
    if (k === ' ') {
      ev.preventDefault();
      const kind = kSrc();
      if (kind) A.aplay({ dataset: { a: kind } });
      return;
    }
    if (k === 's' || k === 'S') {
      ev.preventDefault();
      const b = document.querySelector(`[data-act="asrc"][data-a="${kSrc() === 'bersih' ? 'asli' : 'bersih'}"]`);
      if (b && !b.disabled) kSetSrc(b.dataset.a);
      return;
    }
    if (k === 'ArrowUp' || k === 'ArrowDown') { ev.preventDefault(); kStep(k === 'ArrowUp' ? -1 : 1); return; }
    if (k === 'f' || k === 'F') { ev.preventDefault(); kSetFollow(!K.follow); return; }
    if (k === 'w' || k === 'W') { ev.preventDefault(); kSetWord(!K.word); return; }
    if (k === '[' || k === ']') {
      ev.preventDefault();
      const R = [1, 1.25, 1.5, 2], c = R.indexOf(audio.playbackRate);
      audio.playbackRate = R[Math.max(0, Math.min(R.length - 1, (c < 0 ? 0 : c) + (k === '[' ? -1 : 1)))];
      document.querySelectorAll('[data-ch="arate"]').forEach(x => { x.value = String(audio.playbackRate); });
      return;
    }
  }
  if (!inEd || typing || S.modal || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const e = S.ed;
  if (e.qp) return;
  if (ev.key === 'ArrowDown') { ev.preventDefault(); selSeg(e.sel + 1, true); }
  else if (ev.key === 'ArrowUp') { ev.preventDefault(); selSeg(e.sel - 1, true); }
  else if (ev.key === ' ') { ev.preventDefault(); if (e.play !== -1) A.playMain(); else playSegment(e.sel); }
  else if (ev.key === 'Backspace' || ev.key === 'Delete') { ev.preventDefault(); delSegAt(e.sel); }
  else if ((ev.key === 'p' || ev.key === 'P') && e.parts.length) { ev.preventDefault(); e.qp = { q: '', k: 0 }; render(); const q = $('#qp-in'); if (q) q.focus(); }
  else if (ev.key === 'Enter') { ev.preventDefault(); const el = document.querySelector(`[data-ed="${e.sel}"]`); if (el) { el.focus(); const r = document.createRange(); r.selectNodeContents(el); r.collapse(false); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); } }
  else if (/^[1-9]$/.test(ev.key)) { const p = e.parts[+ev.key - 1]; if (p) tagSel(p.id); }
  else if (ev.key === '0') tagSel(null);
  else if (ev.key === 'n' || ev.key === 'N') { ev.preventDefault(); sugStep(ev.shiftKey ? -1 : 1); }
});
document.addEventListener('focusout', ev => { if (ev.target.dataset && ev.target.dataset.ed != null) setTimeout(() => { if (!document.activeElement || document.activeElement.dataset.ed == null) render(); }, 0); });
// drag a participant row to change the order (keys 1–9 follow the order)
document.addEventListener('dragstart', ev => {
  const g = ev.target.closest && ev.target.closest('.grip[draggable]'); if (!g) return;
  S.dragP = +g.dataset.pi;
  ev.dataTransfer.effectAllowed = 'move';
  try { ev.dataTransfer.setData('text/plain', 'peserta'); } catch (e) { /* ignore */ }
  const row = g.closest('.prow'); if (row) { row.classList.add('dragging'); try { ev.dataTransfer.setDragImage(row, 12, 12); } catch (e) { /* ignore */ } }
});
document.addEventListener('dragover', ev => {
  if (S.dragP == null) return;
  const r = ev.target.closest && ev.target.closest('.prow'); if (!r) return;
  ev.preventDefault();
  document.querySelectorAll('.prow.over').forEach(x => { if (x !== r) x.classList.remove('over'); });
  r.classList.add('over');
});
document.addEventListener('drop', ev => {
  if (S.dragP == null) return;
  const r = ev.target.closest && ev.target.closest('.prow');
  const from = S.dragP; S.dragP = null;
  if (r) { ev.preventDefault(); ev.stopImmediatePropagation(); moveParticipant(from, +r.dataset.pi); }
}, true);
document.addEventListener('dragend', () => { S.dragP = null; document.querySelectorAll('.prow.over,.prow.dragging').forEach(x => x.classList.remove('over', 'dragging')); });
// drag and drop a recording anywhere in the window
document.addEventListener('dragover', ev => { if (ev.dataTransfer && [...ev.dataTransfer.types].includes('Files')) { ev.preventDefault(); const d = ev.target.closest && ev.target.closest('.drop'); document.querySelectorAll('.drop.over').forEach(x => { if (x !== d) x.classList.remove('over'); }); if (d) d.classList.add('over'); } });
document.addEventListener('dragleave', ev => { const d = ev.target.closest && ev.target.closest('.drop'); if (d) d.classList.remove('over'); });
document.addEventListener('drop', ev => {
  if (!ev.dataTransfer || !ev.dataTransfer.files.length) return;
  ev.preventDefault();
  const f = ev.dataTransfer.files[0];
  if (S.route.name === 'meeting' && ['tinjau', 'edit'].includes(S.route.view)) return;
  // in the Mac window the launcher sends the dropped file's path (MN.dropPath), so the file is
  // read where it is; a plain browser has no path and falls back to copying it in
  if (window.pywebview) { clearTimeout(A._dropT); A._dropT = setTimeout(() => uploadFile(f), 3000); return; }
  uploadFile(f);
});
window.MN = window.MN || {};
window.MN.dropPath = async path => {
  clearTimeout(A._dropT);
  if (S.route.name === 'meeting' && ['tinjau', 'edit'].includes(S.route.view)) return;
  try {
    const f = await post('/api/file-info', { path });
    if (!S.s2) await initNew(f); else { s2File(f); }
    if (S.route.name !== 'new') go('#/baru'); else render();
  } catch (e) { fail(e); }
};

/* ------------------------------------------------------------------ start */
(async function start() {
  try {
    await loadState();
    if (S.state.theme && S.state.theme !== theme) applyTheme(S.state.theme);
    await loadList();
  } catch (e) {
    $('#app').innerHTML = `<div class="loading">${ic('warn', 'lg')}<div>${esc(e.message)}</div></div>`;
    return;
  }
  connectEvents();
  const q = new URLSearchParams(location.search);
  const open = q.get('open');
  if (open) {
    history.replaceState(null, '', '/' + location.hash);
    try { const f = await post('/api/file-info', { path: open }); await initNew(f); location.hash = '#/baru'; } catch (e) { fail(e); }
  }
  route();
})();
})();
