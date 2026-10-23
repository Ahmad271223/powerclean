import { fmtDate, fromKey } from './dates';

/** Gemeinsame Darstellung für Ausschreibungen, Angebote und Vergaben. */
export const STATUS_CLS = {
  entwurf: 'bg-black/[0.06] text-[#6E6E73]', veroeffentlicht: 'bg-[#E8F8EC] text-[#1B7F3B]', in_vergabe: 'bg-[#EEE8FD] text-[#6D28D9]',
  vergeben: 'bg-[#1B7F3B] text-white', aufgehoben: 'bg-black/[0.06] text-[#6E6E73] line-through',
};
export const ANGEBOT_CLS = {
  entwurf: 'bg-black/[0.06] text-[#6E6E73]', eingereicht: 'bg-[#E8F0FE] text-[#1D4ED8]', in_pruefung: 'bg-[#FFF4E5] text-[#B25E00]', rueckfrage: 'bg-[#FDE8E8] text-[#C41E3A]',
  ueberarbeitet: 'bg-[#E8F0FE] text-[#1D4ED8]', angenommen: 'bg-[#1B7F3B] text-white', abgelehnt: 'bg-black/[0.06] text-[#6E6E73]', zurueckgezogen: 'bg-black/[0.06] text-[#6E6E73] line-through',
};
export const VERGABE_CLS = {
  vorgeschlagen: 'bg-[#FFF4E5] text-[#B25E00]', freigegeben: 'bg-[#E8F0FE] text-[#1D4ED8]', mitgeteilt: 'bg-[#EEE8FD] text-[#6D28D9]', angenommen: 'bg-[#1B7F3B] text-white',
  abgelehnt_firma: 'bg-[#FDE8E8] text-[#C41E3A]', zurueckgezogen: 'bg-black/[0.06] text-[#6E6E73] line-through',
};
export const VERGABE_NAMEN = { vorgeschlagen: 'Zur Freigabe vorgeschlagen', freigegeben: 'Intern freigegeben', mitgeteilt: 'Firma benachrichtigt – Annahme offen', angenommen: 'Verbindlich angenommen', abgelehnt_firma: 'Von der Firma abgelehnt', zurueckgezogen: 'Zurückgezogen' };
export const ANGEBOT_NAMEN = { entwurf: 'Entwurf', eingereicht: 'Eingereicht', in_pruefung: 'In Prüfung', rueckfrage: 'Rückfrage / Nachforderung', ueberarbeitet: 'Überarbeitet eingereicht', angenommen: 'Angenommen', abgelehnt: 'Abgelehnt', zurueckgezogen: 'Zurückgezogen' };
export const PREISARTEN = { pauschal: 'Pauschalpreis', einheitspreise: 'Einheitspreise (LV)', stunden: 'Nach Stunden' };
export const KRITERIEN = { preis: 'Preis', leistung: 'Leistungsumfang', termin: 'Termin', verfuegbarkeit: 'Verfügbarkeit', qualifikation: 'Qualifikation', vollstaendigkeit: 'Vollständigkeit', mindestanforderungen: 'Mindestanforderungen' };
export const ANFORDERUNGEN = [['qualifikationen', 'Benötigte Qualifikationen'], ['zertifikate', 'Zertifikate und Nachweise'], ['versicherungen', 'Versicherungsnachweise'], ['kapazitaet', 'Benötigte Mitarbeiterkapazität'],
  ['ausruestung', 'Maschinen und Ausrüstung'], ['material', 'Materialanforderungen'], ['technik', 'Technische Spezifikationen'], ['bedingungen', 'Ausführungsbedingungen'], ['sicherheit', 'Sicherheitsanforderungen'], ['sonstiges', 'Zusätzliche Voraussetzungen']];

export const fmtGeld = (n) => (n === null || n === undefined || Number.isNaN(Number(n)) ? '–' : `${Number(n).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`);
export const fmtTag = (key) => (key ? fmtDate(fromKey(key)) : '–');
export const fmtZeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
export const fristText = (a) => {
  if (!a?.angebotsfrist) return 'keine Frist';
  if (a.frist_tage === null || a.frist_tage === undefined) return fmtTag(a.angebotsfrist);
  if (a.frist_tage < 0) return `${fmtTag(a.angebotsfrist)} (abgelaufen)`;
  if (a.frist_tage === 0) return `${fmtTag(a.angebotsfrist)} (heute)`;
  return `${fmtTag(a.angebotsfrist)} (noch ${a.frist_tage} Tage)`;
};

/** Excel-/CSV-Zeilen importieren (Semikolon, Tab oder Komma; Anführungszeichen und Dezimalkomma). */
export function csvZuPositionen(text) {
  const source = String(text || '').replace(/^\uFEFF/, '').trim();
  if (!source) return [];
  const first = source.split(/\r?\n/, 1)[0];
  const counts = { ';': 0, '\t': 0, ',': 0 };
  let quoted = false;
  for (let i = 0; i < first.length; i += 1) {
    if (first[i] === '"') {
      if (quoted && first[i + 1] === '"') { i += 1; continue; }
      quoted = !quoted;
    } else if (!quoted && counts[first[i]] !== undefined) counts[first[i]] += 1;
  }
  const delim = counts['\t'] ? '\t' : counts[';'] ? ';' : ',';
  const rows = [];
  let row = [], cell = '', inside = false;
  for (let i = 0; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '"') {
      if (inside && source[i + 1] === '"') { cell += '"'; i += 1; }
      else inside = !inside;
    } else if (ch === delim && !inside) {
      row.push(cell.trim()); cell = '';
    } else if ((ch === '\n' || ch === '\r') && !inside) {
      if (ch === '\r' && source[i + 1] === '\n') i += 1;
      row.push(cell.trim()); cell = '';
      if (row.some(Boolean)) rows.push(row);
      row = [];
    } else {
      cell += ch;
    }
  }
  if (inside) throw new Error('CSV: Ein Anführungszeichen wurde nicht geschlossen.');
  row.push(cell.trim());
  if (row.some(Boolean)) rows.push(row);

  const normalized = (v) => String(v || '').trim().toLowerCase().replace(/[.\s_-]/g, '');
  const headers = new Set(['nr', 'pos', 'position', 'positionsnummer', 'oz', 'ordnungszahl']);
  const parseMenge = (value) => {
    const raw = String(value ?? '').trim().replace(/\s/g, '');
    if (!raw) return NaN;
    const standard = raw.includes(',') ? raw.replace(/\./g, '').replace(',', '.') : raw;
    return Number(standard);
  };
  const out = [];
  const numbers = new Set();
  rows.forEach((cols, rowIndex) => {
    if (headers.has(normalized(cols[0]))) return;
    if (cols.length < 3 || !String(cols[0] || '').trim() || !String(cols[1] || '').trim()) {
      throw new Error('CSV-Zeile ' + (rowIndex + 1) + ': Bitte Nr;Leistung;Menge;Einheit angeben.');
    }
    const nr = String(cols[0]).trim();
    const menge = parseMenge(cols[2]);
    if (!Number.isFinite(menge) || menge < 0) throw new Error('CSV-Zeile ' + (rowIndex + 1) + ': Ungültige Menge "' + cols[2] + '".');
    if (numbers.has(nr)) throw new Error('CSV-Zeile ' + (rowIndex + 1) + ': Position ' + nr + ' kommt doppelt vor.');
    numbers.add(nr);
    out.push({ nr, leistung: String(cols[1]).trim(), menge, einheit: cols[3] || 'Stück', beschreibung: cols.slice(4).join(delim) || '' });
  });
  return out;
}
