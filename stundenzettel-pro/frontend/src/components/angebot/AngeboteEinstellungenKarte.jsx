import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Btn, Card, Field, TextArea, TextInput } from '../ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';

const FELDER = ['angebot_prefix', 'angebot_gueltig_tage', 'angebot_einleitung', 'angebot_zahlungsbedingungen', 'angebot_schluss'];
const KALK = [['stundensatz', 'Interner Stundensatz (Lohnkosten je Stunde)', '€/Std.'], ['gemeinkosten_prozent', 'Gemeinkostenzuschlag', '%'], ['risiko_prozent', 'Risikozuschlag', '%'], ['gewinn_prozent', 'Gewinnzuschlag', '%']];

/** Firma → Angebote: Nummernkreis, Gültigkeit und Standardtexte der Kundenangebote; Kalkulationssätze nur mit Recht „kostensaetze“. */
export default function AngeboteEinstellungenKarte() {
  const { firma, kann, refresh } = useAuth();
  const [form, setForm] = useState({});
  const [kalk, setKalk] = useState({});
  const [busy, setBusy] = useState('');
  useEffect(() => {
    if (!firma) return;
    setForm(Object.fromEntries(FELDER.map((f) => [f, firma[f] ?? ''])));
    setKalk({ stundensatz: '', gemeinkosten_prozent: '', risiko_prozent: '', gewinn_prozent: '', ...(firma.kalkulation || {}) });
  }, [firma]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const speichern = async () => {
    setBusy('texte');
    try {
      await api.put('/api/firma', { ...form, angebot_gueltig_tage: Number(form.angebot_gueltig_tage) || 30 });
      await refresh();
      toast.success('Angebotseinstellungen gespeichert');
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const kalkSpeichern = async () => {
    setBusy('kalk');
    try {
      await api.put('/api/firma', { kalkulation: Object.fromEntries(Object.entries(kalk).filter(([, v]) => v !== '' && v !== null).map(([k, v]) => [k, Number(v)])) });
      await refresh();
      toast.success('Kalkulationssätze gespeichert');
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  return (
    <>
      <Card className="p-5 sm:p-8">
        <h2 className="text-[17px]">Angebote an Kunden</h2>
        <p className="text-[14px] text-[#6E6E73] mt-1 mb-4">Nummernkreis, Gültigkeit und Standardtexte für neue Angebote. Die Texte lassen sich in jedem Angebot anpassen.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Nummernpräfix" hint="z. B. AN- ergibt AN-2026-0001"><TextInput value={form.angebot_prefix || ''} onChange={set('angebot_prefix')} maxLength={20} /></Field>
          <Field label="Gültigkeit in Tagen"><TextInput type="number" min="1" max="365" value={form.angebot_gueltig_tage ?? ''} onChange={set('angebot_gueltig_tage')} /></Field>
        </div>
        <Field label="Einleitung" className="mt-3"><TextArea rows={2} value={form.angebot_einleitung || ''} onChange={set('angebot_einleitung')} /></Field>
        <Field label="Zahlungsbedingungen" className="mt-3"><TextArea rows={2} value={form.angebot_zahlungsbedingungen || ''} onChange={set('angebot_zahlungsbedingungen')} /></Field>
        <Field label="Schlusstext" className="mt-3"><TextArea rows={2} value={form.angebot_schluss || ''} onChange={set('angebot_schluss')} /></Field>
        <div className="mt-4 flex justify-end"><Btn onClick={speichern} loading={busy === 'texte'}>Speichern</Btn></div>
      </Card>
      {kann('kostensaetze') && (
        <Card className="p-5 sm:p-8">
          <h2 className="text-[17px]">Kalkulationssätze <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FDE8E8] text-[#C41E3A] align-middle">vertraulich</span></h2>
          <p className="text-[14px] text-[#6E6E73] mt-1 mb-4">Standardwerte für die interne Kalkulation der Angebote. Der Stundensatz sind eure Kosten je Arbeitsstunde (Lohn plus Nebenkosten), nicht der Preis für den Kunden. Sichtbar nur mit dem Recht „Kostensätze“.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {KALK.map(([k, l, e]) => <Field key={k} label={l} hint={e}><TextInput type="number" inputMode="decimal" step="0.1" min="0" value={kalk[k] ?? ''} onChange={(ev) => setKalk((x) => ({ ...x, [k]: ev.target.value }))} /></Field>)}
          </div>
          <div className="mt-4 flex justify-end"><Btn onClick={kalkSpeichern} loading={busy === 'kalk'}>Kalkulationssätze speichern</Btn></div>
        </Card>
      )}
    </>
  );
}
