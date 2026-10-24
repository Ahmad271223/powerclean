import React, { useState } from 'react';
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react';
import { Btn, IconBtn, Select, TextArea, TextInput } from '../ui';
import { EINHEITEN, POSITIONSARTEN, fmtGeld, leerePosition, nummerieren, positionBetrag } from '../../lib/angebot';

const num = (v) => (v === '' || v === null || v === undefined ? '' : v);

/** Positionen eines Angebots: Titel gliedern, Positionen mit Menge/Einheit/Einzelpreis, Nachlass je Position, Alternativ-/Eventualkennzeichen.
 *  Im Lesemodus (gesendete Angebote) werden dieselben Zeilen ohne Eingabefelder gezeigt. */
export default function PositionenEditor({ positionen, onChange, leistungen = [], readOnly = false }) {
  const [offen, setOffen] = useState({});   // Beschreibung/Details je Position aufgeklappt
  const liste = nummerieren(positionen || []);
  const set = (i, patch) => onChange(positionen.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  const entfernen = (i) => onChange(positionen.filter((_, j) => j !== i));
  const bewegen = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= positionen.length) return;
    const neu = [...positionen];
    [neu[i], neu[j]] = [neu[j], neu[i]];
    onChange(neu);
  };
  const anfuegen = (art) => onChange([...(positionen || []), leerePosition(art)]);
  const ausLeistung = (id) => {
    const l = leistungen.find((x) => x.id === id);
    if (!l) return;
    onChange([...(positionen || []), { ...leerePosition('stunden'), text: l.name, einzelpreis: Number(l.hourly_rate) || 0, leistung_id: l.id }]);
  };

  if (readOnly) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-[13px] min-w-[640px]">
          <thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="py-2 pr-2 w-12">Pos.</th><th className="py-2 pr-2">Leistung</th><th className="py-2 pr-2 text-right">Menge</th><th className="py-2 pr-2">Einheit</th><th className="py-2 pr-2 text-right">Einzelpreis</th><th className="py-2 text-right">Gesamt</th></tr></thead>
          <tbody>
            {liste.map((p) => (
              <tr key={p.id} className={`border-t border-black/[0.06] align-top ${p.art === 'titel' ? 'bg-[#FAFAFA] font-semibold' : ''}`}>
                <td className="py-2 pr-2 text-[#6E6E73]">{p.nr}</td>
                <td className="py-2 pr-2" colSpan={p.art === 'titel' || p.art === 'text' ? 5 : 1}>
                  <div className={p.art === 'text' ? 'text-[#6E6E73]' : ''}>{p.text || <span className="text-[#C7C7CC]">ohne Text</span>}</div>
                  {p.beschreibung && <div className="text-[12px] text-[#6E6E73] whitespace-pre-line">{p.beschreibung}</div>}
                  {p.alternativ && <span className="inline-block mt-1 text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FFF4E5] text-[#B25E00]">Alternativposition – nicht in der Summe</span>}
                  {p.eventual && <span className="inline-block mt-1 text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FFF4E5] text-[#B25E00]">Eventualposition – nur bei Bedarf</span>}
                  {Number(p.rabatt_prozent) > 0 && <div className="text-[12px] text-[#6E6E73]">abzüglich {p.rabatt_prozent} % Nachlass</div>}
                </td>
                {p.art !== 'titel' && p.art !== 'text' && (<>
                  <td className="py-2 pr-2 text-right">{Number(p.menge || 0).toLocaleString('de-DE', { maximumFractionDigits: 2 })}</td>
                  <td className="py-2 pr-2">{p.einheit}</td>
                  <td className="py-2 pr-2 text-right">{fmtGeld(p.einzelpreis)}</td>
                  <td className={`py-2 text-right ${p.alternativ || p.eventual ? 'text-[#6E6E73]' : 'font-medium'}`}>{fmtGeld(positionBetrag(p))}</td>
                </>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="min-w-[760px] space-y-1.5">
          <div className="grid grid-cols-[40px_1fr_84px_76px_100px_100px_40px_72px] gap-2 text-[11px] text-[#6E6E73] px-1"><div>Pos.</div><div>Leistung</div><div className="text-right">Menge</div><div>Einheit</div><div className="text-right">Einzelpreis</div><div className="text-right">Gesamt</div><div /><div /></div>
          {liste.map((p, i) => {
            const struktur = p.art === 'titel' || p.art === 'text';
            const aufgeklappt = !!offen[p.id];
            return (
              <div key={p.id} className={`rounded-2xl border border-black/[0.06] px-1 py-1.5 ${p.art === 'titel' ? 'bg-[#FAFAFA]' : 'bg-white'} ${p.alternativ || p.eventual ? 'border-dashed border-[#B25E00]/40' : ''}`}>
                <div className="grid grid-cols-[40px_1fr_84px_76px_100px_100px_40px_72px] gap-2 items-center">
                  <div className="text-[12px] text-[#6E6E73] text-center">{p.nr || '–'}</div>
                  <div className="flex gap-1.5 min-w-0">
                    <Select value={p.art} onChange={(e) => set(i, { art: e.target.value, ...(e.target.value === 'stunden' ? { einheit: 'Std.' } : e.target.value === 'pauschal' ? { einheit: 'Psch.', menge: p.menge || 1 } : {}) })} className="w-[132px] shrink-0">
                      {Object.entries(POSITIONSARTEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                    <TextInput value={p.text || ''} onChange={(e) => set(i, { text: e.target.value })} placeholder={p.art === 'titel' ? 'Titel, z. B. „Regelmäßige Reinigung“' : p.art === 'text' ? 'Hinweistext (ohne Preis)' : 'Leistung'} className={p.art === 'titel' ? 'font-semibold' : ''} />
                  </div>
                  {struktur ? <><div /><div /><div /><div /></> : (<>
                    <TextInput type="number" inputMode="decimal" step="0.01" min="0" value={num(p.menge)} onChange={(e) => set(i, { menge: e.target.value })} className="text-right" />
                    <TextInput list="angebot-einheiten" value={p.einheit || ''} onChange={(e) => set(i, { einheit: e.target.value })} />
                    <TextInput type="number" inputMode="decimal" step="0.01" value={num(p.einzelpreis)} onChange={(e) => set(i, { einzelpreis: e.target.value })} className="text-right" />
                    <div className={`text-right text-[14px] pr-1 ${p.alternativ || p.eventual ? 'text-[#6E6E73]' : 'font-semibold'}`}>{fmtGeld(positionBetrag(p))}</div>
                  </>)}
                  <IconBtn size={32} onClick={() => setOffen((o) => ({ ...o, [p.id]: !aufgeklappt }))} title="Beschreibung, Nachlass, Alternativ/Eventual">{aufgeklappt ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</IconBtn>
                  <div className="flex items-center gap-0.5">
                    <IconBtn size={28} onClick={() => bewegen(i, -1)} disabled={i === 0} title="Nach oben"><ArrowUp size={14} /></IconBtn>
                    <IconBtn size={28} onClick={() => bewegen(i, 1)} disabled={i === liste.length - 1} title="Nach unten"><ArrowDown size={14} /></IconBtn>
                    <IconBtn size={28} onClick={() => entfernen(i)} title="Entfernen" className="text-[#C41E3A]"><Trash2 size={14} /></IconBtn>
                  </div>
                </div>
                {aufgeklappt && (
                  <div className="grid grid-cols-[1fr_200px] gap-3 px-1 pt-2 pb-1">
                    <TextArea rows={2} value={p.beschreibung || ''} onChange={(e) => set(i, { beschreibung: e.target.value })} placeholder="Beschreibung (erscheint unter der Position)" />
                    {!struktur && (
                      <div className="text-[13px] space-y-1.5">
                        <label className="flex items-center gap-2">Nachlass <TextInput type="number" inputMode="decimal" step="0.1" min="0" max="100" value={num(p.rabatt_prozent)} onChange={(e) => set(i, { rabatt_prozent: e.target.value })} className="w-20 text-right" /> %</label>
                        <label className="flex items-center gap-2"><input type="checkbox" checked={!!p.alternativ} onChange={(e) => set(i, { alternativ: e.target.checked, eventual: e.target.checked ? false : p.eventual })} /> Alternativposition</label>
                        <label className="flex items-center gap-2"><input type="checkbox" checked={!!p.eventual} onChange={(e) => set(i, { eventual: e.target.checked, alternativ: e.target.checked ? false : p.alternativ })} /> Eventualposition</label>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <datalist id="angebot-einheiten">{EINHEITEN.map((e) => <option key={e} value={e} />)}</datalist>
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <Btn size="sm" variant="soft" onClick={() => anfuegen('leistung')}><Plus size={15} /> Position</Btn>
        <Btn size="sm" variant="soft" onClick={() => anfuegen('titel')}><Plus size={15} /> Titel</Btn>
        <Btn size="sm" variant="ghost" onClick={() => anfuegen('text')}><Plus size={15} /> Textzeile</Btn>
        {leistungen.length > 0 && (
          <Select value="" onChange={(e) => ausLeistung(e.target.value)} className="ml-auto">
            <option value="">Aus Leistung übernehmen …</option>
            {leistungen.map((l) => <option key={l.id} value={l.id}>{l.name}{l.hourly_rate ? ` – ${fmtGeld(l.hourly_rate)}/Std.` : ''}</option>)}
          </Select>
        )}
      </div>
      {liste.length === 0 && <p className="text-[13px] text-[#6E6E73] mt-2">Noch keine Positionen. Füge Positionen hinzu oder übernimm eine Leistung mit ihrem Stundensatz.</p>}
    </div>
  );
}
