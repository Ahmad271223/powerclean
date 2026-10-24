import React, { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Sheet, TextArea } from '../ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';

const fmtGeld = (x) => (x === null || x === undefined ? '–' : Number(x).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €');

/** KI-Entwurf (Stufe H, nur mit Feature-Flag `ki`): Text eingeben → Vorschlag ansehen → ausdrücklich übernehmen. Gespeichert wird nichts automatisch.
 *  art = 'angebot' (Positionen) oder 'beleg' (Felder einer Eingangsrechnung). `onUebernehmen(daten)` bekommt den geprüften Vorschlag. */
export default function KiEntwurfDialog({ art, onUebernehmen, size = 'sm', variant = 'soft', children }) {
  const { feature } = useAuth();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [ergebnis, setErgebnis] = useState(null);
  const [status, setStatus] = useState(null);
  useEffect(() => { if (open && !status) api.get('/api/ki/status').then(setStatus).catch((err) => setStatus({ bereit: false, fehler: err.message })); }, [open, status]);
  if (!feature('ki')) return null;
  const erzeugen = async () => {
    setBusy(true);
    try { setErgebnis(await api.post(art === 'angebot' ? '/api/ki/angebot-entwurf' : '/api/ki/beleg-vorschlag', { text })); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const uebernehmen = () => {
    if (!ergebnis) return;
    onUebernehmen?.(art === 'angebot' ? ergebnis.positionen : ergebnis.vorschlag);
    toast.success(art === 'angebot' ? 'Positionen in den Entwurf übernommen – bitte Preise prüfen' : 'Felder vorausgefüllt – bitte gegen den Beleg prüfen');
    setOpen(false); setErgebnis(null); setText('');
  };
  const pos = ergebnis?.positionen || [];
  const v = ergebnis?.vorschlag;
  return (
    <>
      <Btn type="button" size={size} variant={variant} onClick={() => setOpen(true)} title="KI-Entwurf (nichts wird ohne Übernahme gespeichert)"><Sparkles size={15} /> {children || 'KI-Entwurf'}</Btn>
      <Sheet open={open} onOpenChange={setOpen} title={art === 'angebot' ? 'KI-Entwurf für Angebotspositionen' : 'KI-Vorschlag aus Belegtext'} width="sm:max-w-2xl"
        subtitle="Die KI macht einen Vorschlag. Gespeichert wird erst, wenn du ihn prüfst und übernimmst. Der eingegebene Text wird an den KI-Anbieter gesendet – keine Passwörter oder Personaldaten eingeben.">
        <div className="space-y-4">
          {status && !status.bereit && <div className="rounded-2xl bg-[#FFF4E5] text-[#7A4100] px-4 py-3 text-[13px]">{status.fehler || (!status.paket ? 'Das Paket „anthropic“ fehlt auf dem Server.' : 'Auf dem Server ist kein KI-Schlüssel hinterlegt (ANTHROPIC_API_KEY).')}</div>}
          <TextArea rows={art === 'angebot' ? 6 : 10} value={text} onChange={(e) => setText(e.target.value)} data-testid="ki-text"
            placeholder={art === 'angebot' ? 'z. B. Grundreinigung Bürogebäude 1.200 m² inkl. Glasflächen 180 m², 2 Mitarbeiter, 3 Tage, Anfahrt 40 km …' : 'Text der Rechnung hier einfügen (z. B. aus dem PDF kopiert oder OCR).'} />
          <div className="flex justify-end gap-2"><Btn variant="dark" onClick={erzeugen} loading={busy} disabled={!text.trim() || (status && !status.bereit)}><Sparkles size={15} /> Entwurf erzeugen</Btn></div>
          {ergebnis && (
            <div className="space-y-3" data-testid="ki-ergebnis">
              <p className="text-[12px] text-[#6E6E73]">{ergebnis.hinweis} · {ergebnis.modell} · {ergebnis.dauer_s} s</p>
              {art === 'angebot' ? (
                pos.length === 0 ? <p className="text-[14px]">Kein Vorschlag.</p> : (
                  <table className="w-full text-[13px]"><thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-2 font-medium">Art</th><th className="py-1 pr-2 font-medium">Text</th><th className="py-1 pr-2 font-medium">Menge</th><th className="py-1 pr-2 font-medium">Einzelpreis</th></tr></thead>
                    <tbody>{pos.map((p, i) => <tr key={i} className={`border-t border-black/[0.06] ${p.unsicher ? 'bg-[#FFF4E5]' : ''}`}><td className="py-1 pr-2">{p.art}</td><td className="py-1 pr-2">{p.text}{p.beschreibung ? <span className="block text-[11px] text-[#6E6E73]">{p.beschreibung}</span> : null}</td><td className="py-1 pr-2 whitespace-nowrap">{p.art === 'titel' || p.art === 'text' ? '' : `${p.menge ?? '–'} ${p.einheit}`}</td><td className="py-1 pr-2 whitespace-nowrap">{p.art === 'titel' || p.art === 'text' ? '' : fmtGeld(p.einzelpreis)}{p.unsicher && <span className="ml-1 text-[10px] font-semibold text-[#B25E00]">prüfen</span>}</td></tr>)}</tbody></table>
                )
              ) : (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[13px]">
                  {[['Lieferant', v?.lieferant], ['USt-IdNr.', v?.lieferant_ustid], ['Rechnungsnummer', v?.rechnungsnummer], ['Rechnungsdatum', v?.rechnungsdatum], ['Fällig am', v?.faellig_am], ['Netto', fmtGeld(v?.netto)], ['USt', fmtGeld(v?.ust)], ['Brutto', fmtGeld(v?.brutto)]].map(([k, w]) => <React.Fragment key={k}><dt className="text-[#6E6E73]">{k}</dt><dd className="font-medium">{w || '–'}</dd></React.Fragment>)}
                </dl>
              )}
              {ergebnis.hinweise?.length > 0 && <ul className="list-disc pl-5 text-[13px] text-[#7A4100]">{ergebnis.hinweise.map((h, i) => <li key={i}>{h}</li>)}</ul>}
              <div className="flex justify-end gap-2"><Btn variant="soft" onClick={() => setErgebnis(null)}>Verwerfen</Btn><Btn onClick={uebernehmen} disabled={art === 'angebot' ? pos.length === 0 : !v}>{art === 'angebot' ? 'Positionen übernehmen' : 'Felder übernehmen'}</Btn></div>
            </div>
          )}
        </div>
      </Sheet>
    </>
  );
}
