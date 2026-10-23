// Shared helpers for the Stundenzettel (timesheet) app: API client, auth token, date utils.
import axios from 'axios';

export const API = `${import.meta.env.VITE_BACKEND_URL || 'https://powerclean-backend.onrender.com'}/api`;

export const MIN_YEAR = 2025;
export const MAX_YEAR = Math.max(2035, new Date().getFullYear() + 10);

// ---------- auth (shares the admin token with the admin dashboard) ----------
export const getToken = () => localStorage.getItem('adminToken') || '';
export const setToken = (token) => localStorage.setItem('adminToken', token);
export const clearToken = () => localStorage.removeItem('adminToken');

export const api = axios.create({ baseURL: API });
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function login(username, password) {
  const res = await axios.post(`${API}/admin/login`, { username, password });
  setToken(res.data.token);
  return res.data;
}

/** Fetch a PDF with the auth header and open it in a new tab (or download it). */
export async function fetchPdf(path, params, { download = false, filename = 'dokument.pdf' } = {}) {
  const res = await api.get(path, { params, responseType: 'blob' });
  const disposition = res.headers['content-disposition'] || '';
  const match = disposition.match(/filename="?([^";]+)"?/);
  const name = match ? match[1] : filename;
  const blob = new Blob([res.data], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  if (download) {
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } else {
    const win = window.open(url, '_blank');
    if (!win) {
      // popup blocked -> fall back to download
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      a.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
}

// ---------- dates ----------
export const MONTHS_DE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];
export const WEEKDAYS_DE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
export const WEEKDAYS_LONG_DE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

const pad = (n) => String(n).padStart(2, '0');

/** Date -> 'YYYY-MM-DD' (local time, no timezone shift). */
export const toKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** 'YYYY-MM-DD' -> Date (local). */
export const fromKey = (key) => {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d);
};

export const addDays = (d, n) => {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
};

/** Monday of the ISO week containing d. */
export const mondayOf = (d) => {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = (r.getDay() + 6) % 7; // Mo=0 .. So=6
  r.setDate(r.getDate() - day);
  return r;
};

/** ISO week number + ISO year. */
export const isoWeek = (d) => {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((t - yearStart) / 86400000 + 1) / 7);
  return { week, year: t.getUTCFullYear() };
};

export const fmtDate = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
export const fmtDateShort = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.`;

export const fmtHours = (minutes) => `${Math.floor(minutes / 60)}:${pad(minutes % 60)} h`;
export const fmtDecimalHours = (minutes) => (minutes / 60).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtEur = (value) => value.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });

/** Net minutes for a start/end 'HH:MM' and a pause. End before start = over midnight. */
export const calcNetMinutes = (start, end, pause = 0) => {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(':').map(Number);
  const [eh, em] = end.split(':').map(Number);
  let s = sh * 60 + sm;
  let e = eh * 60 + em;
  if (e < s) e += 24 * 60;
  return Math.max(0, e - s - (Number(pause) || 0));
};

/** All Mondays of ISO weeks overlapping a month (year, month 0-based). */
export const monthWeeks = (year, month) => {
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const result = [];
  let cur = mondayOf(first);
  while (cur <= last) {
    result.push(cur);
    cur = addDays(cur, 7);
  }
  return result;
};

export const clampMonth = (year, month) => {
  if (year < MIN_YEAR) return { year: MIN_YEAR, month: 0 };
  if (year > MAX_YEAR) return { year: MAX_YEAR, month: 11 };
  return { year, month };
};

export const PROJECT_COLORS = ['#C41E3A', '#0F766E', '#1D4ED8', '#7C3AED', '#D97706', '#DB2777', '#059669', '#0A0A0A'];

export const initials = (name) =>
  (name || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('') || '?';

export const LAST_COMPANY_KEY = 'tsLastCompany';

export const companyAddress = (c) =>
  [c?.street, [c?.zip_code, c?.city].filter(Boolean).join(' ')].filter(Boolean).join(', ');

/**
 * Reads an image file (PNG, JPG or SVG), scales it down to max 800x400 px and returns a PNG data URL.
 * SVGs are rasterised in the browser, because the PDF generator only understands PNG/JPG.
 */
export function processLogoFile(file) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error('Keine Datei'));
    const okType = /^image\/(png|jpeg|svg\+xml)$/.test(file.type) || /\.(png|jpe?g|svg)$/i.test(file.name);
    if (!okType) return reject(new Error('Bitte PNG, JPG oder SVG auswählen'));
    if (file.size > 8 * 1024 * 1024) return reject(new Error('Datei ist zu groß (max. 8 MB)'));
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        const MAX_W = 800;
        const MAX_H = 400;
        let w = img.naturalWidth || 400;
        let h = img.naturalHeight || 200;
        const scale = Math.min(1, MAX_W / w, MAX_H / h);
        w = Math.max(1, Math.round(w * scale));
        h = Math.max(1, Math.round(h * scale));
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);
        resolve(canvas.toDataURL('image/png'));
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(new Error('Logo konnte nicht verarbeitet werden'));
      }
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Bild konnte nicht gelesen werden')); };
    img.src = url;
  });
}
