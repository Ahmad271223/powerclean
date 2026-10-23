import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...inputs) => twMerge(clsx(inputs));

export const uid = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${Math.random().toString(36).slice(2, 6)}`;

export const PROJECT_COLORS = ['#C41E3A', '#0F766E', '#1D4ED8', '#7C3AED', '#D97706', '#DB2777', '#059669', '#1D1D1F'];

export const initials = (name) =>
  (name || '').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('') || '?';

export const companyAddress = (c) =>
  [c?.street, [c?.zip_code, c?.city].filter(Boolean).join(' ')].filter(Boolean).join(', ');

/**
 * Reads an image file (PNG, JPG or SVG), scales it to max 800x400 px and returns
 * { dataUrl (PNG), w, h }. The size is stored with the company so PDFs can be built synchronously.
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
        let w = img.naturalWidth || 400;
        let h = img.naturalHeight || 200;
        const scale = Math.min(1, 800 / w, 400 / h);
        w = Math.max(1, Math.round(w * scale));
        h = Math.max(1, Math.round(h * scale));
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);
        resolve({ dataUrl: canvas.toDataURL('image/png'), w, h });
      } catch {
        URL.revokeObjectURL(url);
        reject(new Error('Logo konnte nicht verarbeitet werden'));
      }
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Bild konnte nicht gelesen werden')); };
    img.src = url;
  });
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export function openBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const win = window.open(url, '_blank');
  if (!win) downloadBlob(blob, filename);
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

const canShareFiles = (file) => {
  try { return !!navigator.share && (!navigator.canShare || navigator.canShare({ files: [file] })); } catch { return false; }
};

/**
 * Share a file via the system share sheet when possible, otherwise download it.
 * Must be called synchronously inside a user gesture (tap) so iOS allows the share sheet.
 * Returns 'shared' | 'downloaded' | 'opened' | 'cancelled'.
 */
export function shareOrDownload(blob, filename, title) {
  const file = new File([blob], filename, { type: blob.type || 'application/pdf' });
  if (canShareFiles(file)) {
    return navigator.share({ files: [file], title: title || filename })
      .then(() => 'shared')
      .catch((err) => {
        if (err?.name === 'AbortError') return 'cancelled';
        // NotAllowedError (gesture expired) or anything else: fall back to download
        downloadBlob(blob, filename);
        return 'downloaded';
      });
  }
  downloadBlob(blob, filename);
  return Promise.resolve('downloaded');
}

/** Hand a generated PDF to the user: share sheet on phones, new tab on desktop, or download. */
export function deliverPdf({ blob, filename }, mode = 'share') {
  if (mode === 'download') { downloadBlob(blob, filename); return Promise.resolve('downloaded'); }
  if (navigator.share) return shareOrDownload(blob, filename, filename);
  openBlob(blob, filename);
  return Promise.resolve('opened');
}

export const safeFilename = (text) => (text || '').trim().replace(/[^\p{L}\p{N}_-]+/gu, '_').slice(0, 40) || 'projekt';
