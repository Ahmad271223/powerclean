import React, { useCallback, useEffect, useState } from 'react';
import { Check, Flag, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Field, IconBtn, TextInput } from '../ui';
import { api } from '../../lib/api';
import { fmtDate, fromKey, todayKey } from '../../lib/dates';

/** Meilensteine des Projekts (Leitung pflegt, alle Beteiligten sehen sie – auch im Kalender). */
export default function MeilensteineKarte({ projectId, className = '' }) {
  const [d, setD] = useState(null);
  const [neu, setNeu] = useState({ titel: '', datum: todayKey(), notiz: '' });
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/meilensteine`).then(setD).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  const anlegen = async (e) => {
    e.preventDefault();
    if (!neu.titel.trim()) return;
    setBusy(true);
    try { await api.post(`/api/projekte/${projectId}/meilensteine`, { ...neu, erledigt: false }); setNeu({ titel: '', datum: neu.datum, notiz: '' }); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const umschalten = async (m) => { try { await api.put(`/api/meilensteine/${m.id}`, { titel: m.titel, datum: m.datum, notiz: m.notiz || '', erledigt: !m.erledigt }); laden(); } catch (err) { toast.error(err.message); } };
  const loeschen = async (m) => { if (!window.confirm(`Meilenstein „${m.titel}“ löschen?`)) return; try { await api.del(`/api/meilensteine/${m.id}`); laden(); } catch (err) { toast.error(err.message); } };
  if (!d) return null;
  const heute = todayKey();
  return (
    <Card className={`p-5 space-y-3 ${className}`}>
      <h2 className="text-[16px] flex items-center gap-2"><Flag size={16} /> Meilensteine</h2>
      {d.meilensteine.length === 0 ? <p className="text-[13px] text-[#6E6E73]">{d.leitung ? 'Noch keine. Zwischenziele mit Datum, z. B. „Rohinstallation fertig“. Alle beteiligten Firmen sehen sie im Kalender.' : 'Der Auftraggeber hat noch keine Meilensteine eingetragen.'}</p> : (
        <ul className="divide-y divide-black/[0.06]">
          {d.meilensteine.map((m) => (
            <li key={m.id} className="py-2 flex items-center gap-3 text-[14px]">
              {d.leitung ? <button type="button" onClick={() => umschalten(m)} className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 ${m.erledigt ? 'bg-[#1B7F3B] border-[#1B7F3B] text-white' : 'border-black/20'}`} title={m.erledigt ? 'Als offen markieren' : 'Als erreicht markieren'}>{m.erledigt && <Check size={13} />}</button>
                : <span className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 ${m.erledigt ? 'bg-[#1B7F3B] border-[#1B7F3B] text-white' : 'border-black/20'}`}>{m.erledigt && <Check size={13} />}</span>}
              <div className="flex-1 min-w-0"><div className={`font-medium truncate ${m.erledigt ? 'line-through text-[#6E6E73]' : ''}`}>{m.titel}</div><div className="text-[12px] text-[#6E6E73] truncate">{fmtDate(fromKey(m.datum))}{!m.erledigt && m.datum < heute ? ' · überfällig' : ''}{m.notiz ? ` · ${m.notiz}` : ''}</div></div>
              {d.leitung && <IconBtn size={30} variant="danger" onClick={() => loeschen(m)} title="Löschen"><Trash2 size={14} /></IconBtn>}
            </li>
          ))}
        </ul>
      )}
      {d.leitung && (
        <form onSubmit={anlegen} className="grid grid-cols-1 sm:grid-cols-[1fr_150px_auto] gap-2 items-end rounded-2xl bg-[#F5F5F7] p-3">
          <Field label="Meilenstein"><TextInput value={neu.titel} onChange={(e) => setNeu({ ...neu, titel: e.target.value })} placeholder="z. B. Elektro Rohinstallation fertig" required /></Field>
          <Field label="Datum"><TextInput type="date" value={neu.datum} onChange={(e) => setNeu({ ...neu, datum: e.target.value })} required /></Field>
          <Btn type="submit" loading={busy}><Plus size={16} /> Anlegen</Btn>
        </form>
      )}
    </Card>
  );
}
