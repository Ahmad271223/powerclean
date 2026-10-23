import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Camera, MessageSquare, Pencil, Plus } from 'lucide-react';
import { toast } from 'sonner';
import Bild from '../Bild';
import { Btn, Card, Chip, Empty, Field, IconBtn, Select, Sheet, TextArea, TextInput } from '../ui';
import { api, openFile } from '../../lib/api';
import { fmtDate, fromKey } from '../../lib/dates';

const CLS = { offen: 'bg-[#FDE8E8] text-[#C41E3A]', zugewiesen: 'bg-[#E8F0FE] text-[#1D4ED8]', in_bearbeitung: 'bg-[#FFF4E5] text-[#B25E00]', behoben_gemeldet: 'bg-[#EEE8FD] text-[#6D28D9]',
  in_pruefung: 'bg-[#EEE8FD] text-[#6D28D9]', abgenommen: 'bg-[#1B7F3B] text-white', erneut_geoeffnet: 'bg-[#FDE8E8] text-[#C41E3A]' };
const chip = (st, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${CLS[st] || ''}`}>{name || st}</span>;
const PRIO = { niedrig: 'Niedrig', normal: 'Normal', hoch: 'Hoch', dringend: 'Dringend' };
const AKTION = { offen: 'Offen', zugewiesen: 'Zuweisen', in_bearbeitung: 'In Bearbeitung', behoben_gemeldet: 'Behoben melden', in_pruefung: 'In Prüfung', abgenommen: 'Abnehmen', erneut_geoeffnet: 'Erneut öffnen' };
const LEER = { beschreibung: '', bereich: '', kategorie: '', firma_id: '', frist: '', prioritaet: 'normal' };

/** Mängel: melden, zuweisen, Behebung mit Fotos melden, abnehmen oder erneut öffnen, Kommentarverlauf. */
export default function MaengelTab({ projectId }) {
  const [daten, setDaten] = useState(null);
  const [nurOffen, setNurOffen] = useState(true);
  const [form, setForm] = useState(null);
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/maengel?offen=${nurOffen}`).then(setDaten).catch((err) => toast.error(err.message)), [projectId, nurOffen]);
  useEffect(() => { laden(); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const speichern = async (e) => {
    e.preventDefault();
    const body = { ...form, firma_id: form.firma_id || null, frist: form.frist || null };
    setBusy(true);
    try { if (form.id) { const { id, ...rest } = body; await api.put(`/api/maengel/${id}`, rest); } else await api.post(`/api/projekte/${projectId}/maengel`, body); toast.success('Mangel gespeichert'); setForm(null); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  if (!daten) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2"><Chip active={nurOffen} onClick={() => setNurOffen(true)}>Offen</Chip><Chip active={!nurOffen} onClick={() => setNurOffen(false)}>Alle</Chip></div>
        <Btn onClick={() => setForm({ ...LEER })}><Plus size={17} /> Mangel melden</Btn>
      </div>
      {daten.maengel.length === 0 ? <Card><Empty icon={AlertTriangle} title={nurOffen ? 'Keine offenen Mängel' : 'Keine Mängel'} text="Mängel bekommen eine verantwortliche Firma, eine Frist und Fotos; abnehmen darf nur die Projektleitung." /></Card> : (
        <Card className="p-4">
          <ul className="divide-y divide-black/[0.06]">
            {daten.maengel.map((m) => (
              <li key={m.id} className="py-2.5 flex items-center gap-3">
                <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(m.id)}>
                  <div className="text-[15px] font-semibold truncate">{m.beschreibung}</div>
                  <div className="text-[12px] text-[#6E6E73] truncate">{[m.bereich, m.kategorie, m.firma_name || 'keine Firma zugewiesen', m.frist && `Frist ${fmtDate(fromKey(m.frist))}`, PRIO[m.prioritaet] && `Priorität ${PRIO[m.prioritaet]}`, m.fotos_anzahl ? `${m.fotos_anzahl} Fotos` : ''].filter(Boolean).join(' · ')}</div>
                </button>
                {m.ueberfaellig && <span className="text-[11px] font-semibold text-[#C41E3A]">überfällig</span>}
                {chip(m.status, m.status_name)}
                {daten.leitung && <IconBtn size={30} onClick={() => setForm({ id: m.id, beschreibung: m.beschreibung, bereich: m.bereich || '', kategorie: m.kategorie || '', firma_id: m.firma_id || '', frist: m.frist || '', prioritaet: m.prioritaet || 'normal' })} title="Bearbeiten"><Pencil size={14} /></IconBtn>}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Sheet open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }} title={form?.id ? 'Mangel bearbeiten' : 'Mangel melden'} subtitle={daten.leitung ? 'Mit Firma, Frist und Priorität. Die Firma meldet die Behebung mit Fotos.' : 'Die Projektleitung weist den Mangel einer Firma zu.'}>
        {form && (
          <form onSubmit={speichern} className="space-y-4">
            <Field label="Beschreibung"><TextArea rows={3} value={form.beschreibung} onChange={set('beschreibung')} required placeholder="Was ist wo mangelhaft?" /></Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Ort / Bauabschnitt"><TextInput value={form.bereich} onChange={set('bereich')} /></Field>
              <Field label="Kategorie"><TextInput value={form.kategorie} onChange={set('kategorie')} placeholder="z. B. Elektro, Reinigung" /></Field>
              {daten.leitung && <Field label="Verantwortliche Firma"><Select value={form.firma_id} onChange={set('firma_id')} className="w-full"><option value="">– noch offen –</option>{daten.firmen.map((f) => <option key={f.id} value={f.id}>{f.name}{f.eigentuemer ? ' (eigene)' : ''}</option>)}</Select></Field>}
              <Field label="Frist"><TextInput type="date" value={form.frist} onChange={set('frist')} /></Field>
              <Field label="Priorität"><Select value={form.prioritaet} onChange={set('prioritaet')} className="w-full">{Object.entries(PRIO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
            </div>
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{form.id ? 'Speichern' : 'Melden'}</Btn></div>
          </form>
        )}
      </Sheet>
      <MangelDialog mangelId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} />
    </div>
  );
}

function MangelDialog({ mangelId, onOpenChange, onChanged }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const [kommentar, setKommentar] = useState('');
  const eingabe = useRef(null);
  const laden = useCallback(() => { if (!mangelId) { setD(null); return; } api.get(`/api/maengel/${mangelId}`).then(setD).catch((err) => toast.error(err.message)); }, [mangelId]);
  useEffect(() => { laden(); }, [laden]);
  const status = async (st) => { setBusy(st); try { await api.post(`/api/maengel/${mangelId}/status`, { status: st, kommentar }); toast.success('Status gesetzt'); setKommentar(''); laden(); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const kommentieren = async () => { if (!kommentar.trim()) return; setBusy('kommentar'); try { await api.post(`/api/maengel/${mangelId}/kommentare`, { text: kommentar }); setKommentar(''); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const fotos = async (dateien) => {
    const liste = Array.from(dateien || []).filter((f) => f.type.startsWith('image/'));
    if (!liste.length) return;
    setBusy('foto');
    try { for (const f of liste) { const fd = new FormData(); fd.append('datei', f); fd.append('note', note); await api.upload(`/api/maengel/${mangelId}/fotos`, fd); } toast.success('Foto gespeichert'); setNote(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const m = d?.mangel;
  return (
    <Sheet open={!!mangelId} onOpenChange={onOpenChange} title="Mangel" subtitle={m ? [m.bereich, m.firma_name, m.frist && `Frist ${fmtDate(fromKey(m.frist))}`].filter(Boolean).join(' · ') : ''} width="sm:max-w-2xl">
      {!m ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">{chip(m.status, m.status_name)}<span className="text-[12px] text-[#6E6E73]">Priorität {PRIO[m.prioritaet] || m.prioritaet} · gemeldet von {m.gemeldet_von}</span>{m.ueberfaellig && <span className="text-[11px] font-semibold text-[#C41E3A]">überfällig</span>}</div>
          <p className="text-[14px] whitespace-pre-wrap rounded-2xl bg-[#F5F5F7] px-4 py-3">{m.beschreibung}</p>
          {d.status_erlaubt.length > 0 && (
            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Status</span>
              <div className="flex flex-wrap gap-2">{d.status_erlaubt.filter((s) => s !== m.status && s !== 'offen').map((s) => <Btn key={s} size="sm" variant={s === 'abgenommen' || s === 'behoben_gemeldet' ? 'primary' : 'soft'} onClick={() => status(s)} loading={busy === s}>{AKTION[s] || s}</Btn>)}</div>
            </div>
          )}
          {d.rolle !== 'lesen' && (
            <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-2">
              <span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><MessageSquare size={14} /> Kommentar</span>
              <div className="flex gap-2"><TextInput value={kommentar} onChange={(e) => setKommentar(e.target.value)} placeholder="Rückfrage, Hinweis, Begründung" className="h-9 text-[13px]" /><Btn size="sm" variant="dark" onClick={kommentieren} loading={busy === 'kommentar'}>Senden</Btn></div>
            </div>
          )}
          {(m.kommentare || []).length > 0 && <ul className="space-y-1.5">{m.kommentare.map((k) => <li key={k.id} className="text-[13px]"><span className="font-semibold">{k.user_name}</span> <span className="text-[#6E6E73]">({k.firma_name}, {new Date(k.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })})</span>: {k.text}</li>)}</ul>}
          <div>
            <div className="flex items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Camera size={14} /> Fotos ({d.fotos.length})</span>{d.rolle !== 'lesen' && <><input ref={eingabe} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { fotos(e.target.files); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'foto'}><Camera size={14} /> Foto</Btn></>}</div>
            {d.rolle !== 'lesen' && <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz, z. B. „Vorher“ oder „Behoben“" className="h-9 text-[13px] mb-2" />}
            {d.fotos.length > 0 && <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">{d.fotos.map((f) => <button key={f.id} type="button" className="relative rounded-xl overflow-hidden aspect-square" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))}><Bild id={f.id} max={300} className="w-full h-full" alt={f.note || ''} />{f.note && <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[10px] px-1.5 py-0.5 truncate text-left">{f.note}</span>}</button>)}</div>}
          </div>
          {(m.verlauf || []).length > 0 && <ul className="text-[12px] text-[#6E6E73] space-y-0.5">{m.verlauf.slice().reverse().map((v, i) => <li key={i}>{new Date(v.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} · {AKTION[v.status] || v.status} · {v.user_name}{v.kommentar ? ` · „${v.kommentar}“` : ''}</li>)}</ul>}
        </div>
      )}
    </Sheet>
  );
}
