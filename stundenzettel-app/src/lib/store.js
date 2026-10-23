/**
 * Local data store – everything lives on the device.
 *
 * Storage: IndexedDB (Dexie) with one table per record type and indexes, so the app stays fast
 * with hundreds of projects and many years of entries. Entries are loaded per project on demand.
 * Fallbacks: localStorage (small data sets) and in-memory (nothing persists, user is warned).
 *
 * In-memory model: companies / projects / invoices are always loaded; entries are cached per project.
 * Projects carry pre-computed stats (total_minutes, entry_count, last_activity_at) so the project
 * list never needs to touch the entries table.
 */
import { useEffect, useReducer } from 'react';
import Dexie from 'dexie';
import { get as kvGet, del as kvDel } from 'idb-keyval';
import { uid } from './utils';
import { calcNetMinutes, entryMinutes, entryWorkers, MIN_KEY, MAX_KEY } from './dates';

const DB_NAME = 'stundenzettel';
const LEGACY_KV_KEY = 'stundenzettel-v1';
const LS_KEY = 'stundenzettel-local-v2';
const TABLES = ['companies', 'projects', 'entries', 'invoices'];

export const COMPANY_DEFAULTS = {
  name: '', owner: '', street: '', zip_code: '', city: '', phone: '', email: '', website: '',
  tax_number: '', vat_id: '', bank_name: '', iban: '', bic: '',
  default_hourly_rate: 0, vat_rate: 19, small_business: false,
  invoice_prefix: 'RE-', payment_days: 14,
  invoice_text: 'Reinigungsarbeiten laut beiliegenden Stundenzetteln',
  logo: null, logo_w: 0, logo_h: 0,
  stamp: null, stamp_w: 0, stamp_h: 0, stamp_on_sheet: true, stamp_on_invoice: true, stamp_scale: 100, stamp_config: null,
};

export const PROJECT_DEFAULTS = {
  name: '', color: '#C41E3A', customer_name: '', customer_address: '', employee_name: '',
  hourly_rate: 0, notes: '', archived: false, default_workers: 1,
  total_minutes: 0, entry_count: 0, last_activity_at: null,
};

const now = () => new Date().toISOString();
const sortEntries = (arr) => arr.sort((a, b) => (a.date + a.start_time).localeCompare(b.date + b.start_time));
const byCreated = (a, b) => String(a.created_at || '').localeCompare(String(b.created_at || ''));

// ============================================================
// storage backends
// ============================================================

class DexieBackend {
  constructor() {
    this.db = new Dexie(DB_NAME);
    this.db.version(1).stores({
      companies: 'id, created_at',
      projects: 'id, company_id, archived',
      entries: 'id, project_id, [project_id+date]',
      invoices: 'id, company_id, project_id, [company_id+year]',
      meta: 'key',
    });
  }
  async open() { await this.db.open(); }
  async loadCore() {
    const [companies, projects, invoices, meta] = await Promise.all([
      this.db.companies.toArray(), this.db.projects.toArray(), this.db.invoices.toArray(), this.db.meta.toArray(),
    ]);
    return { companies, projects, invoices, meta: Object.fromEntries(meta.map((m) => [m.key, m.value])) };
  }
  loadEntries(projectId) { return this.db.entries.where('project_id').equals(projectId).toArray(); }
  put(table, obj) { return this.db.table(table).put(obj); }
  bulkPut(table, objs) { return objs.length ? this.db.table(table).bulkPut(objs) : Promise.resolve(); }
  delete(table, id) { return this.db.table(table).delete(id); }
  deleteWhere(table, field, values) { return values.length ? this.db.table(table).where(field).anyOf(values).delete() : Promise.resolve(); }
  setMeta(key, value) { return this.db.meta.put({ key, value }); }
  async exportAll() {
    const [companies, projects, entries, invoices] = await Promise.all(TABLES.map((t) => this.db.table(t).toArray()));
    return { companies, projects, entries, invoices };
  }
  replaceAll(data) {
    return this.db.transaction('rw', this.db.companies, this.db.projects, this.db.entries, this.db.invoices, async () => {
      for (const t of TABLES) { await this.db.table(t).clear(); await this.db.table(t).bulkPut(data[t] || []); }
    });
  }
  mergeAll(data) {
    return this.db.transaction('rw', this.db.companies, this.db.projects, this.db.entries, this.db.invoices, async () => {
      for (const t of TABLES) await this.db.table(t).bulkPut(data[t] || []);
    });
  }
  async isEmpty() { return (await this.db.companies.count()) === 0 && (await this.db.projects.count()) === 0; }
}

/** Small-data fallback when IndexedDB is not available (private mode, very old browsers). */
class LocalStorageBackend {
  constructor() { this.data = { companies: [], projects: [], entries: [], invoices: [], meta: {} }; }
  async open() {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) Object.assign(this.data, JSON.parse(raw));
    this.save();
  }
  save() { localStorage.setItem(LS_KEY, JSON.stringify(this.data)); }
  async loadCore() { const { companies, projects, invoices, meta } = this.data; return { companies: [...companies], projects: [...projects], invoices: [...invoices], meta: { ...meta } }; }
  async loadEntries(projectId) { return this.data.entries.filter((e) => e.project_id === projectId); }
  async put(table, obj) { const arr = this.data[table]; const i = arr.findIndex((x) => x.id === obj.id); if (i >= 0) arr[i] = obj; else arr.push(obj); this.save(); }
  async bulkPut(table, objs) { for (const o of objs) { const arr = this.data[table]; const i = arr.findIndex((x) => x.id === o.id); if (i >= 0) arr[i] = o; else arr.push(o); } this.save(); }
  async delete(table, id) { this.data[table] = this.data[table].filter((x) => x.id !== id); this.save(); }
  async deleteWhere(table, field, values) { const set = new Set(values); this.data[table] = this.data[table].filter((x) => !set.has(x[field])); this.save(); }
  async setMeta(key, value) { this.data.meta[key] = value; this.save(); }
  async exportAll() { const { companies, projects, entries, invoices } = this.data; return { companies: [...companies], projects: [...projects], entries: [...entries], invoices: [...invoices] }; }
  async replaceAll(data) { for (const t of TABLES) this.data[t] = [...(data[t] || [])]; this.save(); }
  async mergeAll(data) { for (const t of TABLES) await this.bulkPut(t, data[t] || []); }
  async isEmpty() { return this.data.companies.length === 0 && this.data.projects.length === 0; }
}

class MemoryBackend extends LocalStorageBackend {
  async open() { /* nothing to load */ }
  save() { /* nothing persists */ }
}

// ============================================================
// in-memory state
// ============================================================

let backend = null;
let state = { companies: [], projects: [], invoices: [], meta: {} };
let entryCache = new Map(); // projectId -> sorted entries
let ready = false;
let version = 0;
const storage = { mode: 'idb', error: null };
const listeners = new Set();
const emit = () => { version += 1; listeners.forEach((fn) => fn()); };

/** Report write failures (e.g. quota exceeded) to the UI instead of losing them silently. */
function persist(promise) {
  return Promise.resolve(promise).catch((err) => {
    console.error('Speicherfehler', err);
    storage.error = err?.message || String(err);
    emit();
  });
}

function setState(patch) {
  state = { ...state, ...patch };
  emit();
}

/** React hook: re-renders on every change. */
export function useStore() {
  const [, force] = useReducer((x) => x + 1, 0);
  useEffect(() => { listeners.add(force); return () => listeners.delete(force); }, []);
  return { state, ready, version, storage };
}

export const getState = () => state;
export const storageInfo = () => ({ ...storage });

// ---------- normalisation ----------

const normaliseCompany = (c) => ({ ...COMPANY_DEFAULTS, ...c });
const normaliseProject = (p) => ({ ...PROJECT_DEFAULTS, ...p, total_minutes: Number(p.total_minutes) || 0, entry_count: Number(p.entry_count) || 0 });

/** Recompute project stats from a complete list of entries. */
function statsFromEntries(entries) {
  const stats = {};
  for (const e of entries) {
    const st = (stats[e.project_id] ||= { total_minutes: 0, entry_count: 0, last_activity_at: null });
    st.total_minutes += entryMinutes(e);
    st.entry_count += 1;
    if (!st.last_activity_at || e.date > st.last_activity_at) st.last_activity_at = e.date;
  }
  return stats;
}

function applyStats(projects, stats) {
  return projects.map((p) => ({ ...p, ...(stats[p.id] || { total_minutes: 0, entry_count: 0, last_activity_at: null }) }));
}

/** Clean up an imported / legacy data set: defaults, ids, stats, company links. */
function normaliseDataset(raw) {
  const data = {};
  for (const t of TABLES) data[t] = Array.isArray(raw?.[t]) ? raw[t].filter((x) => x && typeof x === 'object') : [];
  data.companies = data.companies.map((c) => normaliseCompany({ ...c, id: c.id || uid(), created_at: c.created_at || now() }));
  const companyIds = new Set(data.companies.map((c) => c.id));
  const fallbackCompany = data.companies[0]?.id || null;
  data.projects = data.projects
    .map((p) => normaliseProject({ ...p, id: p.id || uid(), created_at: p.created_at || now(), company_id: companyIds.has(p.company_id) ? p.company_id : fallbackCompany }))
    .filter((p) => p.company_id);
  const projectIds = new Set(data.projects.map((p) => p.id));
  data.entries = data.entries
    .filter((e) => projectIds.has(e.project_id) && e.date && e.start_time && e.end_time)
    .map((e) => ({ activity: '', pause_minutes: 0, ...e, id: e.id || uid(), net_minutes: Number(e.net_minutes) || calcNetMinutes(e.start_time, e.end_time, e.pause_minutes) }));
  const projectCompany = Object.fromEntries(data.projects.map((p) => [p.id, p.company_id]));
  data.invoices = data.invoices
    .filter((i) => projectIds.has(i.project_id) && i.number)
    .map((i) => ({ ...i, id: i.id || uid(), company_id: i.company_id || projectCompany[i.project_id] }));
  data.projects = applyStats(data.projects, statsFromEntries(data.entries));
  return data;
}

// ============================================================
// loading
// ============================================================

async function openBackend() {
  try {
    const b = new DexieBackend();
    await b.open();
    storage.mode = 'idb';
    return b;
  } catch (err) {
    console.warn('IndexedDB nicht verfügbar, nutze localStorage', err);
  }
  try {
    const b = new LocalStorageBackend();
    await b.open();
    storage.mode = 'local';
    return b;
  } catch (err) {
    console.warn('localStorage nicht verfügbar, Daten werden nicht gespeichert', err);
  }
  storage.mode = 'memory';
  return new MemoryBackend();
}

/** One-time migration from the first app version (single idb-keyval blob). */
async function migrateLegacy() {
  if (!(await backend.isEmpty())) return;
  let legacy = null;
  try { legacy = await kvGet(LEGACY_KV_KEY); } catch { return; }
  if (!legacy) return;
  const data = normaliseDataset(legacy);
  await backend.replaceAll(data);
  try { await kvDel(LEGACY_KV_KEY); } catch { /* ignore */ }
}

async function reloadCore() {
  const core = await backend.loadCore();
  state = {
    companies: core.companies.map(normaliseCompany).sort(byCreated),
    projects: core.projects.map(normaliseProject).sort(byCreated),
    invoices: core.invoices,
    meta: core.meta || {},
  };
  entryCache = new Map();
  ready = true;
  emit();
}

export async function loadState() {
  if (ready) return;
  backend = await openBackend();
  try { await migrateLegacy(); } catch (err) { console.warn('Migration fehlgeschlagen', err); }
  await reloadCore();
  try { navigator.storage?.persist?.(); } catch { /* ignore */ }
  backfillLogoSizes();
}

/** Older records stored the logo without its size; measure once and save it (PDFs need it synchronously). */
function backfillLogoSizes() {
  if (typeof Image === 'undefined') return;
  for (const c of state.companies) {
    if (!c.logo || (c.logo_w && c.logo_h)) continue;
    const img = new Image();
    img.onload = () => updateCompany(c.id, { logo_w: img.naturalWidth, logo_h: img.naturalHeight });
    img.src = c.logo;
  }
}

// ============================================================
// meta
// ============================================================

export function setMeta(key, value) {
  setState({ meta: { ...state.meta, [key]: value } });
  return persist(backend.setMeta(key, value));
}

// ============================================================
// companies
// ============================================================

export const findCompany = (id) => state.companies.find((c) => c.id === id) || null;

export function addCompany(data) {
  const c = normaliseCompany({ ...data, id: uid(), created_at: now() });
  setState({ companies: [...state.companies, c] });
  persist(backend.put('companies', c));
  return c;
}

export function updateCompany(id, data) {
  let out = null;
  const companies = state.companies.map((c) => (c.id === id ? (out = normaliseCompany({ ...c, ...data, id })) : c));
  if (!out) return null;
  setState({ companies });
  persist(backend.put('companies', out));
  return out;
}

export function deleteCompany(id) {
  const pids = state.projects.filter((p) => p.company_id === id).map((p) => p.id);
  for (const pid of pids) entryCache.delete(pid);
  setState({
    companies: state.companies.filter((c) => c.id !== id),
    projects: state.projects.filter((p) => p.company_id !== id),
    invoices: state.invoices.filter((i) => i.company_id !== id),
  });
  persist((async () => {
    await backend.deleteWhere('entries', 'project_id', pids);
    await backend.deleteWhere('invoices', 'company_id', [id]);
    await backend.deleteWhere('projects', 'company_id', [id]);
    await backend.delete('companies', id);
  })());
}

// ============================================================
// projects
// ============================================================

export const findProject = (id) => state.projects.find((p) => p.id === id) || null;

/** Projects of a company (stats are stored on the record, no entry scan needed). */
export const companyProjects = (companyId) => state.projects.filter((p) => p.company_id === companyId);

export function addProject(data) {
  const company = findCompany(data.company_id);
  const p = normaliseProject({ ...data, id: uid(), created_at: now(), total_minutes: 0, entry_count: 0, last_activity_at: null });
  if (!p.hourly_rate) p.hourly_rate = Number(company?.default_hourly_rate) || 0;
  setState({ projects: [...state.projects, p] });
  persist(backend.put('projects', p));
  entryCache.set(p.id, []);
  return p;
}

export function updateProject(id, data) {
  let out = null;
  const projects = state.projects.map((p) => (p.id === id ? (out = normaliseProject({ ...p, ...data, id })) : p));
  if (!out) return null;
  setState({ projects });
  persist(backend.put('projects', out));
  return out;
}

export function deleteProject(id) {
  entryCache.delete(id);
  setState({
    projects: state.projects.filter((p) => p.id !== id),
    invoices: state.invoices.filter((i) => i.project_id !== id),
  });
  persist((async () => {
    await backend.deleteWhere('entries', 'project_id', [id]);
    await backend.deleteWhere('invoices', 'project_id', [id]);
    await backend.delete('projects', id);
  })());
}

/** Refresh the stored stats of a project from its (loaded) entry cache. */
function syncProjectStats(projectId) {
  const arr = entryCache.get(projectId);
  if (!arr) return;
  const st = statsFromEntries(arr)[projectId] || { total_minutes: 0, entry_count: 0, last_activity_at: null };
  updateProject(projectId, st);
}

// ============================================================
// entries (cached per project)
// ============================================================

const loading = new Map();

/** Load the entries of a project into the cache (once). */
export function ensureEntries(projectId) {
  if (!projectId || !ready || entryCache.has(projectId)) return Promise.resolve();
  if (loading.has(projectId)) return loading.get(projectId);
  const p = backend.loadEntries(projectId)
    .then((rows) => { if (!entryCache.has(projectId)) entryCache.set(projectId, sortEntries(rows)); })
    .catch((err) => { console.error(err); storage.error = err?.message || String(err); })
    .finally(() => { loading.delete(projectId); emit(); });
  loading.set(projectId, p);
  return p;
}

export const entriesLoaded = (projectId) => entryCache.has(projectId);

/** Entries of a project in a date range (requires ensureEntries first; returns [] until loaded). */
export function projectEntries(projectId, startKey = MIN_KEY, endKey = MAX_KEY) {
  const arr = entryCache.get(projectId) || [];
  if (startKey <= MIN_KEY && endKey >= MAX_KEY) return arr;
  return arr.filter((e) => e.date >= startKey && e.date <= endKey);
}

/** Hook: loads the project's entries and re-renders on changes. */
export function useProjectEntries(projectId) {
  const { version: v } = useStore();
  useEffect(() => { ensureEntries(projectId); }, [projectId, v]);
  return { entries: entryCache.get(projectId) || [], loaded: entryCache.has(projectId), version: v };
}

function validateEntry(e) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(e.date) || e.date < MIN_KEY || e.date > MAX_KEY) throw new Error(`Datum muss zwischen ${MIN_KEY.slice(0, 4)} und ${MAX_KEY.slice(0, 4)} liegen`);
  if (!/^\d{2}:\d{2}$/.test(e.start_time) || !/^\d{2}:\d{2}$/.test(e.end_time)) throw new Error('Uhrzeit im Format HH:MM eingeben');
  if (e.pause_minutes < 0 || e.pause_minutes > 1440) throw new Error('Pause ungültig');
  if ((e.activity || '').length > 500) throw new Error('Tätigkeit ist zu lang (max. 500 Zeichen)');
}

export function addEntry(data) {
  if (!entryCache.has(data.project_id)) throw new Error('Einträge werden noch geladen, bitte kurz warten');
  const e = { activity: '', pause_minutes: 0, workers: 1, ...data, id: uid(), created_at: now() };
  e.activity = (e.activity || '').trim();
  e.pause_minutes = Number(e.pause_minutes) || 0;
  e.workers = entryWorkers(e);
  validateEntry(e);
  e.net_minutes = calcNetMinutes(e.start_time, e.end_time, e.pause_minutes);
  entryCache.set(e.project_id, sortEntries([...entryCache.get(e.project_id), e]));
  persist(backend.put('entries', e));
  syncProjectStats(e.project_id);
  return e;
}

export function updateEntry(id, data) {
  for (const [pid, arr] of entryCache) {
    const i = arr.findIndex((e) => e.id === id);
    if (i < 0) continue;
    const merged = { ...arr[i], ...data, id, project_id: pid };
    merged.activity = (merged.activity || '').trim();
    merged.pause_minutes = Number(merged.pause_minutes) || 0;
    merged.workers = entryWorkers(merged);
    validateEntry(merged);
    merged.net_minutes = calcNetMinutes(merged.start_time, merged.end_time, merged.pause_minutes);
    const next = [...arr];
    next[i] = merged;
    entryCache.set(pid, sortEntries(next));
    persist(backend.put('entries', merged));
    syncProjectStats(pid);
    return merged;
  }
  throw new Error('Eintrag nicht gefunden');
}

export function deleteEntry(id) {
  for (const [pid, arr] of entryCache) {
    if (!arr.some((e) => e.id === id)) continue;
    entryCache.set(pid, arr.filter((e) => e.id !== id));
    persist(backend.delete('entries', id));
    syncProjectStats(pid);
    return;
  }
}

// ============================================================
// invoices
// ============================================================

export const projectInvoices = (projectId) => state.invoices.filter((i) => i.project_id === projectId);
export const companyInvoices = (companyId) =>
  state.invoices.filter((i) => i.company_id === companyId).sort((a, b) => (b.year - a.year) || (b.month - a.month) || (b.seq - a.seq));

const totalsOf = (calc) => (calc ? { total_minutes: calc.totalMinutes, rate: calc.rate, net: calc.net, vat: calc.vat, gross: calc.gross } : {});

/** Returns the stored invoice for project+month or creates one with the next number of the company's sequence. */
export function getOrCreateInvoice(project, company, year, month, calc) {
  const existing = state.invoices.find((i) => i.project_id === project.id && i.year === year && i.month === month);
  if (existing) return existing;
  const seq = state.invoices.filter((i) => i.company_id === company.id && i.year === year).reduce((m, i) => Math.max(m, Number(i.seq) || 0), 0) + 1;
  const inv = {
    id: uid(), company_id: company.id, project_id: project.id, year, month, seq,
    number: `${company.invoice_prefix || 'RE-'}${year}-${String(seq).padStart(4, '0')}`,
    invoice_date: new Date().toISOString().slice(0, 10),
    created_at: now(),
    ...totalsOf(calc),
  };
  setState({ invoices: [...state.invoices, inv] });
  persist(backend.put('invoices', inv));
  return inv;
}

/** Store the amounts of the last generated PDF on the invoice (used by the overview). */
export function updateInvoiceTotals(id, calc) {
  const inv = state.invoices.find((i) => i.id === id);
  if (!inv) return null;
  const t = totalsOf(calc);
  if (Object.keys(t).every((k) => inv[k] === t[k])) return inv;
  const next = { ...inv, ...t, totals_at: now() };
  setState({ invoices: state.invoices.map((i) => (i.id === id ? next : i)) });
  persist(backend.put('invoices', next));
  return next;
}

export function deleteInvoice(id) {
  setState({ invoices: state.invoices.filter((i) => i.id !== id) });
  persist(backend.delete('invoices', id));
}

// ============================================================
// backup
// ============================================================

export async function exportBackup() {
  const data = await backend.exportAll();
  const json = JSON.stringify({ app: 'stundenzettel', version: 2, exported_at: now(), data });
  await setMeta('lastBackupAt', now());
  return json;
}

export async function importBackup(json, { merge = false } = {}) {
  let parsed;
  try { parsed = typeof json === 'string' ? JSON.parse(json) : json; } catch { throw new Error('Datei ist keine gültige Sicherung'); }
  if (parsed?.app && parsed.app !== 'stundenzettel') throw new Error('Datei stammt nicht aus dieser App');
  const data = normaliseDataset(parsed?.data || parsed);
  if (!data.companies.length && !data.projects.length) throw new Error('Keine gültige Sicherung (keine Firmen oder Projekte enthalten)');
  if (merge) {
    await backend.mergeAll(data);
    // stats must cover existing + imported entries
    const all = await backend.exportAll();
    await backend.bulkPut('projects', applyStats(all.projects.map(normaliseProject), statsFromEntries(all.entries)));
  } else {
    await backend.replaceAll(data);
  }
  await reloadCore();
  return { companies: data.companies.length, projects: data.projects.length, entries: data.entries.length, invoices: data.invoices.length };
}

export const totalEntryCount = () => state.projects.reduce((s, p) => s + (p.entry_count || 0), 0);
