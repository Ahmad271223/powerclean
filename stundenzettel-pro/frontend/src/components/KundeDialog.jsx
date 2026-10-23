import React, { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { Sheet, Btn, Field, TextInput, TextArea, Toggle } from './ui';

const EMPTY = { name: '', contact: '', street: '', zip_code: '', city: '', email: '', phone: '', notes: '', reverse_charge: false };

export default function KundeDialog({ open, onOpenChange, kunde, onSaved, onDeleted }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setForm(kunde ? { ...EMPTY, ...kunde } : EMPTY); }, [open, kunde]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Bitte den Kundennamen eingeben'); return; }
    const data = Object.fromEntries(Object.keys(EMPTY).map((k) => [k, form[k]]));
    setBusy(true);
    try {
      const r = kunde ? await api.put(`/api/kunden/${kunde.id}`, data) : await api.post('/api/kunden', data);
      toast.success(kunde ? 'Kunde gespeichert' : 'Kunde angelegt');
      onSaved?.(r.kunde);
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const remove = async () => {
    if (!kunde || !window.confirm(`Kunde "${kunde.name}" löschen?`)) return;
    try { await api.del(`/api/kunden/${kunde.id}`); toast.success('Kunde gelöscht'); onOpenChange(false); onDeleted?.(kunde); }
    catch (err) { toast.error(err.message); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={kunde ? 'Kunde bearbeiten' : 'Neuer Kunde'} subtitle="Name und Adresse erscheinen auf Rechnungen und Stundenzetteln.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Firma / Name"><TextInput value={form.name} onChange={set('name')} required placeholder="z. B. Gebäudeservice Müller GmbH" /></Field>
        <Field label="Ansprechpartner"><TextInput value={form.contact} onChange={set('contact')} /></Field>
        <Field label="Straße und Hausnummer"><TextInput value={form.street} onChange={set('street')} /></Field>
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <Field label="PLZ"><TextInput value={form.zip_code} onChange={set('zip_code')} inputMode="numeric" /></Field>
          <Field label="Ort"><TextInput value={form.city} onChange={set('city')} /></Field>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="E-Mail"><TextInput type="email" value={form.email} onChange={set('email')} /></Field>
          <Field label="Telefon"><TextInput type="tel" value={form.phone} onChange={set('phone')} /></Field>
        </div>
        <div className="rounded-2xl bg-[#F5F5F7] px-4">
          <Toggle checked={!!form.reverse_charge} onChange={(v) => setForm((f) => ({ ...f, reverse_charge: v }))} label="Rechnungen ohne Umsatzsteuer (§ 13b UStG)" hint="Der Kunde erbringt selbst Gebäudereinigungsleistungen (Subunternehmer-Verhältnis)." />
        </div>
        <Field label="Notizen"><TextArea rows={2} value={form.notes} onChange={set('notes')} /></Field>
        <div className="flex items-center justify-between gap-3 pt-1">
          {kunde ? <Btn type="button" variant="danger" size="sm" onClick={remove}><Trash2 size={15} /> Löschen</Btn> : <span />}
          <div className="flex gap-2"><Btn type="button" variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn type="submit" loading={busy}>Speichern</Btn></div>
        </div>
      </form>
    </Sheet>
  );
}
