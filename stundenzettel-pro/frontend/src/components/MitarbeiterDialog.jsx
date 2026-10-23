import React, { useState } from 'react';
import { Copy, Share2, UserPlus, Check } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Sheet, Btn, Chip, Field, TextInput } from './ui';

export const ROLLEN = [
  ['mitarbeiter', 'Mitarbeiter', 'Stempeluhr, eigene Zeiten, zugewiesene Projekte'],
  ['vorarbeiter', 'Vorarbeiter', 'Wie Mitarbeiter, dazu auf seinen Projekten: alle Zeiten sehen, für Kollegen eintragen, Serien und Checklisten anlegen'],
  ['buero', 'Büro', 'Alles außer Lizenz, API-Schlüssel und Webhooks'],
  ['inhaber', 'Inhaber', 'Alle Rechte'],
];

/** Mitarbeiter einladen: Konto wird angelegt, der Einladungslink per WhatsApp/E-Mail weitergegeben. */
export default function MitarbeiterDialog({ open, onOpenChange, onSaved }) {
  const { isInhaber } = useAuth();
  const [form, setForm] = useState({ name: '', email: '', role: 'mitarbeiter', personalnummer: '', phone: '' });
  const [link, setLink] = useState('');
  const [busy, setBusy] = useState(false);
  const [kopiert, setKopiert] = useState(false);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post('/api/mitarbeiter', { ...form, name: form.name.trim(), email: form.email.trim() });
      setLink(r.einladung_link);
      onSaved?.(r.mitarbeiter);
      toast.success('Konto angelegt – jetzt den Link weitergeben');
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  const kopieren = async () => { try { await navigator.clipboard.writeText(link); setKopiert(true); setTimeout(() => setKopiert(false), 2000); } catch { toast.error('Kopieren nicht möglich'); } };
  const teilen = () => navigator.share?.({ title: 'Einladung Stundenzettel Pro', text: `Hallo ${form.name}, hier dein Zugang zur Zeiterfassung: ${link}` }).catch(() => {});
  const schliessen = (o) => { if (!o) { setLink(''); setForm({ name: '', email: '', role: 'mitarbeiter', personalnummer: '', phone: '' }); } onOpenChange(o); };

  return (
    <Sheet open={open} onOpenChange={schliessen} title="Mitarbeiter einladen" subtitle="Der Mitarbeiter öffnet den Link, vergibt ein Passwort und kann sofort stempeln.">
      {!link ? (
        <form onSubmit={submit} className="space-y-5">
          <Field label="Name"><TextInput value={form.name} onChange={set('name')} required placeholder="Vor- und Nachname" /></Field>
          <Field label="E-Mail (Anmeldename)"><TextInput type="email" value={form.email} onChange={set('email')} required placeholder="name@beispiel.de" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Personalnummer (optional)"><TextInput value={form.personalnummer} onChange={set('personalnummer')} /></Field>
            <Field label="Telefon (optional)"><TextInput type="tel" value={form.phone} onChange={set('phone')} /></Field>
          </div>
          <div>
            <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Rolle</span>
            <div className="flex gap-2 flex-wrap">{ROLLEN.filter(([v]) => v !== 'inhaber' || isInhaber).map(([v, l]) => <Chip key={v} active={form.role === v} onClick={() => setForm((f) => ({ ...f, role: v }))}>{l}</Chip>)}</div>
            <span className="block text-[12px] text-[#86868B] mt-1.5">{ROLLEN.find(([v]) => v === form.role)?.[2]}</span>
          </div>
          <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => schliessen(false)}>Abbrechen</Btn><Btn type="submit" loading={busy}><UserPlus size={16} /> Einladen</Btn></div>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[14px] break-all select-all">{link}</div>
          <p className="text-[13px] text-[#6E6E73]">Der Link gilt 14 Tage. Unter „Mitarbeiter“ kannst du jederzeit einen neuen Link erzeugen.</p>
          <div className="flex flex-wrap gap-2">
            <Btn onClick={kopieren}>{kopiert ? <Check size={16} /> : <Copy size={16} />} {kopiert ? 'Kopiert' : 'Link kopieren'}</Btn>
            {navigator.share && <Btn variant="soft" onClick={teilen}><Share2 size={16} /> Per WhatsApp / E-Mail</Btn>}
            <Btn variant="ghost" onClick={() => schliessen(false)}>Fertig</Btn>
          </div>
        </div>
      )}
    </Sheet>
  );
}
