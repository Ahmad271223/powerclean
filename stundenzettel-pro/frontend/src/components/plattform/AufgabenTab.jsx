import React, { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, ClipboardList, Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import AufgabeDialog, { statusChip } from './AufgabeDialog';
import { Btn, Card, Empty, Field, IconBtn, Select, Sheet, TextArea, TextInput } from '../ui';
import { api } from '../../lib/api';
import { MONTHS_DE, WEEKDAYS_LONG_DE, fmtDate, fromKey, monthLastDay, toKey, todayKey } from '../../lib/dates';

const LEER = { titel: '', beschreibung: '', gewerk: '', firma_id: '', datum: todayKey(), start_time: '07:00', end_time: '15:30', prioritaet: 'normal', bereich: '', material: '' };

/** Aufgaben eines Plattform-Projekts: Projektleitung plant je Tag, welche Firma was macht; Partner sehen ihre Aufgaben. */
export default function AufgabenTab({ projectId }) {
  const heute = new Date();
  const [ym, setYm] = useState({ year: heute.getFullYear(), month: heute.getMonth() });
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState(null);     // null = geschlossen, {} = neu, {id} = bearbeiten
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState(false);
  const von = toKey(new Date(ym.year, ym.month, 1));
  const bis = toKey(monthLastDay(ym.year, ym.month));
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/aufgaben?von=${von}&bis=${bis}`).then(setDaten).catch((err) => toast.error(err.message)), [projectId, von, bis]);
  useEffect(() => { laden(); }, [laden]);

  const speichern = async (e) => {
    e.preventDefault();
    const body = { ...form, firma_id: form.firma_id || null, start_time: form.start_time || null, end_time: form.end_time || null };
    setBusy(true);
    try {
      if (form.id) { const { id, ...rest } = body; await api.put(`/api/aufgaben/${id}`, rest); } else await api.post(`/api/projekte/${projectId}/aufgaben`, body);
      toast.success(form.id ? 'Aufgabe gespeichert' : 'Aufgabe angelegt'); setForm(null); laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (a) => { if (!window.confirm(`Aufgabe „${a.titel}“ löschen?`)) return; try { await api.del(`/api/aufgaben/${a.id}`); laden(); } catch (err) { toast.error(err.message); } };
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const prev = () => setYm(ym.month === 0 ? { year: ym.year - 1, month: 11 } : { year: ym.year, month: ym.month - 1 });
  const next = () => setYm(ym.month === 11 ? { year: ym.year + 1, month: 0 } : { year: ym.year, month: ym.month + 1 });

  if (!daten) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  const tage = {};
  for (const a of daten.aufgaben) (tage[a.datum] ||= []).push(a);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <IconBtn variant="soft" onClick={prev}><ChevronLeft size={18} /></IconBtn>
          <span className="text-[15px] font-semibold px-1">{MONTHS_DE[ym.month]} {ym.year}</span>
          <IconBtn variant="soft" onClick={next}><ChevronRight size={18} /></IconBtn>
        </div>
        {daten.leitung && <Btn onClick={() => setForm({ ...LEER, datum: von <= todayKey() && todayKey() <= bis ? todayKey() : von, firma_id: '' })}><Plus size={17} /> Aufgabe</Btn>}
      </div>
      {daten.aufgaben.length === 0 ? <Card><Empty icon={ClipboardList} title="Keine Aufgaben in diesem Monat" text={daten.leitung ? 'Lege fest, welche Firma an welchem Tag was erledigt.' : 'Sobald euch der Auftraggeber Aufgaben zuteilt, erscheinen sie hier.'} /></Card> : (
        Object.keys(tage).sort().map((tag) => (
          <Card key={tag} className="p-4">
            <div className="text-[13px] font-semibold text-[#6E6E73] mb-2">{WEEKDAYS_LONG_DE[(fromKey(tag).getDay() + 6) % 7]}, {fmtDate(fromKey(tag))}{tag === todayKey() ? ' · heute' : ''}</div>
            <ul className="divide-y divide-black/[0.06]">
              {tage[tag].map((a) => (
                <li key={a.id} className="py-2.5 flex items-center gap-3">
                  <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(a.id)}>
                    <div className="text-[15px] font-semibold truncate">{a.titel}</div>
                    <div className="text-[12px] text-[#6E6E73] truncate">{a.firma_name}{a.gewerk ? ` · ${a.gewerk}` : ''}{a.start_time ? ` · ${a.start_time}${a.end_time ? `–${a.end_time}` : ''}` : ''}{a.bereich ? ` · ${a.bereich}` : ''}{a.fotos_anzahl ? ` · ${a.fotos_anzahl} Fotos` : ''}{a.mitarbeiter_ids?.length ? ` · ${a.mitarbeiter_ids.length} Mitarbeiter` : ''}</div>
                  </button>
                  {statusChip(a.status, a.status_name)}
                  {daten.leitung && <IconBtn size={30} onClick={() => setForm({ id: a.id, titel: a.titel, beschreibung: a.beschreibung || '', gewerk: a.gewerk || '', firma_id: a.firma_id === daten.firmen[0]?.id ? '' : a.firma_id, datum: a.datum, start_time: a.start_time || '', end_time: a.end_time || '', prioritaet: a.prioritaet || 'normal', bereich: a.bereich || '', material: a.material || '' })} title="Bearbeiten"><Pencil size={14} /></IconBtn>}
                  {daten.leitung && <IconBtn size={30} variant="danger" onClick={() => loeschen(a)} title="Löschen"><Trash2 size={14} /></IconBtn>}
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}

      <Sheet open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }} title={form?.id ? 'Aufgabe bearbeiten' : 'Neue Aufgabe'} subtitle="Welche Firma macht was an welchem Tag? Die beauftragte Firma teilt ihre Mitarbeiter selbst zu.">
        {form && (
          <form onSubmit={speichern} className="space-y-4">
            <Field label="Aufgabe"><TextInput value={form.titel} onChange={set('titel')} required placeholder="z. B. Kabeltrassen in Halle B montieren" /></Field>
            <Field label="Beschreibung"><TextArea rows={2} value={form.beschreibung} onChange={set('beschreibung')} /></Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Firma"><Select value={form.firma_id} onChange={set('firma_id')} className="w-full">{daten.firmen.map((f) => <option key={f.id} value={f.eigentuemer ? '' : f.id}>{f.name}{f.gewerk ? ` (${f.gewerk})` : ''}{f.eigentuemer ? ' (eigene)' : ''}</option>)}</Select></Field>
              <Field label="Gewerk"><TextInput list="gewerke-liste" value={form.gewerk} onChange={set('gewerk')} /><datalist id="gewerke-liste">{daten.gewerke.map((g) => <option key={g} value={g} />)}</datalist></Field>
              <Field label="Datum"><TextInput type="date" value={form.datum} onChange={set('datum')} required /></Field>
              <Field label="Priorität"><Select value={form.prioritaet} onChange={set('prioritaet')} className="w-full">{[['niedrig', 'Niedrig'], ['normal', 'Normal'], ['hoch', 'Hoch'], ['dringend', 'Dringend']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
              <Field label="Beginn"><TextInput type="time" value={form.start_time} onChange={set('start_time')} /></Field>
              <Field label="Ende"><TextInput type="time" value={form.end_time} onChange={set('end_time')} /></Field>
              <Field label="Bauabschnitt / Ort"><TextInput value={form.bereich} onChange={set('bereich')} placeholder="z. B. Halle B, EG" /></Field>
              <Field label="Material"><TextInput value={form.material} onChange={set('material')} /></Field>
            </div>
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{form.id ? 'Speichern' : 'Anlegen'}</Btn></div>
          </form>
        )}
      </Sheet>
      <AufgabeDialog aufgabeId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} />
    </div>
  );
}
