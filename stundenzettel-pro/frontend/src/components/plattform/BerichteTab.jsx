import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, FileText, Plus, Trash2, Wand2 } from 'lucide-react';
import { toast } from 'sonner';
import Bild from '../Bild';
import { Btn, Card, Empty, Field, IconBtn, Sheet, TextArea, TextInput } from '../ui';
import { api, download, openFile } from '../../lib/api';
import { fmtDate, fromKey, todayKey } from '../../lib/dates';

const CLS = { entwurf: 'bg-black/[0.06] text-[#6E6E73]', eingereicht: 'bg-[#EEE8FD] text-[#6D28D9]', freigegeben: 'bg-[#1B7F3B] text-white' };
const chip = (st, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${CLS[st] || ''}`}>{name || st}</span>;
const LEER = { datum: todayKey(), bereich: '', wetter: '', firmen: [], mitarbeiter_anzahl: 0, taetigkeiten: '', fortschritt: '', lieferungen: '', behinderungen: '', maengel: '', besondere_vorkommnisse: '', notizen: '' };
const FELDER = [['taetigkeiten', 'Tätigkeiten', 4], ['fortschritt', 'Fortschritt', 2], ['lieferungen', 'Lieferungen', 2], ['behinderungen', 'Behinderungen', 2], ['maengel', 'Mängel', 2], ['besondere_vorkommnisse', 'Besondere Vorkommnisse', 2], ['notizen', 'Notizen', 2]];
const AKTION = { entwurf: 'Zurück zum Entwurf', eingereicht: 'Zur Freigabe einreichen', freigegeben: 'Freigeben' };

/** Bautagesberichte: Entwurf (mit Vorbelegung aus Aufgaben und Lieferungen des Tages) → einreichen → Freigabe durch die Projektleitung, PDF. */
export default function BerichteTab({ projectId }) {
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState(null);
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/tagesberichte`).then(setDaten).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const vorbelegen = async () => {
    setBusy('vorschlag');
    try { const v = await api.get(`/api/projekte/${projectId}/tagesbericht-vorschlag?datum=${form.datum}`); setForm((f) => ({ ...f, firmen: v.firmen, taetigkeiten: f.taetigkeiten || v.taetigkeiten, lieferungen: f.lieferungen || v.lieferungen, mitarbeiter_anzahl: f.mitarbeiter_anzahl || v.mitarbeiter_anzahl, maengel: f.maengel || (v.maengel_offen ? `${v.maengel_offen} offene Mängel` : '') })); toast.success('Aus Aufgaben und Lieferungen des Tages vorbelegt'); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const speichern = async (e) => {
    e.preventDefault();
    const body = { ...form, mitarbeiter_anzahl: parseInt(form.mitarbeiter_anzahl, 10) || 0, firmen: Array.isArray(form.firmen) ? form.firmen : String(form.firmen).split(',').map((x) => x.trim()).filter(Boolean) };
    setBusy('speichern');
    try { if (form.id) { const { id, ...rest } = body; await api.put(`/api/tagesberichte/${id}`, rest); } else await api.post(`/api/projekte/${projectId}/tagesberichte`, body); toast.success('Bericht gespeichert'); setForm(null); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  if (!daten) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] text-[#6E6E73]">Berichte nach Datum. Entwurf → Einreichen → Freigabe durch die Projektleitung. Freigegebene Berichte sind unveränderlich.</p>
        {daten.schreiben && <Btn onClick={() => setForm({ ...LEER })}><Plus size={17} /> Tagesbericht</Btn>}
      </div>
      {daten.berichte.length === 0 ? <Card><Empty icon={FileText} title="Noch kein Bautagesbericht" text="Ein Bericht je Tag und Firma: Tätigkeiten, Firmen, Mitarbeiterzahl, Fortschritt, Lieferungen, Behinderungen, Mängel, Fotos." /></Card> : (
        <Card className="p-4"><ul className="divide-y divide-black/[0.06]">
          {daten.berichte.map((b) => (
            <li key={b.id} className="py-2.5 flex items-center gap-3">
              <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(b.id)}>
                <div className="text-[15px] font-semibold">{fmtDate(fromKey(b.datum))}{b.bereich ? <span className="font-normal text-[#6E6E73]"> · {b.bereich}</span> : null}</div>
                <div className="text-[12px] text-[#6E6E73] truncate">{[b.firma_name, b.verfasser, b.mitarbeiter_anzahl ? `${b.mitarbeiter_anzahl} Mitarbeiter` : '', b.fotos_anzahl ? `${b.fotos_anzahl} Fotos` : ''].filter(Boolean).join(' · ')}</div>
              </button>
              {chip(b.status, b.status_name)}
              <IconBtn size={30} variant="soft" onClick={() => download(`/api/tagesberichte/${b.id}/pdf`).catch((err) => toast.error(err.message))} title="PDF"><FileText size={14} /></IconBtn>
            </li>
          ))}
        </ul></Card>
      )}
      <Sheet open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }} title={form?.id ? 'Tagesbericht bearbeiten' : 'Neuer Tagesbericht'} subtitle="„Vorbelegen“ holt Aufgaben, Lieferungen und Anwesenheit des Tages." width="sm:max-w-2xl">
        {form && (
          <form onSubmit={speichern} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
              <Field label="Datum"><TextInput type="date" value={form.datum} onChange={set('datum')} required /></Field>
              <Field label="Bauabschnitt"><TextInput value={form.bereich} onChange={set('bereich')} /></Field>
              <Btn type="button" variant="soft" onClick={vorbelegen} loading={busy === 'vorschlag'}><Wand2 size={15} /> Vorbelegen</Btn>
              <Field label="Wetter"><TextInput value={form.wetter} onChange={set('wetter')} placeholder="z. B. trocken, 12 °C" /></Field>
              <Field label="Beteiligte Firmen" className="sm:col-span-2"><TextInput value={Array.isArray(form.firmen) ? form.firmen.join(', ') : form.firmen} onChange={(e) => { const v = e.target.value; setForm((f) => ({ ...f, firmen: v })); }} placeholder="durch Komma getrennt" /></Field>
              <Field label="Mitarbeiter vor Ort"><TextInput type="number" min="0" inputMode="numeric" value={form.mitarbeiter_anzahl} onChange={set('mitarbeiter_anzahl')} /></Field>
            </div>
            {FELDER.map(([k, l, rows]) => <Field key={k} label={l}><TextArea rows={rows} value={form[k]} onChange={set(k)} /></Field>)}
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy === 'speichern'}>Speichern</Btn></div>
          </form>
        )}
      </Sheet>
      <BerichtDialog berichtId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} onEdit={(b) => { setOffen(null); setForm({ id: b.id, ...Object.fromEntries(Object.keys(LEER).map((k) => [k, b[k] ?? LEER[k]])) }); }} />
    </div>
  );
}

function BerichtDialog({ berichtId, onOpenChange, onChanged, onEdit }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const eingabe = useRef(null);
  const laden = useCallback(() => { if (!berichtId) { setD(null); return; } api.get(`/api/tagesberichte/${berichtId}`).then(setD).catch((err) => toast.error(err.message)); }, [berichtId]);
  useEffect(() => { laden(); }, [laden]);
  const status = async (st) => { setBusy(st); try { await api.post(`/api/tagesberichte/${berichtId}/status`, { status: st }); toast.success(AKTION[st] || st); laden(); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const fotos = async (dateien) => {
    const liste = Array.from(dateien || []).filter((f) => f.type.startsWith('image/'));
    if (!liste.length) return;
    setBusy('foto');
    try { for (const f of liste) { const fd = new FormData(); fd.append('datei', f); fd.append('note', note); await api.upload(`/api/tagesberichte/${berichtId}/fotos`, fd); } toast.success('Foto gespeichert'); setNote(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const loeschen = async () => { if (!window.confirm('Bericht löschen?')) return; try { await api.del(`/api/tagesberichte/${berichtId}`); onOpenChange(false); onChanged?.(); } catch (err) { toast.error(err.message); } };
  const b = d?.bericht;
  return (
    <Sheet open={!!berichtId} onOpenChange={onOpenChange} title={b ? `Bautagesbericht ${fmtDate(fromKey(b.datum))}` : 'Bautagesbericht'} subtitle={b ? [b.firma_name, b.verfasser, b.bereich, b.wetter].filter(Boolean).join(' · ') : ''} width="sm:max-w-2xl"
      footer={b && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex gap-2">{d.bearbeiten && <Btn size="sm" variant="soft" onClick={() => onEdit?.(b)}>Bearbeiten</Btn>}{d.bearbeiten && <IconBtn size={34} variant="danger" onClick={loeschen} title="Löschen"><Trash2 size={14} /></IconBtn>}</div>
          <div className="flex gap-2">{d.status_erlaubt.map((s) => <Btn key={s} size="sm" variant={s === 'entwurf' ? 'soft' : 'primary'} onClick={() => status(s)} loading={busy === s}>{AKTION[s]}</Btn>)}<Btn size="sm" variant="dark" onClick={() => download(`/api/tagesberichte/${berichtId}/pdf`).catch((err) => toast.error(err.message))}><FileText size={14} /> PDF</Btn></div>
        </div>
      )}>
      {!b ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">{chip(b.status, b.status_name)}<span className="text-[12px] text-[#6E6E73]">{(b.firmen || []).join(', ')}{b.mitarbeiter_anzahl ? ` · ${b.mitarbeiter_anzahl} Mitarbeiter` : ''}</span></div>
          {FELDER.filter(([k]) => b[k]).map(([k, l]) => <div key={k}><span className="block text-[12px] font-semibold text-[#6E6E73]">{l}</span><p className="text-[14px] whitespace-pre-wrap">{b[k]}</p></div>)}
          <div>
            <div className="flex items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Camera size={14} /> Fotos ({d.fotos.length})</span>{d.bearbeiten && <><input ref={eingabe} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { fotos(e.target.files); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'foto'}><Camera size={14} /> Foto</Btn></>}</div>
            {d.bearbeiten && <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz zum nächsten Foto" className="h-9 text-[13px] mb-2" />}
            {d.fotos.length > 0 && <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">{d.fotos.map((f) => <button key={f.id} type="button" className="relative rounded-xl overflow-hidden aspect-square" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))}><Bild id={f.id} max={300} className="w-full h-full" alt={f.note || ''} />{f.note && <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[10px] px-1.5 py-0.5 truncate text-left">{f.note}</span>}</button>)}</div>}
          </div>
        </div>
      )}
    </Sheet>
  );
}
