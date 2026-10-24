import React, { useCallback, useEffect, useState } from 'react';
import { Ban, CreditCard, FileDown, Mail, Plus, Receipt } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, IconBtn } from '../ui';
import { useDialoge } from '../Dialoge';
import { api, openFile } from '../../lib/api';
import { fmtDate, fromKey } from '../../lib/dates';
import { ART_CLS, AbschlagDialog, STATUS_CLS, SendenDialog, ZahlungDialog, fmtEur } from './RechnungDialoge';

/** Projekt → Abrechnung: Auftragswert und Nachträge, Abschläge, Schlussrechnung, Rechnung aus dem Auftrag, Zahlungsstand je Rechnung. */
export default function AbrechnungTab({ projekt, kunde }) {
  const { fragen, bestaetigen } = useDialoge();
  const [d, setD] = useState(null);
  const [abschlag, setAbschlag] = useState(false);
  const [zahlung, setZahlung] = useState(null);
  const [senden, setSenden] = useState(null);
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/projekte/${projekt.id}/abrechnung`).then(setD).catch((err) => toast.error(err.message)), [projekt.id]);
  useEffect(() => { laden(); }, [laden]);
  const anlegen = async (art) => {
    if (art === 'schluss' && !(await bestaetigen({ titel: 'Schlussrechnung stellen?', text: `Gesamtleistung ${fmtEur(d.basis.basis_netto)} netto abzüglich ${d.abschlaege.length} Abschlagsrechnung${d.abschlaege.length === 1 ? '' : 'en'} (${fmtEur(d.abschlaege.reduce((s, r) => s + (r.net || 0), 0))} netto). Danach sind keine weiteren Abschläge möglich.` }))) return;
    setBusy(art);
    try { const r = await api.post('/api/rechnungen/auftrag', { project_id: projekt.id, art }); toast.success(`${r.rechnung.art_name} ${r.rechnung.number} angelegt`); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const storno = async (r) => {
    if (!r.festgeschrieben_at) { toast.error('Entwürfe werden unter „Rechnungen“ zurückgesetzt, nicht storniert.'); return; }
    const grund = await fragen({ titel: `${r.art_name} ${r.number} stornieren`, text: 'Grund (erscheint auf der Stornorechnung):', pflicht: true });
    if (!grund) return;
    setBusy(r.id);
    try { const x = await api.post(`/api/rechnungen/${r.id}/storno`, { grund }); toast.success(`Stornorechnung ${x.storno.number} angelegt`); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  if (!d) return <Card className="p-5 text-[14px] text-[#6E6E73]">Abrechnung wird geladen …</Card>;
  const b = d.basis;
  const s = d.summen;
  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="text-[17px] flex items-center gap-2"><Receipt size={17} /> Abrechnung</h2>
          <div className="flex flex-wrap gap-2">
            {d.kann_pauschal && <Btn size="sm" variant="soft" onClick={() => anlegen('pauschal')} loading={busy === 'pauschal'}><Plus size={14} /> Rechnung aus Auftrag</Btn>}
            {d.kann_abschlag && <Btn size="sm" onClick={() => setAbschlag(true)}><Plus size={14} /> {d.naechster_abschlag_nr}. Abschlag</Btn>}
            {d.kann_schluss && d.abschlaege.length > 0 && <Btn size="sm" variant="soft" onClick={() => anlegen('schluss')} loading={busy === 'schluss'}><Plus size={14} /> Schlussrechnung</Btn>}
          </div>
        </div>
        {!b.basis_netto ? <p className="text-[14px] text-[#6E6E73]">Kein Auftragswert hinterlegt. Lege aus einem angenommenen Angebot den Auftrag an (Reiter „Angebot & Auftrag“) oder trage im Projekt eine Pauschale ein – dann lassen sich Abschläge, Schluss- und Pauschalrechnungen stellen. Monatsrechnungen nach Stunden entstehen weiterhin im Kalender.</p> : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Auftragssumme netto</div><div className="text-[18px] font-semibold">{fmtEur(b.basis_netto)}</div>{b.nachtraege_netto > 0 && <div className="text-[11px] text-[#86868B]">inkl. {fmtEur(b.nachtraege_netto)} Nachträge</div>}</div>
            <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Gestellt netto</div><div className="text-[18px] font-semibold">{fmtEur(s.gestellt_netto)}</div><div className="text-[11px] text-[#86868B]">Rest {fmtEur(s.rest_netto)}</div></div>
            <div className="rounded-2xl bg-[#E8F8EC] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Bezahlt brutto</div><div className="text-[18px] font-semibold">{fmtEur(s.bezahlt_brutto)}</div></div>
            <div className={`rounded-2xl px-4 py-3 ${s.offen_brutto > 0 ? 'bg-[#FFF4E5]' : 'bg-[#F5F5F7]'}`}><div className="text-[12px] text-[#6E6E73]">Offen brutto</div><div className="text-[18px] font-semibold">{fmtEur(s.offen_brutto)}</div></div>
          </div>
        )}
      </Card>
      <Card className="p-5">
        <h2 className="text-[17px] mb-2">Rechnungen zu diesem Projekt</h2>
        {d.rechnungen.length === 0 ? <Empty icon={Receipt} title="Noch keine Rechnungen" text="Abschläge, Schluss- und Pauschalrechnungen erscheinen hier; Monatsrechnungen nach Stunden entstehen im Kalender." /> : (
          <ul className="divide-y divide-black/[0.06]">
            {d.rechnungen.slice().reverse().map((r) => (
              <li key={r.id} className="py-2.5 flex flex-wrap items-center gap-3 text-[14px]">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold flex items-center gap-2 flex-wrap">{r.number}{r.art !== 'monat' && <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${ART_CLS[r.art] || ''}`}>{r.art_name}{r.art === 'abschlag' && r.leistungsstand_prozent ? ` ${r.leistungsstand_prozent} %` : ''}</span>}<span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[r.status] || ''}`}>{r.status_name}</span>{!r.festgeschrieben_at && r.status === 'offen' && <span className="text-[11px] text-[#86868B]">Entwurf</span>}</div>
                  <div className="text-[12px] text-[#6E6E73]">{r.invoice_date ? fmtDate(fromKey(r.invoice_date)) : ''}{r.faellig_am && r.status !== 'bezahlt' && r.art !== 'storno' ? ` · fällig ${fmtDate(fromKey(r.faellig_am))}` : ''}{r.storno_nummer ? ` · storniert durch ${r.storno_nummer}` : ''}{r.mahnstufe ? ` · Mahnstufe ${r.mahnstufe}` : ''}</div>
                </div>
                <div className="text-right"><div className="font-semibold">{fmtEur(r.gross)}</div>{r.offen_betrag > 0 && r.status !== 'storniert' && <div className="text-[11px] text-[#B25E00]">offen {fmtEur(r.offen_betrag)}</div>}</div>
                <div className="flex items-center gap-1">
                  <IconBtn size={32} variant="soft" onClick={() => openFile(`/api/rechnungen/${r.id}/rechnung.pdf`).then(laden).catch((e) => toast.error(e.message))} title="PDF"><FileDown size={15} /></IconBtn>
                  {!['storno', 'gutschrift'].includes(r.art) && r.status !== 'storniert' && <IconBtn size={32} variant="soft" onClick={() => setZahlung(r)} title="Zahlungen"><CreditCard size={15} /></IconBtn>}
                  {r.status !== 'storniert' && <IconBtn size={32} variant="soft" onClick={() => setSenden(r)} title="Per E-Mail senden"><Mail size={15} /></IconBtn>}
                  {r.status !== 'storniert' && r.art !== 'storno' && r.festgeschrieben_at && <IconBtn size={32} onClick={() => storno(r)} title="Stornieren (Korrekturbeleg)" className="text-[#6E6E73]"><Ban size={14} /></IconBtn>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <AbschlagDialog open={abschlag} onOpenChange={setAbschlag} projekt={projekt} abrechnung={d} onSaved={laden} />
      <ZahlungDialog rechnung={zahlung} onOpenChange={(o) => { if (!o) setZahlung(null); }} onSaved={laden} />
      <SendenDialog rechnung={senden} kundeEmail={kunde?.email || ''} onOpenChange={(o) => { if (!o) setSenden(null); }} onSaved={laden} />
    </div>
  );
}
