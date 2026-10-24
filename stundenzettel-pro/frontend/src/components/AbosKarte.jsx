import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Btn } from './ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate } from '../lib/dates';

export const fmtGeld = (n) => `${Number(n || 0).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

/** Preisliste (netto je Monat) – Texte in einer Komponente, Zahlen kommen aus /api/firma/abos bzw. /api/preise. */
export function PreisListe({ preise, className = '' }) {
  const p = preise || { projekt_gu: 50.99, firma: 4.99, nutzer: 3.99 };
  return (
    <div className={`rounded-2xl bg-[#F5F5F7] px-4 py-4 text-[14px] space-y-2 ${className}`}>
      <div className="font-semibold">Preise (netto je Monat)</div>
      <div><strong>Firmenabo</strong> – {fmtGeld(p.firma)} je Firma plus {fmtGeld(p.nutzer)} je weiterem Nutzer (Inhaber enthalten): Mitarbeiter, Stempeluhr, Stundenzettel, Rechnungen und E-Rechnung, Lohnvorbereitung, eigene Projekte, Projektakte (ZIP), Schnittstellen.</div>
      <div><strong>GU-Projekt</strong> – {fmtGeld(p.projekt_gu)} je aktivem Bauprojekt eines Auftraggebers: beliebig viele Gewerke, Ausschreibungen, Projektleiter und beteiligte Firmen. Die Abrechnung beginnt mit der ersten Veröffentlichung oder Einladung; Entwürfe sind kostenlos. Kündigung zum Monatsende, danach bleiben Lesen, Export und Projektakte.</div>
      <div><strong>Kostenlose Projektteilnahme</strong> – eingeladene Betriebe sehen Ausschreibungen, geben Angebote ab, stellen Rückfragen und arbeiten in Projekten der Auftraggeber mit (Aufgaben, Fotos, Zeiten, Berichte, Nachträge, Abnahmen), ohne zu zahlen.</div>
      <div className="text-[#6E6E73]">14 Tage Test mit allem. Abrechnung per Rechnung des Anbieters; ein Zahlungsdienst (Karte/Lastschrift) folgt. Lesen und Exportieren geht immer weiter. Fair Use: 5 GB Speicher je Firma (erweiterbar), 25 MB je Datei.</div>
    </div>
  );
}

const STATUS_TEXT = (abo) => {
  if (!abo) return '';
  if (abo.status === 'aktiv') return `aktiv seit ${fmtDate(new Date(abo.aktiviert_am))}`;
  if (abo.status === 'gekuendigt') return `gekündigt – läuft bis ${abo.endet_am ? fmtDate(new Date(abo.endet_am)) : 'Monatsende'}`;
  return `beendet${abo.beendet_am ? ` ${fmtDate(new Date(abo.beendet_am))}` : ''}`;
};

/** Eure Abos: Firmenabo, GU-Projekte mit Kündigen/Aktivieren (Inhaber), Monatssumme. */
export default function AbosKarte({ className = '', onLoaded }) {
  const { isInhaber } = useAuth();
  const [abos, setAbos] = useState(null);
  const laden = useCallback(() => api.get('/api/firma/abos').then((a) => { setAbos(a); onLoaded?.(a); }).catch(() => setAbos(null)), [onLoaded]);
  useEffect(() => { laden(); }, [laden]);
  const guAbo = async (p, aktiv) => {
    const abo = p.gu_abo || {};
    const frage = aktiv
      ? (abo.status === 'gekuendigt' ? `Kündigung für „${p.name}“ zurücknehmen? Das GU-Abo läuft dann weiter.` : `„${p.name}“ als GU-Projekt aktivieren (${fmtGeld(abos?.preise?.projekt_gu)} netto je Monat)?`)
      : `GU-Abo für „${p.name}“ zum Monatsende kündigen? Bis dahin bleibt alles nutzbar; Veröffentlichen oder Einladen aktiviert es wieder.`;
    if (!window.confirm(frage)) return;
    try { await api.post(`/api/projekte/${p.id}/gu-abo`, { aktiv }); toast.success(aktiv ? 'GU-Projekt aktiv' : 'Zum Monatsende gekündigt'); laden(); } catch (err) { toast.error(err.message); }
  };
  if (!abos) return null;
  return (
    <div className={`rounded-2xl bg-[#F5F5F7] px-4 py-4 text-[14px] space-y-2 ${className}`}>
      <div className="font-semibold">Eure Abos</div>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span>Firmenabo: <strong>{abos.firmenabo ? `${fmtGeld(abos.kosten_firma_monat)} (${abos.nutzer_aktiv} Nutzer)` : 'kostenlose Projektteilnahme'}</strong>{abos.plan.status === 'test' ? ' – in der Testphase noch frei' : ''}</span>
        <span>GU-Projekte aktiv: <strong>{abos.gu_projekte_aktiv} × {fmtGeld(abos.preise.projekt_gu)}</strong></span>
        <span>Summe: <strong>{fmtGeld(abos.kosten_monat)}</strong> je Monat</span>
        {abos.art !== 'betrieb' && <span>GU-Freischaltung: <strong>{abos.gu_freigeschaltet ? 'ja' : 'nein'}</strong>{abos.plan.status === 'test' ? ' (in der Testphase frei)' : abos.gu_freigeschaltet ? '' : ' – nach der Testphase durch den Anbieter'}</span>}
      </div>
      {abos.projekte.length > 0 && (
        <ul className="divide-y divide-black/[0.06]">
          {abos.projekte.map((p) => (
            <li key={p.id} className="py-1.5 flex items-center gap-2">
              <span className="flex-1 min-w-0 truncate">{p.name}</span>
              <span className="text-[12px] text-[#6E6E73]">{STATUS_TEXT(p.gu_abo)}</span>
              {isInhaber && (p.gu_abo?.status === 'aktiv' ? <Btn size="sm" variant="ghost" onClick={() => guAbo(p, false)}>Kündigen</Btn> : <Btn size="sm" variant="ghost" onClick={() => guAbo(p, true)}>{p.gu_abo?.status === 'gekuendigt' ? 'Weiterführen' : 'Aktivieren'}</Btn>)}
            </li>
          ))}
        </ul>
      )}
      <div className="text-[12px] text-[#86868B]">{abos.zahlung} Abrechnungsperiode: {abos.periode || 'Kalendermonat'}.</div>
    </div>
  );
}
