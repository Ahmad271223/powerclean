/**
 * Fotos der Projektakte: Vorschau-Adressen, Tag/Zeit eines Fotos und das Laden der Bilddaten für PDFs
 * (verkleinertes JPEG vom Server, Maße fürs Seitenverhältnis).
 */
import { fetchBlob } from './api';

export const bildPfad = (id, max = 400) => `/api/dokumente/${id}/bild?max=${max}`;
export const fotoTag = (f) => f.tag || f.date || (f.created_at || '').slice(0, 10);
export const fotoZeit = (f) => (f.created_at ? new Date(f.created_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '');
export const istFoto = (d) => (d.mime || '').startsWith('image/');

/** Fotos nach Tag gruppieren: { '2026-10-07': [...] } */
export function fotosNachTag(fotos) {
  const m = {};
  for (const f of fotos || []) (m[fotoTag(f)] ||= []).push(f);
  return m;
}

/** Fotos im Zeitraum (Tage als JJJJ-MM-TT), sortiert nach Tag und Aufnahmezeit. */
export function fotosImZeitraum(fotos, von, bis) {
  return (fotos || []).filter((f) => { const t = fotoTag(f); return t >= von && t <= bis; }).sort((a, b) => (fotoTag(a) + (a.created_at || '')).localeCompare(fotoTag(b) + (b.created_at || '')));
}

const blobZuDataUrl = (blob) => new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.onerror = reject; r.readAsDataURL(blob); });
const masse = (dataUrl) => new Promise((resolve) => { const img = new Image(); img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight }); img.onerror = () => resolve(null); img.src = dataUrl; });

/** Bilddaten für die PDF laden (JPEG, max. 1400 px). Nicht lesbare Bilder (z. B. HEIC) werden übersprungen. */
export async function ladeFotoDaten(fotos, max = 1400) {
  const aus = [];
  for (const f of fotos) {
    try {
      const blob = await fetchBlob(bildPfad(f.id, max));
      const dataUrl = await blobZuDataUrl(blob);
      const m = await masse(dataUrl);
      if (m) aus.push({ ...f, dataUrl, w: m.w, h: m.h, tag: fotoTag(f), zeit: fotoZeit(f) });
    } catch { /* Foto nicht lesbar: auslassen, PDF trotzdem erzeugen */ }
  }
  return aus;
}
