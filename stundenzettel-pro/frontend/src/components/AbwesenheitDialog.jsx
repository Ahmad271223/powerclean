import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { todayKey } from '../lib/dates';
import { Sheet, Btn, Chip, Field, TextInput, TextArea } from './ui';

export const ABWESENHEIT_ARTEN = [['urlaub', 'Urlaub'], ['krank', 'Krank'], ['feiertag', 'Feiertag'], ['unbezahlt', 'Unbezahlt'], ['sonstiges', 'Sonstiges']];
export const ABWESENHEIT_LABEL = Object.fromEntries(ABWESENHEIT_ARTEN);

/** Abwesenheit beantragen (Mitarbeiter) bzw. eintragen (Büro, direkt genehmigt). */
export default function AbwesenheitDialog({ open, onOpenChange, abwesenheit, mitarbeiter = [], userId = '', onSaved }) {
  const { isBuero } = useAuth();
  const [form, setForm] = useState({ user_id: '', type: 'urlaub', from_date: todayKey(), to_date: todayKey(), note: '' });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(abwesenheit ? { user_id: abwesenheit.user_id || '', type: abwesenheit.type, from_date: abwesenheit.from_date, to_date: abwesenheit.to_date, note: abwesenheit.note || '' }
      : { user_id: userId || '', type: 'urlaub', from_date: todayKey(), to_date: todayKey(), note: '' });
  }, [open, abwesenheit, userId]);

  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v, ...(k === 'from_date' && v > f.to_date ? { to_date: v } : {}) })); };

  const submit = async (e) => {
    e.preventDefault();
    if (isBuero && !form.user_id) { toast.error('Bitte einen Mitarbeiter wählen'); return; }
    setBusy(true);
    try {
      const body = { ...form, user_id: form.user_id || null };
      if (abwesenheit) await api.put(`/api/abwesenheiten/${abwesenheit.id}`, body); else await api.post('/api/abwesenheiten', body);
      toast.success(abwesenheit ? 'Gespeichert' : (isBuero ? 'Eingetragen' : 'Antrag gesendet'));
      onSaved?.();
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={abwesenheit ? 'Abwesenheit ändern' : (isBuero ? 'Abwesenheit eintragen' : 'Abwesenheit beantragen')}>
      <form onSubmit={submit} className="space-y-5">
        {isBuero && (
          <Field label="Mitarbeiter">
            <select value={form.user_id} onChange={set('user_id')} className="w-full h-11 rounded-xl bg-[#F5F5F7] px-3.5 text-[15px] outline-none" required>
              <option value="">– wählen –</option>
              {mitarbeiter.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </Field>
        )}
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Art</span>
          <div className="flex gap-2 flex-wrap">{ABWESENHEIT_ARTEN.map(([v, l]) => <Chip key={v} active={form.type === v} onClick={() => setForm((f) => ({ ...f, type: v }))}>{l}</Chip>)}</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Von"><TextInput type="date" value={form.from_date} onChange={set('from_date')} required /></Field>
          <Field label="Bis"><TextInput type="date" value={form.to_date} onChange={set('to_date')} min={form.from_date} required /></Field>
        </div>
        <Field label="Notiz (optional)"><TextArea rows={2} value={form.note} onChange={set('note')} /></Field>
        <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{abwesenheit ? 'Speichern' : (isBuero ? 'Eintragen' : 'Beantragen')}</Btn></div>
      </form>
    </Sheet>
  );
}
