import React, { useCallback, useEffect, useState } from 'react';
import { BellRing, CreditCard, FileDown, Settings2 } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Empty, Field, IconBtn, TextArea, TextInput } from '../components/ui';
import { MahnungDialog, STATUS_CLS, ZahlungDialog, fmtEur } from '../components/rechnungen/RechnungDialoge';
import { api, openFile } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate, fromKey } from '../lib/dates';

const REGELN = [['erinnerung_tage', 'Zahlungserinnerung: Tage nach Fälligkeit'], ['mahnung_tage', 'Mahnung: Tage nach der Erinnerung'], ['letzte_mahnung_tage', 'Letzte Mahnung: Tage nach der Mahnung'], ['gebuehr_mahnung', 'Gebühr Mahnung €'], ['gebuehr_letzte', 'Gebühr letzte Mahnung €']];
const TEXTE = [['text_erinnerung', 'Text Zahlungserinnerung'], ['text_mahnung', 'Text Mahnung'], ['text_letzte', 'Text letzte Mahnung']];

function Regeln({ regeln, onSaved }) {
  const { refresh } = useAuth();
  const [f, setF] = useState(regeln);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setF(regeln); }, [regeln]);
  const speichern = async () => {
    setBusy(true);
    try { await api.put('/api/firma', { mahnwesen: f }); await refresh(); toast.success('Mahnregeln gespeichert'); onSaved(); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Card className="p-5">
      <h2 className="text-[17px] mb-1 flex items-center gap-2"><Settings2 size={17} /> Fristen, Gebühren und Texte</h2>
      <p className="text-[13px] text-[#6E6E73] mb-3">Mahnungen werden nie automatisch verschickt – die Regeln bestimmen nur, wann die nächste Stufe vorgeschlagen wird. Gebühren nur, wenn sie vertraglich oder gesetzlich zulässig sind (Standard 0 €).</p>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">{REGELN.map(([k, l]) => <Field key={k} label={l}><TextInput type="number" inputMode="decimal" min="0" step={k.startsWith('gebuehr') ? '0.5' : '1'} value={f?.[k] ?? ''} onChange={(e) => setF((x) => ({ ...x, [k]: e.target.value }))} /></Field>)}</div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mt-3">{TEXTE.map(([k, l]) => <Field key={k} label={l}><TextArea rows={4} value={f?.[k] ?? ''} onChange={(e) => setF((x) => ({ ...x, [k]: e.target.value }))} /></Field>)}</div>
      <div className="flex justify-end mt-3"><Btn onClick={speichern} loading={busy}>Regeln speichern</Btn></div>
    </Card>
  );
}

/** Mahnwesen: überfällige, ausgestellte Rechnungen mit Mahnstand und nächstem Schritt – Zahlungserinnerung, Mahnung, letzte Mahnung, jeweils von Hand. */
export default function MahnwesenPage() {
  const [d, setD] = useState(null);
  const [mahnung, setMahnung] = useState(null);
  const [zahlung, setZahlung] = useState(null);
  const [regeln, setRegeln] = useState(false);
  const laden = useCallback(() => api.get('/api/mahnwesen').then(setD).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  return (
    <Layout title="Mahnwesen" subtitle="Überfällige Rechnungen mit Zahlungsstand, Mahnstufe und Vorschlag für den nächsten Schritt. Versand immer nach deiner Freigabe, jede E-Mail mit Nachweis."
      action={<Btn variant="soft" onClick={() => setRegeln((v) => !v)}><Settings2 size={16} /> Regeln</Btn>} wide>
      {!d ? <Ladeanzeige /> : (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Überfällig (brutto offen)</div><div className={`text-[20px] font-semibold ${d.offen_brutto > 0 ? 'text-[#C41E3A]' : ''}`}>{fmtEur(d.offen_brutto)}</div><div className="text-[12px] text-[#6E6E73]">{d.rechnungen.length} Rechnungen</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Jetzt fällig</div><div className="text-[20px] font-semibold">{d.jetzt_faellig}</div><div className="text-[12px] text-[#6E6E73]">nächster Schritt möglich</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Fristen</div><div className="text-[14px] font-semibold mt-1">{d.regeln.erinnerung_tage} / {d.regeln.mahnung_tage} / {d.regeln.letzte_mahnung_tage} Tage</div><div className="text-[12px] text-[#6E6E73]">Erinnerung / Mahnung / letzte</div></Card>
          </div>
          {regeln && <Regeln regeln={d.regeln} onSaved={laden} />}
          {d.rechnungen.length === 0 ? <Card><Empty icon={BellRing} title="Nichts überfällig" text="Sobald eine ausgestellte Rechnung über die Fälligkeit hinaus offen ist, erscheint sie hier." /></Card> : (
            <Card className="overflow-x-auto">
              <table className="w-full text-[13px] min-w-[860px]">
                <thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="px-4 py-2">Rechnung</th><th className="py-2 pr-2">Kunde / Projekt</th><th className="py-2 pr-2">Fällig</th><th className="py-2 pr-2 text-right">Offen</th><th className="py-2 pr-2">Stand</th><th className="py-2 pr-2">Nächster Schritt</th><th className="py-2 pr-4" /></tr></thead>
                <tbody>
                  {d.rechnungen.map((r) => (
                    <tr key={r.id} className="border-t border-black/[0.06] align-middle">
                      <td className="px-4 py-2"><div className="font-semibold">{r.number}</div><div className="text-[11px] text-[#6E6E73]">{r.art_name} · {r.invoice_date ? fmtDate(fromKey(r.invoice_date)) : ''}</div></td>
                      <td className="py-2 pr-2"><div>{r.kunde_name || '–'}</div><div className="text-[11px] text-[#6E6E73]">{r.projekt_name}{r.kunde_email ? ` · ${r.kunde_email}` : ' · keine E-Mail'}</div></td>
                      <td className="py-2 pr-2"><div>{r.faellig_am ? fmtDate(fromKey(r.faellig_am)) : '–'}</div><div className="text-[11px] text-[#C41E3A] font-semibold">{r.tage_ueberfaellig} Tage überfällig</div></td>
                      <td className="py-2 pr-2 text-right"><div className="font-semibold">{fmtEur(r.offen_betrag)}</div><div className="text-[11px] text-[#6E6E73]">von {fmtEur(r.gross)}</div></td>
                      <td className="py-2 pr-2"><span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[r.status] || ''}`}>{r.status_name}</span>{r.mahnstufe > 0 && <div className="text-[11px] text-[#6E6E73] mt-1">{d.stufen[r.mahnstufe]} am {r.letzte_mahnung_am ? fmtDate(fromKey(r.letzte_mahnung_am)) : ''}</div>}</td>
                      <td className="py-2 pr-2">{r.naechste_stufe ? <div><div className={r.jetzt_faellig ? 'font-semibold' : 'text-[#6E6E73]'}>{r.naechste_name}</div>{!r.jetzt_faellig && r.faellig_ab && <div className="text-[11px] text-[#6E6E73]">ab {fmtDate(fromKey(r.faellig_ab))}</div>}</div> : <span className="text-[#6E6E73]">alle Stufen durch</span>}</td>
                      <td className="py-2 pr-4"><div className="flex items-center justify-end gap-1">
                        {(r.mahnungen || []).map((m) => <IconBtn key={m.stufe} size={30} variant="soft" onClick={() => openFile(`/api/rechnungen/${r.id}/mahnung/${m.stufe}.pdf`).catch((e) => toast.error(e.message))} title={`${m.name} vom ${fmtDate(fromKey(m.am))} (PDF)`}><FileDown size={14} /></IconBtn>)}
                        <IconBtn size={30} variant="soft" onClick={() => setZahlung(r)} title="Zahlung erfassen"><CreditCard size={14} /></IconBtn>
                        {r.naechste_stufe && <Btn size="sm" variant={r.jetzt_faellig ? 'primary' : 'soft'} onClick={() => setMahnung(r)}><BellRing size={14} /> {r.naechste_name}</Btn>}
                      </div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}
      <MahnungDialog eintrag={mahnung} regeln={d?.regeln} onOpenChange={(o) => { if (!o) setMahnung(null); }} onSaved={laden} />
      <ZahlungDialog rechnung={zahlung} onOpenChange={(o) => { if (!o) setZahlung(null); }} onSaved={laden} />
    </Layout>
  );
}
