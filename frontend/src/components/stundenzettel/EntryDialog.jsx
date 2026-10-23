import React, { useEffect, useState } from 'react';
import { Pencil, Trash2, FileText, Plus, X, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { api, calcNetMinutes, fmtHours, fmtDate, fromKey, isoWeek, WEEKDAYS_LONG_DE } from '@/lib/ts';
import { Sheet, Btn, Chip, TextArea, IconBtn } from './ui';

const PAUSES = [0, 15, 30, 45, 60];
const PRESETS = [['07:00', '15:00'], ['08:00', '16:00'], ['08:00', '17:00'], ['06:00', '14:00']];

const emptyForm = (last) => ({
  start_time: last?.start_time || '08:00',
  end_time: last?.end_time || '16:00',
  pause_minutes: last?.pause_minutes ?? 0,
  activity: last?.activity || '',
});

/**
 * Day sheet: all entries of one day plus a quick form (presets, pause chips, recent activities).
 * Every saved entry is immediately part of the weekly Stundenzettel PDF.
 */
export default function EntryDialog({ open, onOpenChange, projectId, dateKey, entries, lastEntry, recentActivities = [], onChanged, onWeekPdf }) {
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm(null));
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    if (open) {
      setEditing(null);
      setForm(emptyForm(lastEntry));
      setShowForm(entries.length === 0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, dateKey]);

  if (!dateKey) return null;
  const date = fromKey(dateKey);
  const { week } = isoWeek(date);
  const net = calcNetMinutes(form.start_time, form.end_time, form.pause_minutes);
  const dayTotal = entries.reduce((s, e) => s + (e.net_minutes || 0), 0);
  const set = (key) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [key]: v })); };

  const startEdit = (entry) => {
    setEditing(entry.id);
    setForm({ start_time: entry.start_time, end_time: entry.end_time, pause_minutes: entry.pause_minutes || 0, activity: entry.activity || '' });
    setShowForm(true);
  };

  const cancelEdit = () => {
    setEditing(null);
    setForm(emptyForm(lastEntry));
    setShowForm(entries.length === 0);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.start_time || !form.end_time) { toast.error('Bitte Anfang und Arbeitsende eingeben'); return; }
    if (net <= 0) { toast.error('Die Netto-Arbeitszeit muss größer als 0 sein'); return; }
    setBusy(true);
    try {
      const payload = { date: dateKey, activity: form.activity.trim(), start_time: form.start_time, end_time: form.end_time, pause_minutes: Number(form.pause_minutes) || 0 };
      if (editing) {
        await api.patch(`/ts/entries/${editing}`, payload);
      } else {
        await api.post('/ts/entries', { ...payload, project_id: projectId });
      }
      toast.success(editing ? 'Gespeichert' : 'Eingetragen');
      await onChanged();
      setEditing(null);
      setForm(emptyForm({ ...payload }));
      setShowForm(false);
    } catch (error) {
      console.error(error);
      toast.error(error.response?.data?.detail || 'Fehler beim Speichern');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (entry) => {
    if (!window.confirm('Eintrag wirklich löschen?')) return;
    try {
      await api.delete(`/ts/entries/${entry.id}`);
      toast.success('Gelöscht');
      await onChanged();
      if (editing === entry.id) cancelEdit();
    } catch (error) {
      console.error(error);
      toast.error('Fehler beim Löschen');
    }
  };

  const isPreset = (s, e) => form.start_time === s && form.end_time === e;

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={`${WEEKDAYS_LONG_DE[(date.getDay() + 6) % 7]}, ${fmtDate(date)}`}
      subtitle={`KW ${week} · Tagessumme ${fmtHours(dayTotal)}`}
    >
      <div className="space-y-5" data-testid="entry-dialog">
        {entries.length > 0 && (
          <ul className="rounded-2xl bg-[#F5F5F7] divide-y divide-black/[0.06] overflow-hidden" data-testid="entry-list">
            {entries.map((entry) => (
              <li key={entry.id} className={`flex items-center gap-3 px-4 py-3 ${editing === entry.id ? 'bg-[#C41E3A]/5' : ''}`}>
                <span className="w-10 h-10 rounded-xl bg-white shadow-card flex items-center justify-center text-[#C41E3A]"><Clock size={18} /></span>
                <div className="flex-1 min-w-0">
                  <div className="text-[15px] font-semibold">
                    {entry.start_time} – {entry.end_time}
                    <span className="ml-2 text-[#C41E3A]">{fmtHours(entry.net_minutes || 0)}</span>
                    {entry.pause_minutes > 0 && <span className="ml-2 text-[12px] font-normal text-[#86868B]">Pause {entry.pause_minutes} Min.</span>}
                  </div>
                  <div className="text-[13px] text-[#6E6E73] truncate">{entry.activity || <em>keine Tätigkeit</em>}</div>
                </div>
                <IconBtn size={32} onClick={() => startEdit(entry)} title="Bearbeiten"><Pencil size={15} /></IconBtn>
                <IconBtn size={32} variant="danger" onClick={() => remove(entry)} title="Löschen"><Trash2 size={15} /></IconBtn>
              </li>
            ))}
          </ul>
        )}

        {!showForm ? (
          <div className="flex flex-wrap gap-2">
            <Btn size="lg" className="flex-1 min-w-[220px]" onClick={() => { setEditing(null); setForm(emptyForm(lastEntry)); setShowForm(true); }} data-testid="entry-add">
              <Plus size={18} /> Arbeitszeit eintragen
            </Btn>
            <Btn size="lg" variant="soft" className="flex-1 min-w-[220px]" onClick={onWeekPdf}><FileText size={18} /> Stundenzettel KW {week}</Btn>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-5" data-testid="entry-form">
            <div className="flex items-center justify-between">
              <h3 className="text-[15px] font-semibold">{editing ? 'Eintrag bearbeiten' : 'Arbeitszeit eintragen'}</h3>
              {entries.length > 0 && <IconBtn size={30} onClick={cancelEdit} title="Abbrechen"><X size={16} /></IconBtn>}
            </div>

            {/* quick presets */}
            <div className="flex gap-2 overflow-x-auto -mx-6 px-6 pb-1 no-scrollbar">
              {lastEntry && (
                <Chip active={isPreset(lastEntry.start_time, lastEntry.end_time) && Number(form.pause_minutes) === (lastEntry.pause_minutes || 0)} onClick={() => setForm({ ...form, start_time: lastEntry.start_time, end_time: lastEntry.end_time, pause_minutes: lastEntry.pause_minutes || 0 })}>
                  Wie zuletzt · {lastEntry.start_time}–{lastEntry.end_time}
                </Chip>
              )}
              {PRESETS.map(([s, e]) => (
                <Chip key={s + e} active={isPreset(s, e)} onClick={() => setForm((f) => ({ ...f, start_time: s, end_time: e }))}>{s}–{e}</Chip>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label className="block rounded-2xl bg-[#F5F5F7] px-4 py-3">
                <span className="block text-[12px] font-medium text-[#6E6E73]">Anfang</span>
                <input type="time" value={form.start_time} onChange={set('start_time')} required className="mt-0.5 w-full bg-transparent text-[26px] font-semibold tracking-tight outline-none" data-testid="entry-start" />
              </label>
              <label className="block rounded-2xl bg-[#F5F5F7] px-4 py-3">
                <span className="block text-[12px] font-medium text-[#6E6E73]">Arbeitsende</span>
                <input type="time" value={form.end_time} onChange={set('end_time')} required className="mt-0.5 w-full bg-transparent text-[26px] font-semibold tracking-tight outline-none" data-testid="entry-end" />
              </label>
            </div>

            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Pause</span>
              <div className="flex gap-2 flex-wrap">
                {PAUSES.map((p) => (
                  <Chip key={p} active={Number(form.pause_minutes) === p} onClick={() => setForm((f) => ({ ...f, pause_minutes: p }))} data-testid={`entry-pause-${p}`}>
                    {p === 0 ? 'Keine' : `${p} Min.`}
                  </Chip>
                ))}
              </div>
            </div>

            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Tätigkeit</span>
              <TextArea rows={2} value={form.activity} onChange={set('activity')} placeholder="z. B. Bauendreinigung EG, Fensterreinigung" data-testid="entry-activity" />
              {recentActivities.length > 0 && (
                <div className="flex gap-2 overflow-x-auto -mx-6 px-6 mt-2 pb-1 no-scrollbar">
                  {recentActivities.map((a) => (
                    <Chip key={a} active={form.activity === a} onClick={() => setForm((f) => ({ ...f, activity: a }))} className="max-w-[220px] truncate">{a}</Chip>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-3 pt-1">
              <div>
                <div className="text-[12px] text-[#6E6E73]">Netto Arbeitszeit</div>
                <div className={`text-[22px] font-bold tracking-tight leading-none ${net > 0 ? 'text-[#C41E3A]' : 'text-[#A1A1A6]'}`}>{fmtHours(net)}</div>
              </div>
              <Btn type="submit" size="lg" loading={busy} data-testid="entry-save">{editing ? 'Speichern' : 'Eintragen'}</Btn>
            </div>
          </form>
        )}
      </div>
    </Sheet>
  );
}
