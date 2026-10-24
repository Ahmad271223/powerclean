import React, { useEffect, useState } from 'react';
import { Calculator, Info, Wand2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, TextInput } from '../ui';
import { api } from '../../lib/api';
import { KALKULATION_FELDER, KALKULATION_ZUSCHLAEGE, fmtGeld, fmtProzent } from '../../lib/angebot';

const num = (v) => (v === '' || v === null || v === undefined ? '' : v);

function Kennzahl({ label, wert, hinweis, warn }) {
  return (
    <div className={`rounded-2xl px-4 py-3 ${warn ? 'bg-[#FFF4E5]' : 'bg-[#F5F5F7]'}`}>
      <div className="text-[12px] text-[#6E6E73]">{label}</div>
      <div className="text-[18px] font-semibold leading-tight">{wert}</div>
      {hinweis && <div className="text-[11px] text-[#86868B] mt-0.5">{hinweis}</div>}
    </div>
  );
}

/** Interne Kalkulation (nur mit Recht „kalkulation“): je Position Stunden, interner Stundensatz, Material-Einkauf, Fremdleistung, Geräte, Transport,
 *  Zuschläge für Gemeinkosten, Risiko und Gewinn → Selbstkosten, Preisvorschlag, Gewinn, Aufschlag, Marge, Deckungsbeitrag. Nichts davon erreicht den Kunden. */
export default function KalkulationPanel({ angebotId, positionen, kalkulation, bearbeitbar, onAngebot }) {
  const [eingaben, setEingaben] = useState({});
  const [k, setK] = useState(kalkulation);
  const [mehr, setMehr] = useState(false);
  const [busy, setBusy] = useState('');
  useEffect(() => { setK(kalkulation); }, [kalkulation]);
  useEffect(() => {
    const e = {};
    (positionen || []).forEach((p) => { if (p.art !== 'titel' && p.art !== 'text') e[p.id] = { ...(p.kalkulation || {}) }; });
    setEingaben(e);
  }, [positionen]);
  const set = (id, feld, wert) => setEingaben((e) => ({ ...e, [id]: { ...(e[id] || {}), [feld]: wert } }));

  const speichern = async () => {
    setBusy('speichern');
    try {
      const r = await api.put(`/api/kundenangebote/${angebotId}/kalkulation`, { positionen: eingaben });
      setK(r.kalkulation);
      onAngebot?.(r.angebot);
      toast.success('Kalkulation gespeichert');
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const uebernehmen = async (positionId) => {
    setBusy(positionId || 'alle');
    try {
      await api.put(`/api/kundenangebote/${angebotId}/kalkulation`, { positionen: eingaben });
      const r = await api.post(`/api/kundenangebote/${angebotId}/kalkulation/uebernehmen${positionId ? `?position_id=${positionId}` : ''}`);
      onAngebot?.(r.angebot);
      setK(r.angebot?.kalkulation || k);
      toast.success(`${r.uebernommen} Preis${r.uebernommen === 1 ? '' : 'e'} aus der Kalkulation übernommen`);
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };

  const zeilen = (positionen || []).filter((p) => p.art !== 'titel' && p.art !== 'text');
  const firmaK = k?.firma || {};
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="text-[17px] flex items-center gap-2"><Calculator size={17} /> Interne Kalkulation <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FDE8E8] text-[#C41E3A]">vertraulich</span></h2>
        <div className="flex gap-2">
          {bearbeitbar && <Btn size="sm" variant="soft" onClick={() => uebernehmen(null)} loading={busy === 'alle'} title="Preisvorschläge aller kalkulierten Positionen als Einzelpreise übernehmen"><Wand2 size={15} /> Alle Preise übernehmen</Btn>}
          <Btn size="sm" onClick={speichern} loading={busy === 'speichern'}>Kalkulation speichern</Btn>
        </div>
      </div>
      {k && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <Kennzahl label="Verkauf (netto)" wert={fmtGeld(k.netto)} hinweis="nach Zuschlägen und Rabatt" />
          <Kennzahl label="Selbstkosten" wert={fmtGeld(k.selbstkosten)} hinweis={`direkt ${fmtGeld(k.direkt)} + GK ${fmtGeld(k.gemeinkosten)} + Risiko ${fmtGeld(k.risiko)}`} warn={!k.vollstaendig} />
          <Kennzahl label="Gewinn" wert={k.vollstaendig ? fmtGeld(k.gewinn) : `${fmtGeld(k.gewinn)} (unvollständig)`} hinweis={`Aufschlag ${fmtProzent(k.aufschlag_prozent)} · Marge ${fmtProzent(k.marge_prozent)}`} warn={!k.vollstaendig} />
          <Kennzahl label="Deckungsbeitrag" wert={fmtGeld(k.deckungsbeitrag)} hinweis={k.stundenverrechnungssatz ? `Stundenverrechnungssatz ${fmtGeld(k.stundenverrechnungssatz)}/Std.` : 'Verkauf minus direkte Kosten'} />
        </div>
      )}
      {k?.hinweise?.length > 0 && <ul className="text-[13px] text-[#B25E00] mb-3 space-y-0.5">{k.hinweise.map((h) => <li key={h}>⚠ {h}</li>)}</ul>}
      <div className="overflow-x-auto -mx-1 px-1">
        <table className="w-full text-[13px] min-w-[900px]">
          <thead>
            <tr className="text-left text-[#6E6E73] text-[11px]">
              <th className="py-1 pr-2 w-10">Pos.</th><th className="py-1 pr-2">Position</th>
              {KALKULATION_FELDER.map(([f, l, e]) => <th key={f} className="py-1 pr-1 text-right whitespace-nowrap">{l}<br /><span className="font-normal">{e}</span></th>)}
              {mehr && KALKULATION_ZUSCHLAEGE.map(([f, l]) => <th key={f} className="py-1 pr-1 text-right whitespace-nowrap">{l} %</th>)}
              <th className="py-1 pr-1 text-right">Selbstkosten</th><th className="py-1 pr-1 text-right">Vorschlag</th><th className="py-1 pr-1 text-right">Verkauf</th><th className="py-1 text-right">Marge</th>{bearbeitbar && <th />}
            </tr>
          </thead>
          <tbody>
            {zeilen.map((p) => {
              const e = eingaben[p.id] || {};
              const r = k?.je_position?.[p.id];
              return (
                <tr key={p.id} className={`border-t border-black/[0.06] align-middle ${p.zaehlt === false ? 'text-[#6E6E73]' : ''}`}>
                  <td className="py-1 pr-2">{p.nr}</td>
                  <td className="py-1 pr-2 max-w-[180px] truncate" title={p.text}>{p.text || '–'}{p.zaehlt === false && <span className="ml-1 text-[11px]">(nicht in der Summe)</span>}</td>
                  {KALKULATION_FELDER.map(([f]) => (
                    <td key={f} className="py-1 pr-1"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={num(e[f])} onChange={(ev) => set(p.id, f, ev.target.value)} placeholder={f === 'stundensatz' ? String(firmaK.stundensatz ?? '') : f === 'stunden' && p.art === 'stunden' ? String(p.menge ?? '') : ''} className="w-[82px] text-right h-9 px-2" /></td>
                  ))}
                  {mehr && KALKULATION_ZUSCHLAEGE.map(([f]) => (
                    <td key={f} className="py-1 pr-1"><TextInput type="number" inputMode="decimal" step="0.1" min="0" value={num(e[f])} onChange={(ev) => set(p.id, f, ev.target.value)} placeholder={String(firmaK[f] ?? '')} className="w-[64px] text-right h-9 px-2" /></td>
                  ))}
                  <td className="py-1 pr-1 text-right">{r ? fmtGeld(r.selbstkosten) : '–'}</td>
                  <td className="py-1 pr-1 text-right">{r ? fmtGeld(r.vk_vorschlag) : '–'}</td>
                  <td className="py-1 pr-1 text-right font-medium">{fmtGeld(p.gesamt)}</td>
                  <td className={`py-1 text-right ${r && r.gewinn < 0 ? 'text-[#C41E3A]' : ''}`}>{r ? fmtProzent(r.marge_prozent) : '–'}</td>
                  {bearbeitbar && <td className="py-1 pl-1">{r && <Btn size="sm" variant="ghost" onClick={() => uebernehmen(p.id)} loading={busy === p.id} title="Preisvorschlag als Einzelpreis übernehmen"><Wand2 size={14} /></Btn>}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-2 text-[12px] text-[#6E6E73]">
        <button type="button" className="text-[#C41E3A] font-medium" onClick={() => setMehr((m) => !m)}>{mehr ? 'Zuschläge je Position ausblenden' : 'Zuschläge je Position anpassen (Gemeinkosten, Risiko, Gewinn)'}</button>
        <span>Standard der Firma: Stundensatz {fmtGeld(firmaK.stundensatz)}, Gemeinkosten {fmtProzent(firmaK.gemeinkosten_prozent)}, Risiko {fmtProzent(firmaK.risiko_prozent)}, Gewinn {fmtProzent(firmaK.gewinn_prozent)} (Firma → Angebote).</span>
      </div>
      {k?.erklaerung && (
        <div className="mt-3 rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[12px] text-[#6E6E73] flex gap-2">
          <Info size={14} className="shrink-0 mt-0.5" />
          <div><div>{k.erklaerung.selbstkosten}</div><div>{k.erklaerung.aufschlag}</div><div>{k.erklaerung.marge}</div><div>{k.erklaerung.deckungsbeitrag}</div></div>
        </div>
      )}
    </Card>
  );
}
