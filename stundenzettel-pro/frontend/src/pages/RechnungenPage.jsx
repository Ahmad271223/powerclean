import React, { useCallback, useEffect, useState } from 'react';
import { Receipt, FileStack, Download, RotateCcw, CheckCircle2, Ban, ListPlus, Trash2, Plus } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Empty, IconBtn, Select, Sheet, TextInput } from '../components/ui';
import { api } from '../lib/api';
import { invoicePdf, monthPdf, signatureMap, preloadLogo } from '../lib/pdf';
import { fmtDate, fmtDecimalHours, fmtEur, fromKey, MONTHS_DE, monthLastDay, toKey } from '../lib/dates';
import { deliverPdf } from '../lib/utils';

const STATUS_CLS = { offen: 'bg-[#FFF4E5] text-[#B25E00]', bezahlt: 'bg-[#E8F8EC] text-[#1B7F3B]', storniert: 'bg-black/[0.06] text-[#6E6E73]' };
const VORSCHLAEGE = [['Anfahrt', 'Fahrten'], ['Reinigungsmittel', 'Stk.'], ['Entsorgung', 'Pauschale'], ['Maschinenmiete', 'Tage'], ['Sonderreinigung', 'Pauschale']];

export default function RechnungenPage() {
  const [daten, setDaten] = useState(null);
  const [jahr, setJahr] = useState('');
  const [status, setStatus] = useState('alle');
  const [busy, setBusy] = useState('');
  const [extras, setExtras] = useState(null);   // Rechnung, deren Zusatzpositionen bearbeitet werden
  const laden = useCallback(() => api.get(`/api/rechnungen${jahr ? `?jahr=${jahr}` : ''}`).then(setDaten).catch((err) => toast.error(err.message)), [jahr]);
  useEffect(() => { laden(); }, [laden]);

  const liste = (daten?.rechnungen || []).filter((r) => status === 'alle' || r.status === status);
  const summe = (st) => (daten?.rechnungen || []).filter((r) => r.status === st).reduce((s, r) => s + (Number(r.gross) || 0), 0);

  const pdf = async (r, art, mode) => {
    setBusy(`${art}-${r.id}`);
    try {
      const d = await api.get(`/api/rechnungen/${r.id}/daten`);
      await preloadLogo(d.firma);
      const m0 = r.month - 1;
      const first = toKey(new Date(r.year, m0, 1));
      const last = toKey(monthLastDay(r.year, m0));
      const monthE = d.eintraege.filter((e) => e.date >= first && e.date <= last);
      const result = art === 'month' ? monthPdf(d.projekt, d.firma, r.year, m0, d.eintraege, d.rechnung, signatureMap(d.unterschriften)) : invoicePdf(d.projekt, d.firma, r.year, m0, monthE, d.rechnung);
      await deliverPdf(result, mode);
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const setzen = async (r, st) => {
    if (st === 'storniert' && !window.confirm(`Rechnung ${r.number} stornieren?`)) return;
    try { await api.put(`/api/rechnungen/${r.id}`, { status: st }); toast.success(st === 'bezahlt' ? 'Als bezahlt markiert' : st === 'offen' ? 'Wieder offen' : 'Storniert'); laden(); } catch (err) { toast.error(err.message); }
  };
  const reset = async (r) => {
    if (!window.confirm(`Rechnungsnummer ${r.number} zurücksetzen? Beim nächsten PDF wird eine neue Nummer vergeben.`)) return;
    try { await api.del(`/api/rechnungen/${r.id}`); toast.success('Zurückgesetzt'); laden(); } catch (err) { toast.error(err.message); }
  };

  return (
    <Layout title="Rechnungen" subtitle="Eine Rechnung je Projekt und Monat. Neue entstehen im Kalender eines Projekts."
      action={daten?.jahre?.length > 1 ? <Select value={jahr} onChange={(e) => setJahr(e.target.value)}><option value="">Alle Jahre</option>{daten.jahre.map((j) => <option key={j} value={j}>{j}</option>)}</Select> : null}>
      {!daten ? <Ladeanzeige /> : (
        <>
          <div className="grid grid-cols-3 gap-3 mb-5">
            {[['offen', 'Offen'], ['bezahlt', 'Bezahlt'], ['storniert', 'Storniert']].map(([st, l]) => (
              <button key={st} type="button" onClick={() => setStatus(status === st ? 'alle' : st)} className={`rounded-2xl p-4 text-left transition-all ${status === st ? 'bg-[#1D1D1F] text-white' : 'bg-white shadow-card'}`}>
                <div className={`text-[12px] ${status === st ? 'text-white/70' : 'text-[#6E6E73]'}`}>{l} ({daten.rechnungen.filter((r) => r.status === st).length})</div>
                <div className="text-[20px] font-bold tracking-tight">{fmtEur(summe(st))}</div>
              </button>
            ))}
          </div>
          {liste.length === 0 ? <Card><Empty icon={Receipt} title="Keine Rechnungen" text="Öffne ein Projekt und erstelle über „Monats-PDF“ oder „Nur Rechnung“ die erste Rechnung." /></Card> : (
            <div className="space-y-3">
              {liste.map((r) => (
                <Card key={r.id} className="p-4 sm:p-5 flex flex-wrap items-center gap-3">
                  <div className="flex-1 min-w-[220px]">
                    <div className="text-[15px] font-semibold flex items-center gap-2">{r.number} <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[r.status] || ''}`}>{r.status}</span></div>
                    <div className="text-[13px] text-[#6E6E73] truncate">{r.project_name}{r.customer_name ? ` · ${r.customer_name}` : ''} · {MONTHS_DE[r.month - 1]} {r.year} · vom {fmtDate(fromKey(r.invoice_date))}{r.paid_at ? ` · bezahlt ${fmtDate(fromKey(r.paid_at))}` : ''}</div>
                    <div className="text-[12px] text-[#86868B] mt-0.5">{fmtDecimalHours(r.total_minutes || 0)} Std. · netto {fmtEur(r.net || 0)}{r.extras_anzahl ? ` · ${r.extras_anzahl} Zusatzposition${r.extras_anzahl > 1 ? 'en' : ''} (${fmtEur(r.extras_net || 0)})` : ''}{r.reverse_charge ? ' · § 13b' : ''}</div>
                  </div>
                  <div className="text-[18px] font-bold tracking-tight">{fmtEur(r.gross || 0)}</div>
                  <div className="flex items-center gap-1 flex-wrap">
                    <Btn size="sm" onClick={() => pdf(r, 'invoice')} loading={busy === `invoice-${r.id}`}><Receipt size={15} /> PDF</Btn>
                    <IconBtn size={34} variant="soft" onClick={() => pdf(r, 'month')} disabled={!!busy} title="Monats-PDF (Stundenzettel + Rechnung)"><FileStack size={15} /></IconBtn>
                    <IconBtn size={34} variant="soft" onClick={() => pdf(r, 'invoice', 'download')} disabled={!!busy} title="Rechnung herunterladen"><Download size={15} /></IconBtn>
                    {r.status === 'offen' && <><IconBtn size={34} variant="soft" onClick={() => setExtras(r)} title="Zusatzpositionen (Material, Anfahrt, Pauschalen)"><ListPlus size={16} /></IconBtn><IconBtn size={34} onClick={() => setzen(r, 'bezahlt')} title="Als bezahlt markieren" className="text-[#1B7F3B]"><CheckCircle2 size={16} /></IconBtn><IconBtn size={34} onClick={() => setzen(r, 'storniert')} title="Stornieren" className="text-[#6E6E73]"><Ban size={15} /></IconBtn><IconBtn size={34} onClick={() => reset(r)} title="Nummer zurücksetzen" className="text-[#A1A1A6]"><RotateCcw size={14} /></IconBtn></>}
                    {r.status === 'bezahlt' && <Btn size="sm" variant="ghost" onClick={() => setzen(r, 'offen')}>Wieder offen</Btn>}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
      <ExtrasDialog rechnung={extras} onOpenChange={(o) => { if (!o) setExtras(null); }} onSaved={laden} />
    </Layout>
  );
}

/** Zusatzpositionen einer offenen Rechnung: Material, Anfahrt, Pauschalen – Summen rechnet der Server neu. */
function ExtrasDialog({ rechnung, onOpenChange, onSaved }) {
  const [zeilen, setZeilen] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!rechnung) return;
    api.get(`/api/rechnungen/${rechnung.id}/daten`).then((d) => setZeilen((d.rechnung.extras || []).map((x) => ({ text: x.text, quantity: String(x.quantity), unit: x.unit || '', unit_price: String(x.unit_price) })))).catch((err) => toast.error(err.message));
  }, [rechnung]);
  if (!rechnung) return null;
  const set = (i, k, v) => setZeilen((z) => z.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  const add = (text = '', unit = 'Stk.') => setZeilen((z) => [...z, { text, quantity: '1', unit, unit_price: '' }]);
  const zahl = (s) => parseFloat(String(s).replace(',', '.')) || 0;
  const summe = zeilen.reduce((s, x) => s + zahl(x.quantity) * zahl(x.unit_price), 0);
  const speichern = async () => {
    const extras = zeilen.filter((x) => x.text.trim()).map((x) => ({ text: x.text.trim(), quantity: zahl(x.quantity), unit: x.unit.trim() || 'Stk.', unit_price: zahl(x.unit_price) }));
    setBusy(true);
    try { const r = await api.put(`/api/rechnungen/${rechnung.id}/extras`, { extras }); toast.success(`Gespeichert – Rechnungsbetrag jetzt ${fmtEur(r.rechnung.gross)}`); onSaved?.(); onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={!!rechnung} onOpenChange={onOpenChange} title={`Zusatzpositionen · ${rechnung.number}`} subtitle="Material, Anfahrt, Entsorgung, Pauschalen – erscheinen unter den Stunden auf der Rechnung." width="sm:max-w-2xl">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">{VORSCHLAEGE.map(([t, u]) => <Btn key={t} size="sm" variant="soft" onClick={() => add(t, u)}><Plus size={13} /> {t}</Btn>)}<Btn size="sm" variant="ghost" onClick={() => add()}><Plus size={13} /> Leere Zeile</Btn></div>
        {zeilen.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine Zusatzpositionen.</p> : (
          <div className="space-y-2">
            <div className="hidden sm:grid grid-cols-[1fr_80px_90px_100px_36px] gap-2 text-[11px] uppercase tracking-wider text-[#86868B] px-1"><span>Bezeichnung</span><span>Menge</span><span>Einheit</span><span>Einzelpreis €</span><span /></div>
            {zeilen.map((x, i) => (
              <div key={i} className="grid grid-cols-2 sm:grid-cols-[1fr_80px_90px_100px_36px] gap-2 items-center">
                <TextInput value={x.text} onChange={(e) => set(i, 'text', e.target.value)} placeholder="Bezeichnung" className="col-span-2 sm:col-span-1" />
                <TextInput type="number" step="0.01" min="0" inputMode="decimal" value={x.quantity} onChange={(e) => set(i, 'quantity', e.target.value)} placeholder="Menge" />
                <TextInput value={x.unit} onChange={(e) => set(i, 'unit', e.target.value)} placeholder="Einheit" />
                <TextInput type="number" step="0.01" inputMode="decimal" value={x.unit_price} onChange={(e) => set(i, 'unit_price', e.target.value)} placeholder="Preis" />
                <IconBtn size={32} variant="danger" onClick={() => setZeilen((z) => z.filter((_, j) => j !== i))} title="Entfernen"><Trash2 size={14} /></IconBtn>
              </div>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between pt-2"><div className="text-[14px]">Zusatz netto: <strong>{fmtEur(summe)}</strong></div><div className="flex gap-2"><Btn variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={speichern} loading={busy}>Speichern</Btn></div></div>
      </div>
    </Sheet>
  );
}
