import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Calculator } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '../ui';
import { api } from '../../lib/api';
import { fmtGeld, fmtMenge, fmtProzent } from '../../lib/angebot';
import { fmtDate, fromKey } from '../../lib/dates';

function Kennzahl({ label, wert, hinweis, warn, gut }) {
  return (
    <div className={`rounded-2xl px-4 py-3 ${warn ? 'bg-[#FFF4E5]' : gut ? 'bg-[#E8F8EC]' : 'bg-[#F5F5F7]'}`}>
      <div className="text-[12px] text-[#6E6E73]">{label}</div>
      <div className="text-[18px] font-semibold leading-tight">{wert}</div>
      {hinweis && <div className="text-[11px] text-[#86868B] mt-0.5">{hinweis}</div>}
    </div>
  );
}

const g = (x) => (x === null || x === undefined ? '–' : fmtGeld(x));

/** Projekt → Nachkalkulation: Soll (Auftrag + Angebotskalkulation) gegen Ist (Stunden × Kostenmodell, Material, Eingangsrechnungen) je Kostenart.
 *  Fehlende Lohnsätze, ungeprüfte Stunden, Material oder Rechnungen werden benannt; ein „Ergebnis“ gibt es erst, wenn alles geprüft ist. */
export default function NachkalkulationTab({ projekt }) {
  const navigate = useNavigate();
  const [n, setN] = useState(null);
  const [fehler, setFehler] = useState('');
  useEffect(() => { api.get(`/api/projekte/${projekt.id}/nachkalkulation`).then((r) => setN(r.nachkalkulation)).catch((err) => { setFehler(err.message); toast.error(err.message); }); }, [projekt.id]);
  if (fehler) return <Card className="p-5 text-[14px] text-[#6E6E73]">{fehler}</Card>;
  if (!n) return <Card className="p-5 text-[14px] text-[#6E6E73]">Nachkalkulation wird berechnet …</Card>;
  const max = Math.max(1, ...n.kostenarten.flatMap((k) => [k.plan || 0, k.ist || 0]));
  const db = n.deckungsbeitrag;
  return (
    <div className="space-y-5">
      {n.hinweise.length > 0 && (
        <Card className="p-4 border border-[#F59E0B]/40">
          <div className="font-semibold text-[14px] flex items-center gap-2 mb-1"><AlertTriangle size={16} className="text-[#B25E00]" /> Noch unvollständig – diese Punkte verfälschen das Ergebnis</div>
          <ul className="text-[13px] space-y-0.5">{n.hinweise.map((h) => <li key={h}>• {h}</li>)}</ul>
        </Card>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kennzahl label="Vereinbarter Umsatz (netto)" wert={g(n.umsatz_vereinbart)} hinweis={n.nachtraege_freigegeben ? `inkl. ${fmtGeld(n.nachtraege_freigegeben)} freigegebene Nachträge` : n.auftragswert_netto ? 'Auftragswert' : 'kein Auftragswert hinterlegt'} />
        <Kennzahl label="Plan-Kosten (Selbstkosten)" wert={g(n.plan.gesamt)} hinweis={n.plan.quelle || 'keine Angebotskalkulation'} />
        <Kennzahl label="Ist-Kosten bisher" wert={fmtGeld(n.ist.gesamt)} hinweis={`direkt ${fmtGeld(n.ist.direkt)} + Gemeinkosten ${fmtGeld(n.ist.gemeinkosten_zuschlag + n.ist.gemeinkosten)}`} warn={n.abweichung !== null && n.abweichung > 0} />
        <Kennzahl label="Abweichung Ist − Plan" wert={n.abweichung === null ? '–' : `${n.abweichung > 0 ? '+' : ''}${fmtGeld(n.abweichung)}`} hinweis={n.plan.gesamt ? fmtProzent(n.abweichung / n.plan.gesamt * 100) : ''} warn={n.abweichung !== null && n.abweichung > 0} gut={n.abweichung !== null && n.abweichung <= 0} />
        <Kennzahl label="Erwarteter Deckungsbeitrag" wert={g(db.erwartet)} hinweis="Umsatz − geplante direkte Kosten" />
        <Kennzahl label="Aktueller Deckungsbeitrag" wert={g(db.aktuell)} hinweis="Umsatz − bisherige direkte Kosten" warn={db.aktuell !== null && db.aktuell < 0} />
        <Kennzahl label="Ergebnis nach allen Kosten" wert={n.vollstaendig ? g(db.ergebnis) : 'noch offen'} hinweis={n.vollstaendig ? 'alle Zeiten, Material und Rechnungen geprüft' : 'erst nach Prüfung aller Kosten'} gut={n.vollstaendig && db.ergebnis > 0} warn={n.vollstaendig && db.ergebnis < 0} />
        {n.abrechenbar_stunden_netto !== null && <Kennzahl label="Abrechenbar (Stunden × Kundensatz)" wert={fmtGeld(n.abrechenbar_stunden_netto)} hinweis="Stundenprojekt: Leistung getrennt von Kosten" />}
      </div>
      <Card className="p-5">
        <h2 className="text-[17px] mb-3 flex items-center gap-2"><Calculator size={17} /> Soll / Ist nach Kostenarten</h2>
        <div className="space-y-3">
          {n.kostenarten.map((k) => (
            <div key={k.art}>
              <div className="flex justify-between text-[13px] mb-1"><span>{k.name}</span><span className="text-[#6E6E73]">Plan {g(k.plan)} · Ist <span className={`font-semibold ${k.plan !== null && k.ist > k.plan ? 'text-[#B25E00]' : 'text-[#1D1D1F]'}`}>{fmtGeld(k.ist)}</span></span></div>
              <div className="h-2 rounded-full bg-black/[0.06] overflow-hidden"><div className="h-2 rounded-full bg-[#C7C7CC]" style={{ width: `${Math.min(100, (k.plan || 0) / max * 100)}%` }} /></div>
              <div className="h-2 rounded-full bg-black/[0.06] overflow-hidden mt-0.5"><div className={`h-2 rounded-full ${k.plan !== null && k.ist > k.plan ? 'bg-[#B25E00]' : 'bg-[#1B7F3B]'}`} style={{ width: `${Math.min(100, (k.ist || 0) / max * 100)}%` }} /></div>
            </div>
          ))}
        </div>
        <div className="text-[11px] text-[#86868B] mt-2">Grauer Balken = Plan, farbiger Balken = Ist. {n.kostenmodell.text} Lohnnebenkosten {fmtProzent(n.kostenmodell.lohnnebenkosten_prozent)}.</div>
      </Card>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <h2 className="text-[17px] mb-2">Stunden</h2>
          <table className="w-full text-[14px]"><tbody>
            {[['Geplant (Angebotskalkulation)', n.stunden.plan_kalkulation], ['Geplant (Plantafel-Einsätze)', n.stunden.plan_einsaetze], ['Gebucht (Stempelung / Einträge)', n.stunden.gebucht], ['Davon freigegeben', n.stunden.freigegeben], ['Noch ungeprüft', n.stunden.ungeprueft], ['Ohne Lohnsatz', n.stunden.ohne_lohnsatz]].map(([l, v]) => (
              <tr key={l} className="border-t border-black/[0.06]"><td className="py-1.5 text-[#6E6E73]">{l}</td><td className={`py-1.5 text-right font-medium ${(l.startsWith('Noch') || l.startsWith('Ohne')) && v > 0 ? 'text-[#B25E00]' : ''}`}>{v === null || v === undefined ? '–' : `${fmtMenge(v)} h`}</td></tr>
            ))}
          </tbody></table>
          {n.je_person.length > 0 && (
            <>
              <h3 className="text-[14px] font-semibold mt-4 mb-1">Personalkosten je Person <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FDE8E8] text-[#C41E3A] align-middle">vertraulich</span></h3>
              <table className="w-full text-[13px]"><tbody>{n.je_person.map((p) => <tr key={p.name} className="border-t border-black/[0.06]"><td className="py-1">{p.name}<span className="text-[#6E6E73]"> · {p.modell === 'stundenlohn' ? 'Stundenlohn' : p.modell === 'monatsgehalt' ? 'Monatsgehalt' : p.modell === 'firmensatz' ? 'Firmensatz' : 'ohne Satz'}</span></td><td className="py-1 text-right">{fmtMenge(p.minuten / 60)} h</td><td className={`py-1 text-right font-medium ${p.ohne_satz ? 'text-[#B25E00]' : ''}`}>{p.ohne_satz ? 'ohne Satz' : fmtGeld(p.kosten)}</td></tr>)}</tbody></table>
            </>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="text-[17px] mb-2">Material und Eingangsrechnungen</h2>
          <div className="text-[14px] space-y-1">
            <div className="flex justify-between"><span>Material geprüft ({n.ist.material_buchungen} Buchungen)</span><span className="font-medium">{fmtGeld(n.ist.material)}</span></div>
            {n.ist.material_ungeprueft > 0 && <div className="flex justify-between text-[#B25E00]"><span>Material ungeprüft (zählt noch nicht)</span><span>{fmtGeld(n.ist.material_ungeprueft)}</span></div>}
          </div>
          {n.eingangsrechnungen.length > 0 ? (
            <ul className="divide-y divide-black/[0.06] mt-2 text-[13px]">
              {n.eingangsrechnungen.map((r) => <li key={r.id} role="button" tabIndex={0} onClick={() => navigate(`/eingangsrechnungen?id=${r.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/eingangsrechnungen?id=${r.id}`)} className="py-1.5 flex items-center gap-2 cursor-pointer"><div className="flex-1 min-w-0 truncate">{r.lieferant} · {r.rechnungsnummer}{r.rechnungsdatum ? ` · ${fmtDate(fromKey(r.rechnungsdatum))}` : ''}</div><span className="font-medium">{fmtGeld(r.anteil_netto)}</span><span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${r.status === 'erfasst' ? 'bg-[#FFF4E5] text-[#B25E00]' : r.status === 'storniert' ? 'bg-black/[0.06] text-[#6E6E73]' : 'bg-[#E8F8EC] text-[#1B7F3B]'}`}>{r.status}</span></li>)}
            </ul>
          ) : <p className="text-[13px] text-[#6E6E73] mt-2">Keine Eingangsrechnungen diesem Projekt zugeordnet.</p>}
          <p className="text-[11px] text-[#86868B] mt-3">Stand {n.stand ? fmtDate(fromKey(n.stand)) : ''}. Geplante Zeit und tatsächliche Zeit werden nie vermischt; Pauschalprojekte: Pauschale minus zurechenbare Kosten.</p>
        </Card>
      </div>
    </div>
  );
}
