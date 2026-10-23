// Date & number helpers (German formats, ISO weeks).
export const MIN_YEAR = 2025;
/** Always at least ten years ahead of today (re-evaluated on every app start). */
export const MAX_YEAR = Math.max(2035, new Date().getFullYear() + 10);
export const MIN_KEY = `${MIN_YEAR}-01-01`;
export const MAX_KEY = `${MAX_YEAR}-12-31`;

export const MONTHS_DE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
export const WEEKDAYS_DE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
export const WEEKDAYS_LONG_DE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

const pad = (n) => String(n).padStart(2, '0');

export const toKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const fromKey = (key) => { const [y, m, d] = key.split('-').map(Number); return new Date(y, m - 1, d); };
export const addDays = (d, n) => { const r = new Date(d); r.setDate(r.getDate() + n); return r; };
export const mondayOf = (d) => { const r = new Date(d.getFullYear(), d.getMonth(), d.getDate()); r.setDate(r.getDate() - ((r.getDay() + 6) % 7)); return r; };
export const monthLastDay = (year, month0) => new Date(year, month0 + 1, 0);

export const isoWeek = (d) => {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return { week: Math.ceil(((t - yearStart) / 86400000 + 1) / 7), year: t.getUTCFullYear() };
};

export const fmtDate = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
export const fmtDateShort = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.`;
export const fmtHours = (minutes) => `${Math.floor(minutes / 60)}:${pad(minutes % 60)} h`;
export const fmtDecimal = (value, digits = 2) => Number(value || 0).toLocaleString('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const fmtDecimalHours = (minutes) => fmtDecimal(minutes / 60);
export const fmtEur = (value) => `${fmtDecimal(value)} €`;

export const calcNetMinutes = (start, end, pause = 0) => {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(':').map(Number);
  const [eh, em] = end.split(':').map(Number);
  let s = sh * 60 + sm;
  let e = eh * 60 + em;
  if (e < s) e += 24 * 60;
  return Math.max(0, e - s - (Number(pause) || 0));
};

/** Mondays of all ISO weeks overlapping a month (month 0-based). */
export const monthWeeks = (year, month) => {
  const last = monthLastDay(year, month);
  const result = [];
  let cur = mondayOf(new Date(year, month, 1));
  while (cur <= last) { result.push(cur); cur = addDays(cur, 7); }
  return result;
};

export const clampMonth = (year, month) => {
  if (year < MIN_YEAR) return { year: MIN_YEAR, month: 0 };
  if (year > MAX_YEAR) return { year: MAX_YEAR, month: 11 };
  return { year, month };
};

export const todayKey = () => toKey(new Date());

/** Number of workers on an entry (1 if not set). */
export const entryWorkers = (e) => Math.max(1, Math.min(99, Math.round(Number(e?.workers) || 1)));
/** Minutes an entry counts for totals and billing: net minutes x workers (Mitarbeiterstunden). */
export const entryMinutes = (e) => (Number(e?.net_minutes) || 0) * entryWorkers(e);

/** Days between two ISO timestamps / dates (floored). */
export const daysSince = (iso) => {
  if (!iso) return Infinity;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return Infinity;
  return Math.floor((Date.now() - t) / 86400000);
};
