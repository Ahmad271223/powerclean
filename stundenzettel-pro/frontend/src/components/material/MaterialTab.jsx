import React, { useCallback, useEffect, useState } from 'react';
import { Check, Package, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, Field, IconBtn, Select, TextArea, TextInput } from '../ui';
import { useDialoge } from '../Dialoge';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { fmtGeld, fmtMenge } from '../../lib/angebot';
import { fmtDate, fromKey, todayKey } from '../../lib/dates';

/** Projekt → Material: Mitarbeiter buchen verbrauchtes Material (Artikel aus dem Stamm oder frei), ohne Preise zu sehen;
 *  das Büro sieht Kosten (mit Recht „Kostensätze“) und prüft die Buchungen – erst geprüfte zählen in der Nachkalkulation. */
export default function MaterialTab({ projekt }) {
  const { user, isBuero, kann } = useAuth();
  const { fragen, bestaetigen } = useDialoge();
  const [d, setD] = useState(null);
  const [artikel, setArtikel] = useState([]);
  const [f, setF] = useState({ artikel_id: '', bezeichnung: '', menge: '', einheit: '', date: todayKey(), note: '' });
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/projekte/${projekt.id}/material`).then(setD).catch((err) => toast.error(err.message)), [projekt.id]);
  useEffect(() => { laden(); api.get('/api/artikel/auswahl').then((r) => setArtikel(r.artikel)).catch(() => {}); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const artikelGewaehlt = (e) => { const a = artikel.find((x) => x.id === e.target.value); setF((x) => ({ ...x, artikel_id: e.target.value, einheit: a?.einheit || x.einheit, bezeichnung: a ? '' : x.bezeichnung })); };
  const buchen = async () => {
    if (!f.artikel_id && !f.bezeichnung.trim()) { toast.error('Artikel wählen oder Material benennen'); return; }
    if (!(Number(f.menge) > 0)) { toast.error('Menge angeben'); return; }
    setBusy('buchen');
    try {
      await api.post(`/api/projekte/${projekt.id}/material`, { artikel_id: f.artikel_id || null, bezeichnung: f.bezeichnung, menge: Number(f.menge), einheit: f.einheit, date: f.date, note: f.note });
      toast.success('Material gebucht');
      setF((x) => ({ ...x, artikel_id: '', bezeichnung: '', menge: '', note: '' }));
      laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const pruefen = async (m) => {
    setBusy(m.id);
    try {
      await api.post(`/api/material/${m.id}/pruefen`, {});
      toast.success('Buchung geprüft');
      laden();
    } catch (err) {
      if (err.status === 400 && kann('kostensaetze')) {
        const ek = await fragen({ titel: 'Einkaufspreis fehlt', text: `Einkaufspreis je ${m.einheit} für „${m.bezeichnung}“ (netto, €):`, pflicht: true });
        if (ek) { try { await api.post(`/api/material/${m.id}/pruefen`, { einkaufspreis: Number(String(ek).replace(',', '.')) }); toast.success('Buchung geprüft'); laden(); } catch (e2) { toast.error(e2.message); } }
      } else toast.error(err.message);
    } finally { setBusy(''); }
  };
  const loeschen = async (m) => {
    if (!(await bestaetigen({ titel: 'Buchung löschen?', text: `${fmtMenge(m.menge)} ${m.einheit} ${m.bezeichnung}`, gefaehrlich: true }))) return;
    try { await api.del(`/api/material/${m.id}`); toast.success('Gelöscht'); laden(); } catch (err) { toast.error(err.message); }
  };
  const liste = d?.material || [];
  return (
    <div className="space-y-5">
      <Card className="p-5">
        <h2 className="text-[17px] mb-1 flex items-center gap-2"><Package size={17} /> Material verbraucht</h2>
        <p className="text-[13px] text-[#6E6E73] mb-3">Was auf dieser Baustelle verbraucht wurde – Artikel aus dem Stamm oder frei benannt. Lieferungen und Lagereingänge sind davon getrennt.</p>
        <div className="grid grid-cols-2 sm:grid-cols-[1fr_1fr_90px_90px_140px] gap-2 items-end">
          <Field label="Artikel" className="col-span-2 sm:col-span-1"><Select value={f.artikel_id} onChange={artikelGewaehlt}><option value="">Frei benennen …</option>{artikel.map((a) => <option key={a.id} value={a.id}>{a.nummer ? `${a.nummer} · ` : ''}{a.name}</option>)}</Select></Field>
          <Field label="Material (frei)" className="col-span-2 sm:col-span-1"><TextInput value={f.bezeichnung} onChange={set('bezeichnung')} placeholder="z. B. Müllsäcke 120 l" disabled={!!f.artikel_id} /></Field>
          <Field label="Menge"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.menge} onChange={set('menge')} /></Field>
          <Field label="Einheit"><TextInput value={f.einheit} onChange={set('einheit')} placeholder="Stk." /></Field>
          <Field label="Datum"><TextInput type="date" value={f.date} onChange={set('date')} /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2 items-end mt-2">
          <Field label="Notiz (optional)"><TextArea rows={1} value={f.note} onChange={set('note')} placeholder="z. B. für die Glasflächen im EG" /></Field>
          <Btn onClick={buchen} loading={busy === 'buchen'}><Plus size={16} /> Buchen</Btn>
        </div>
      </Card>
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 className="text-[17px]">Buchungen{isBuero ? '' : ' (nur deine eigenen)'}</h2>
          {d?.preise_sichtbar && <div className="text-[13px] text-[#6E6E73]">Materialkosten (EK): <span className="font-semibold text-[#1D1D1F]">{fmtGeld(d.kosten_summe)}</span>{d.ungeprueft ? ` · ${d.ungeprueft} ungeprüft` : ''}</div>}
          {isBuero && !d?.preise_sichtbar && d?.ungeprueft > 0 && <div className="text-[13px] text-[#6E6E73]">{d.ungeprueft} ungeprüft</div>}
        </div>
        {!d ? <p className="text-[14px] text-[#6E6E73]">Lädt …</p> : liste.length === 0 ? <Empty icon={Package} title="Noch kein Material gebucht" text="Buchungen erscheinen hier mit Datum, Menge und Status." /> : (
          <ul className="divide-y divide-black/[0.06]">
            {liste.map((m) => (
              <li key={m.id} className="py-2.5 flex items-center gap-3 text-[14px]">
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{fmtMenge(m.menge)} {m.einheit} · {m.bezeichnung}{m.artikel_nummer ? <span className="text-[#6E6E73] font-normal"> ({m.artikel_nummer})</span> : null}</div>
                  <div className="text-[12px] text-[#6E6E73] truncate">{m.date ? fmtDate(fromKey(m.date)) : ''}{isBuero ? ` · ${m.user_name}` : ''}{m.note ? ` · ${m.note}` : ''}{m.status === 'geprueft' ? ` · geprüft von ${m.geprueft_von}` : ''}</div>
                </div>
                {d.preise_sichtbar && <div className="text-right"><div className="font-semibold">{m.kosten === null || m.kosten === undefined ? <span className="text-[#B25E00]">ohne EK</span> : fmtGeld(m.kosten)}</div>{m.einkaufspreis !== null && m.einkaufspreis !== undefined && <div className="text-[11px] text-[#6E6E73]">{fmtGeld(m.einkaufspreis)}/{m.einheit}</div>}</div>}
                <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${m.status === 'geprueft' ? 'bg-[#E8F8EC] text-[#1B7F3B]' : 'bg-[#FFF4E5] text-[#B25E00]'}`}>{m.status === 'geprueft' ? 'geprüft' : 'erfasst'}</span>
                {isBuero && kann('kalkulation') && m.status !== 'geprueft' && <Btn size="sm" variant="soft" onClick={() => pruefen(m)} loading={busy === m.id}><Check size={14} /> Prüfen</Btn>}
                {(isBuero || (m.user_id === user?.id && m.status !== 'geprueft')) && <IconBtn onClick={() => loeschen(m)} title="Löschen" className="text-[#C41E3A]"><Trash2 size={16} /></IconBtn>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
