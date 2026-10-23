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

/** CSV-Text (Nr;Leistung;Menge;Einheit[;Beschreibung]) in Positionen umwandeln – für die Eingabe im Dialog. */
export function csvZuPositionen(text) {
  const zeilen = (text || '').replace(/^﻿/, '').split(/\r?\n/).filter((z) => z.trim());
  if (!zeilen.length) return [];
  const trenner = zeilen[0].includes(';') ? ';' : zeilen[0].includes('\t') ? '\t' : ',';
  const aus = [];
  for (const z of zeilen) {
    const t = z.split(trenner).map((x) => x.trim());
    if (['nr', 'nr.', 'pos', 'pos.', 'position', 'oz'].includes((t[0] || '').toLowerCase())) continue;
    if (!t[1]) throw new Error(`Zeile „${z.slice(0, 40)}“: Leistung fehlt`);
    const mengeText = (t[2] || '0').includes(',') ? (t[2] || '0').replace(/\./g, '').replace(',', '.') : (t[2] || '0');
    const menge = parseFloat(mengeText);
    if (Number.isNaN(menge)) throw new Error(`Position ${t[0]}: Menge „${t[2]}“ ist keine Zahl`);
    aus.push({ nr: t[0], leistung: t[1], menge, einheit: t[3] || 'Stück', beschreibung: t[4] || '' });
  }
  return aus;
}
