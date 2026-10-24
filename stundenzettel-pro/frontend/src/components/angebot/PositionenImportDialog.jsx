import React, { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Btn, Sheet, Toggle } from '../ui';
import { api } from '../../lib/api';
import { fmtGeld, fmtMenge } from '../../lib/angebot';

/** Positionen aus einer Datei (CSV, Excel .xlsx, GAEB DA XML .x83) mit Vorschau und Fehlerzeilen – für Kundenangebote (mit Anhängen/Ersetzen)
 *  und Ausschreibungen (Leistungsverzeichnis ersetzen). `url` ist der Endpunkt, der `vorschau` (0/1) als Formularfeld versteht. */
export default function PositionenImportDialog({ open, onOpenChange, url, mitModus = false, onDone }) {
  const datei = useRef(null);
  const [vorschau, setVorschau] = useState(null);
  const [anhaengen, setAnhaengen] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setVorschau(null); setAnhaengen(false); } }, [open]);
  const lesen = async (endgueltig) => {
    const f = datei.current?.files?.[0];
    if (!f) { toast.error('Bitte eine Datei wählen (CSV, Excel oder GAEB .x83)'); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('datei', f); fd.append('vorschau', endgueltig ? '0' : '1');
      if (mitModus) fd.append('modus', anhaengen ? 'anhaengen' : 'ersetzen');
      const r = await api.upload(url, fd);
      setVorschau(r);
      if (endgueltig && r.vorschau === false) { toast.success(`${(r.positionen || r.angebot?.positionen || []).length} Positionen übernommen${r.fehler?.length ? `, ${r.fehler.length} Hinweise` : ''}`); onDone?.(r); onOpenChange(false); }
      else if (endgueltig) toast.error('Keine gültigen Positionen in der Datei.');
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const positionen = vorschau?.positionen || [];
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Positionen aus Datei" subtitle="CSV (Nr;Leistung;Menge;Einheit;Beschreibung;Einzelpreis – Kopfzeile wird erkannt), Excel (.xlsx) oder GAEB DA XML (.x83). Vorschau zeigt, was übernommen wird und welche Zeilen nicht passen." width="sm:max-w-2xl"
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Schließen</Btn><Btn variant="soft" onClick={() => lesen(false)} loading={busy}>Vorschau</Btn><Btn onClick={() => lesen(true)} loading={busy} disabled={!vorschau || !positionen.length}>Übernehmen ({positionen.length})</Btn></>}>
      <input ref={datei} type="file" accept=".csv,.txt,.xlsx,.x83,.x84,.x81,.x82,.x85,.x86,text/csv,application/xml,text/xml,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="block w-full text-[14px]" />
      {mitModus && <div className="rounded-2xl bg-[#F5F5F7] px-4 mt-3"><Toggle checked={anhaengen} onChange={setAnhaengen} label="An bestehende Positionen anhängen" hint="Aus: die Positionen der Datei ersetzen alle bisherigen." /></div>}
      {vorschau && (
        <div className="mt-3 text-[13px] space-y-2">
          <div className="text-[#6E6E73]">Quelle: {vorschau.quelle || 'Datei'}{vorschau.phase ? ` (GAEB X${vorschau.phase})` : ''} · {positionen.length} Positionen</div>
          {vorschau.fehler?.length > 0 && <div className="rounded-2xl bg-[#FFF4E5] px-3 py-2"><div className="font-semibold text-[#B25E00] mb-1">{vorschau.fehler.length} Hinweise</div><ul className="space-y-0.5">{vorschau.fehler.slice(0, 50).map((x, i) => <li key={i}>{x.zeile ? `Zeile ${x.zeile}: ` : ''}{x.grund}</li>)}</ul></div>}
          {positionen.length > 0 && (
            <div className="overflow-x-auto"><table className="w-full text-[12px] min-w-[520px]"><thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-2">Nr.</th><th className="py-1 pr-2">Leistung</th><th className="py-1 pr-2 text-right">Menge</th><th className="py-1 pr-2">Einheit</th><th className="py-1 text-right">EP</th></tr></thead>
              <tbody>{positionen.slice(0, 200).map((p, i) => <tr key={i} className={`border-t border-black/[0.06] ${p.art === 'titel' ? 'font-semibold bg-[#FAFAFA]' : ''}`}><td className="py-1 pr-2">{p.import_nr || p.nr}</td><td className="py-1 pr-2">{p.text || p.leistung}</td><td className="py-1 pr-2 text-right">{p.art === 'titel' ? '' : fmtMenge(p.menge)}</td><td className="py-1 pr-2">{p.art === 'titel' ? '' : p.einheit}</td><td className="py-1 text-right">{p.einzelpreis ? fmtGeld(p.einzelpreis) : ''}</td></tr>)}</tbody></table></div>
          )}
        </div>
      )}
    </Sheet>
  );
}
