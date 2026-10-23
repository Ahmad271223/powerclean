/**
 * Zugriff auf die Server-API. Token liegt im localStorage; 401 meldet den Nutzer ab,
 * 402 (Lizenz) und andere Fehler kommen als ApiError mit deutschem Text an.
 */
import { downloadBlob } from './utils';

const BASE = import.meta.env.VITE_API_URL || '';
const TOKEN_KEY = 'szpro-token';

let token = null;
try { token = localStorage.getItem(TOKEN_KEY); } catch { /* privater Modus */ }

const abmeldeListener = new Set();
export const onUnauthorized = (fn) => { abmeldeListener.add(fn); return () => abmeldeListener.delete(fn); };

export function setToken(t) {
  token = t || null;
  try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}
export const hasToken = () => !!token;

/** Antwort des Server-Auffangs: die Oberfläche ruft eine Route, die der Server (noch) nicht kennt – meist nach einem Update nur der App. */
export const SERVER_VERALTET = 'Diese Funktion kennt der Server noch nicht. Bitte den Server auf den neuen Stand bringen (oder die Seite neu laden).';

export class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data; }
}

async function request(method, path, body, { form = false } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = body;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: payload });
  } catch {
    throw new ApiError('Keine Verbindung zum Server. Bitte Internet prüfen.', 0, null);
  }
  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await res.json().catch(() => null) : null;
  if (res.status === 401 && token) { abmeldeListener.forEach((fn) => fn()); }
  if (!res.ok) {
    let text = (data && (typeof data.detail === 'string' ? data.detail : data.detail?.[0]?.msg)) || `Fehler ${res.status}`;
    if (res.status === 404 && text === 'Nicht gefunden.') text = SERVER_VERALTET;
    throw new ApiError(text, res.status, data);
  }
  return data;
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p, b) => request('DELETE', p, b),
  upload: (p, formData) => request('POST', p, formData, { form: true }),
};

/** Datei mit Anmeldung laden (CSV/JSON/Dokument) und herunterladen. */
export async function download(path, filename) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(BASE + path, { headers });
  if (!res.ok) {
    let text = `Fehler ${res.status}`;
    try { text = (await res.json()).detail || text; } catch { /* ignore */ }
    if (res.status === 404 && text === 'Nicht gefunden.') text = SERVER_VERALTET;
    throw new ApiError(text, res.status, null);
  }
  const blob = await res.blob();
  const cd = res.headers.get('content-disposition') || '';
  const m = /filename="?([^";]+)"?/.exec(cd);
  downloadBlob(blob, filename || (m ? m[1] : 'datei'));
}

/** Datei mit Anmeldung als Blob laden (Fotos, Vorschauen). */
export async function fetchBlob(path) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(BASE + path, { headers });
  if (!res.ok) throw new ApiError(`Fehler ${res.status}`, res.status, null);
  return res.blob();
}

/** Datei mit Anmeldung öffnen (z. B. Foto in neuem Tab). */
export async function openFile(path) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(BASE + path, { headers });
  if (!res.ok) throw new ApiError('Datei konnte nicht geladen werden', res.status, null);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const win = window.open(url, '_blank');
  if (!win) downloadBlob(blob, 'datei');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export const fehlerText = (err, fallback = 'Etwas ist schiefgelaufen') => err?.message || fallback;
