import React, { useEffect, useState } from 'react';
import { Repeat, Users, Tag } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { calcNetMinutes, fmtHours, WEEKDAYS_DE, toKey, monthLastDay } from '../lib/dates';
import { Sheet, Btn, Chip, Field, TextInput, TextArea, Toggle } from './ui';

const PAUSES = [0, 15, 30, 45, 60];

/** Serien-Einträge: gleiche Zeit an festen Wochentagen, z. B. Mo–Fr 06:00–09:00 für den ganzen Monat (Feiertage werden übersprungen). */
export default function SerieDialog({ open, onOpenChange, projectId, year, month0, mitarbeiter = [], leistungen = [], defaultWorkers = 1, onDone }) {
  const [form, setForm] = useState({ from_date: '', to_date: '', weekdays: [0, 1, 2, 3, 4], start_time: '06:00', end_time: '09:00', pause_minutes: 0, activity: '', user_id: '', workers: defaultWorkers, service_id: '', skip_holidays: true });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setForm((f) => ({ ...f, from_date: toKey(new Date(year, month0, 1)), to_date: toKey(monthLastDay(year, month0)), workers: defaultWorkers }));
  }, [open, year, month0, defaultWorkers]);

  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const toggleDay = (i) => setForm((f) => ({ ...f, weekdays: f.weekdays.includes(i) ? f.weekdays.filter((d) => d !== i) : [...f.weekdays, i].sort() }));
  const net = calcNetMinutes(form.start_time, form.end_time, form.pause_minutes);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.weekdays.length) { toast.error('Bitte mindestens einen Wochentag wählen'); return; }
    if (net <= 0) { toast.error('Die Netto-Arbeitszeit muss größer als 0 sein'); return; }
    setBusy(true);
    try {
      const r = await api.post('/api/zeiten/serie', { project_id: projectId, from_date: form.from_date, to_date: form.to_date, weekdays: form.weekdays, start_time: form.start_time, end_time: form.end_time, pause_minutes: Number(form.pause_minutes) || 0, activity: form.activity, user_id: form.user_id || null, workers: form.user_id ? 1 : Math.max(1, parseInt(form.workers, 10) || 1), service_id: form.service_id || null, skip_holidays: form.skip_holidays });
      toast.success(r.angelegt ? `${r.angelegt} Einträge angelegt` : 'Nichts angelegt – an diesen Tagen gab es schon Einträge mit dieser Startzeit');
      onDone?.();
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Zeiten als Serie eintragen" subtitle="Feste Einsatzzeiten für einen Zeitraum auf einmal, z. B. Mo–Fr 06:00–09:00.">
      <form onSubmit={submit} className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Von"><TextInput type="date" value={form.from_date} onChange={set('from_date')} required /></Field>
          <Field label="Bis"><TextInput type="date" value={form.to_date} onChange={set('to_date')} required /></Field>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Wochentage</span>
          <div className="flex gap-2 flex-wrap">{WEEKDAYS_DE.map((d, i) => <Chip key={d} active={form.weekdays.includes(i)} onClick={() => toggleDay(i)}>{d}</Chip>)}</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Anfang"><TextInput type="time" value={form.start_time} onChange={set('start_time')} required /></Field>
          <Field label="Arbeitsende"><TextInput type="time" value={form.end_time} onChange={set('end_time')} required /></Field>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Pause</span>
          <div className="flex gap-2 flex-wrap">{PAUSES.map((p) => <Chip key={p} active={Number(form.pause_minutes) === p} onClick={() => setForm((f) => ({ ...f, pause_minutes: p }))}>{p === 0 ? 'Keine' : `${p} Min.`}</Chip>)}</div>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-2 flex items-center gap-1.5"><Users size={14} /> Person</span>
          <div className="flex gap-2 overflow-x-auto -mx-6 px-6 pb-1 no-scrollbar">
            <Chip active={!form.user_id} onClick={() => setForm((f) => ({ ...f, user_id: '' }))}>Anzahl ohne Namen</Chip>
            {mitarbeiter.map((m) => <Chip key={m.id} active={form.user_id === m.id} onClick={() => setForm((f) => ({ ...f, user_id: m.id }))}>{m.name}</Chip>)}
          </div>
          {!form.user_id && <div className="mt-2 flex items-center gap-2 text-[13px] text-[#6E6E73]">Mitarbeiter je Tag <TextInput type="number" min="1" max="99" value={form.workers} onChange={set('workers')} className="w-20 h-9 text-center" /></div>}
        </div>
        {leistungen.length > 0 && (
          <div>
            <span className="block text-[13px] font-medium text-[#6E6E73] mb-2 flex items-center gap-1.5"><Tag size={14} /> Leistung</span>
            <div className="flex gap-2 overflow-x-auto -mx-6 px-6 pb-1 no-scrollbar">
              <Chip active={!form.service_id} onClick={() => setForm((f) => ({ ...f, service_id: '' }))}>Keine</Chip>
              {leistungen.map((l) => <Chip key={l.id} active={form.service_id === l.id} onClick={() => setForm((f) => ({ ...f, service_id: l.id }))}>{l.name}</Chip>)}
            </div>
          </div>
        )}
        <Field label="Tätigkeit"><TextArea rows={2} value={form.activity} onChange={set('activity')} placeholder="z. B. Unterhaltsreinigung" /></Field>
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={form.skip_holidays} onChange={(v) => setForm((f) => ({ ...f, skip_holidays: v }))} label="Feiertage überspringen" hint="Gesetzliche Feiertage des Bundeslands der Firma" /></div>
        <div className="flex items-center justify-between gap-3 pt-1">
          <div className="text-[13px] text-[#6E6E73]">Je Tag <strong className="text-[#1D1D1F]">{fmtHours(net)}</strong>{!form.user_id && Number(form.workers) > 1 ? ` × ${form.workers}` : ''}</div>
          <Btn type="submit" loading={busy}><Repeat size={16} /> Serie anlegen</Btn>
        </div>
      </form>
    </Sheet>
  );
}
