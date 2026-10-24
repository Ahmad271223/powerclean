/** Kundenangebote: Status, Positionsarten und die Summenrechnung (Spiegel von backend/angebote.py für die Live-Vorschau im Editor;
 *  verbindlich rechnet immer der Server beim Speichern). */
import { fmtGeld } from './ausschreibung';

export { fmtGeld };

export const STATUS_NAMEN = {
  anfrage: 'Kundenanfrage', entwurf: 'Entwurf', gesendet: 'Gesendet – Antwort offen', angenommen: 'Angenommen', abgelehnt: 'Abgelehnt',
  zurueckgezogen: 'Zurückgezogen', abgelaufen: 'Abgelaufen', ersetzt: 'Durch neue Version ersetzt',
};
export const STATUS_CLS = {
  anfrage: 'bg-[#E8F0FE] text-[#1D4ED8]', entwurf: 'bg-black/[0.06] text-[#6E6E73]', gesendet: 'bg-[#FFF4E5] text-[#B25E00]', angenommen: 'bg-[#E8F8EC] text-[#1B7F3B]',
  abgelehnt: 'bg-[#FDE8E8] text-[#C41E3A]', zurueckgezogen: 'bg-black/[0.06] text-[#6E6E73]', abgelaufen: 'bg-[#FDE8E8] text-[#C41E3A]', ersetzt: 'bg-black/[0.06] text-[#6E6E73]',
};
export const POSITIONSARTEN = { titel: 'Titel / Gruppe', leistung: 'Leistung', stunden: 'Stundenposition', material: 'Material', pauschal: 'Pauschale', text: 'Textzeile' };
export const EINHEITEN = ['Stk.', 'Std.', 'm', 'm²', 'm³', 'lfm', 'kg', 'l', 'Psch.', 'Tag', 'Monat', 'Fahrt'];
export const ANNAHMEARTEN = { schriftlich: 'schriftlich (E-Mail oder Brief)', unterschrift: 'unterschriebenes Angebot', telefonisch: 'telefonisch', persoenlich: 'persönlich', online: 'online über den Antwortlink' };
export const KALKULATION_FELDER = [
  ['stunden', 'Stunden', 'Std.'], ['stundensatz', 'Stundensatz intern', '€/Std.'], ['material_ek', 'Material (Einkauf)', '€'], ['fremd', 'Fremdleistungen', '€'],
  ['geraete', 'Geräte', '€'], ['transport', 'Transport / Anfahrt', '€'], ['sonstige', 'Sonstige Kosten', '€'],
];
export const KALKULATION_ZUSCHLAEGE = [['gemeinkosten_prozent', 'Gemeinkosten'], ['risiko_prozent', 'Risiko'], ['gewinn_prozent', 'Gewinn']];

/** Kaufmännisch runden (halb aufrunden), stabil gegen Gleitkomma-Reste. */
export const rund = (x) => Math.round(Number(((Number(x) || 0) * 100).toFixed(6))) / 100;
export const fmtProzent = (x) => (x === null || x === undefined || Number.isNaN(Number(x)) ? '–' : `${Number(x).toLocaleString('de-DE', { maximumFractionDigits: 2 })} %`);
export const fmtMenge = (x) => Number(x || 0).toLocaleString('de-DE', { maximumFractionDigits: 2 });

let zaehler = 0;
export const leerePosition = (art = 'leistung') => ({
  id: `neu-${Date.now().toString(36)}-${(zaehler += 1)}`, art, text: '', beschreibung: '', menge: art === 'titel' || art === 'text' ? 0 : 1,
  einheit: art === 'stunden' ? 'Std.' : art === 'pauschal' ? 'Psch.' : 'Stk.', einzelpreis: 0, rabatt_prozent: 0, alternativ: false, eventual: false, leistung_id: null,
});
export const istNeu = (p) => !p.id || String(p.id).startsWith('neu-');

/** Laufende Nummern wie auf dem Server: Titel und freie Positionen oben, unter einem Titel 2.1, 2.2 …; Textzeilen ohne Nummer. */
export function nummerieren(positionen) {
  let oben = 0; let unter = 0; let titel = null;
  return (positionen || []).map((p) => {
    const art = p.art || 'leistung';
    if (art === 'titel') { oben += 1; titel = oben; unter = 0; return { ...p, nr: String(oben) }; }
    if (art === 'text') return { ...p, nr: '' };
    if (titel === null) { oben += 1; return { ...p, nr: String(oben) }; }
    unter += 1;
    return { ...p, nr: `${titel}.${unter}` };
  });
}

export function positionBetrag(p) {
  if ((p.art || 'leistung') === 'titel' || p.art === 'text') return 0;
  const rabatt = Math.max(0, Math.min(100, Number(p.rabatt_prozent) || 0));
  return rund((Number(p.menge) || 0) * (Number(p.einzelpreis) || 0) * (1 - rabatt / 100));
}

/** Netto aus den Positionen (ohne Alternativ/Eventual) → Zuschläge → Rabatt → USt → Brutto. */
export function summen(positionen, zuschlaege, rabattProzent, steuer) {
  const pos = nummerieren(positionen);
  let nettoPos = 0; let alternativ = 0; let eventual = 0;
  const titel = [];
  const mitBetrag = pos.map((p) => {
    const betrag = positionBetrag(p);
    if (p.art === 'titel') { titel.push({ nr: p.nr, text: p.text || '', netto: 0 }); return { ...p, gesamt: 0 }; }
    if (p.art === 'text') return { ...p, gesamt: 0 };
    if (p.alternativ) { alternativ += betrag; return { ...p, gesamt: betrag, zaehlt: false }; }
    if (p.eventual) { eventual += betrag; return { ...p, gesamt: betrag, zaehlt: false }; }
    nettoPos += betrag;
    if (titel.length && (p.nr || '').includes('.')) titel[titel.length - 1].netto = rund(titel[titel.length - 1].netto + betrag);
    return { ...p, gesamt: betrag, zaehlt: true };
  });
  nettoPos = rund(nettoPos);
  let zuSumme = 0;
  const zu = (zuschlaege || []).map((z) => { const betrag = rund(nettoPos * (Number(z.prozent) || 0) / 100); zuSumme += betrag; return { text: z.text || 'Zuschlag', prozent: Number(z.prozent) || 0, betrag }; });
  const zwischen = rund(nettoPos + zuSumme);
  const rabatt = Math.max(0, Math.min(100, Number(rabattProzent) || 0));
  const rabattBetrag = rund(zwischen * rabatt / 100);
  const netto = rund(zwischen - rabattBetrag);
  const satz = Number(steuer?.satz) || 0;
  const ust = rund(netto * satz / 100);
  return { positionen: mitBetrag, titel, positionen_netto: nettoPos, zuschlaege: zu, zuschlaege_netto: rund(zuSumme), rabatt_prozent: rabatt, rabatt_betrag: rabattBetrag,
    netto, ust_satz: satz, ust, brutto: rund(netto + ust), alternativ_netto: rund(alternativ), eventual_netto: rund(eventual), steuer: steuer || { kategorie: 'S', satz, hinweis: '' } };
}

/** Positionen für PUT/POST: temporäre IDs weglassen, Zahlen als Zahlen, Kalkulation nicht mitschicken (eigener Endpunkt). */
export const positionenFuerServer = (positionen) => (positionen || []).map((p) => ({
  ...(istNeu(p) ? {} : { id: p.id }), art: p.art || 'leistung', text: p.text || '', beschreibung: p.beschreibung || '', menge: Number(p.menge) || 0, einheit: p.einheit || 'Stk.',
  einzelpreis: Number(p.einzelpreis) || 0, rabatt_prozent: Number(p.rabatt_prozent) || 0, alternativ: !!p.alternativ, eventual: !!p.eventual, leistung_id: p.leistung_id || null, artikel_id: p.artikel_id || null,
}));
