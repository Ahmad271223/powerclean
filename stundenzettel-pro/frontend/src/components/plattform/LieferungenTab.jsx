import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, ChevronLeft, ChevronRight, Pencil, Plus, Trash2, Truck } from 'lucide-react';
import { toast } from 'sonner';
import Bild from '../Bild';
import { Btn, Card, Empty, Field, IconBtn, Select, Sheet, TextArea, TextInput } from '../ui';
import { api, openFile } from '../../lib/api';
import { MONTHS_DE, WEEKDAYS_LONG_DE, fmtDate, fromKey, monthLastDay, toKey, todayKey } from '../../lib/dates';

const CLS = { angefragt: 'bg-black/[0.06] text-[#6E6E73]', bestaetigt: 'bg-[#E8F0FE] text-[#1D4ED8]', unterwegs: 'bg-[#FFF4E5] text-[#B25E00]', eingetroffen: 'bg-[#E8F8EC] text-[#1B7F3B]',
  entladen: 'bg-[#E8F8EC] text-[#1B7F3B]', abgeschlossen: 'bg-[#1B7F3B] text-white', verspaetet: 'bg-[#FDE8E8] text-[#C41E3A]', storniert: 'bg-black/[0.06] text-[#6E6E73] line-through' };
const chip = (st, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${CLS[st] || ''}`}>{name || st}</span>;
const LEER = { material: '', menge: '', lieferant: '', firma_id: '', geplant_am: todayKey(), zeitfenster_von: '07:00', zeitfenster_bis: '09:00', entladeort: '', ansprechpartner: '', bemerkungen: '' };

/** Lieferungen je Tag: Projektleitung plant, zuständige Firma bestätigt, meldet Verspätung/Eintreffen und hängt Lieferscheinfotos an. */
export default function LieferungenTab({ projectId }) {
  const heute = new Date();
  const [ym, setYm] = useState({ year: heute.getFullYear(), month: heute.getMonth() });
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState(null);
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState(false);
  const von = toKey(new Date(ym.year, ym.month, 1));
  const bis = toKey(monthLastDay(ym.year, ym.month));
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/lieferungen?von=${von}&bis=${bis}`).then(setDaten).catch((err) => toast.error(err.message)), [projectId, von, bis]);
  useEffect(() => { laden(); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const speichern = async (e) => {
    e.preventDefault();
    const body = { ...form, firma_id: form.firma_id || null, zeitfenster_von: form.zeitfenster_von || null, zeitfenster_bis: form.zeitfenster_bis || null };
    setBusy(true);
    try { if (form.id) { const { id, ...rest } = body; await api.put(`/api/lieferungen/${id}`, rest); } else await api.post(`/api/projekte/${projectId}/lieferungen`, body); toast.success('Lieferung gespeichert'); setForm(null); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (l) => { if (!window.confirm(`Lieferung „${l.material}“ löschen?`)) return; try { await api.del(`/api/lieferungen/${l.id}`); laden(); } catch (err) { toast.error(err.message); } };
  if (!daten) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  const tage = {};
  for (const l of daten.lieferungen) (tage[l.geplant_am] ||= []).push(l);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <IconBtn variant="soft" onClick={() => setYm(ym.month === 0 ? { year: ym.year - 1, month: 11 } : { year: ym.year, month: ym.month - 1 })}><ChevronLeft size={18} /></IconBtn>
          <span className="text-[15px] font-semibold px-1">{MONTHS_DE[ym.month]} {ym.year}</span>
          <IconBtn variant="soft" onClick={() => setYm(ym.month === 11 ? { year: ym.year + 1, month: 0 } : { year: ym.year, month: ym.month + 1 })}><ChevronRight size={18} /></IconBtn>
        </div>
        {daten.leitung && <Btn onClick={() => setForm({ ...LEER })}><Plus size={17} /> Lieferung</Btn>}
      </div>
      {daten.lieferungen.length === 0 ? <Card><Empty icon={Truck} title="Keine Lieferungen in diesem Monat" text={daten.leitung ? 'Plane Material und Anlieferungen je Tag; die zuständige Firma bestätigt und meldet das Eintreffen.' : 'Vom Auftraggeber geplante Lieferungen für eure Firma erscheinen hier.'} /></Card> : (
        Object.keys(tage).sort().map((tag) => (
          <Card key={tag} className="p-4">
            <div className="text-[13px] font-semibold text-[#6E6E73] mb-2">{WEEKDAYS_LONG_DE[(fromKey(tag).getDay() + 6) % 7]}, {fmtDate(fromKey(tag))}{tag === daten.heute ? ' · heute' : ''}</div>
            <ul className="divide-y divide-black/[0.06]">
              {tage[tag].map((l) => (
                <li key={l.id} className="py-2.5 flex items-center gap-3">
                  <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(l.id)}>
                    <div className="text-[15px] font-semibold truncate">{l.material}{l.menge ? <span className="font-normal text-[#6E6E73]"> · {l.menge}</span> : null}</div>
                    <div className="text-[12px] text-[#6E6E73] truncate">{[l.firma_name, l.lieferant && `von ${l.lieferant}`, l.zeitfenster_von && `${l.zeitfenster_von}${l.zeitfenster_bis ? `–${l.zeitfenster_bis}` : ''}`, l.entladeort, l.fotos_anzahl ? `${l.fotos_anzahl} Fotos` : ''].filter(Boolean).join(' · ')}</div>
                  </button>
                  {chip(l.status, l.status_name)}
                  {daten.leitung && <IconBtn size={30} onClick={() => setForm({ id: l.id, material: l.material, menge: l.menge || '', lieferant: l.lieferant || '', firma_id: l.firma_id === daten.firmen[0]?.id ? '' : l.firma_id, geplant_am: l.geplant_am, zeitfenster_von: l.zeitfenster_von || '', zeitfenster_bis: l.zeitfenster_bis || '', entladeort: l.entladeort || '', ansprechpartner: l.ansprechpartner || '', bemerkungen: l.bemerkungen || '' })} title="Bearbeiten"><Pencil size={14} /></IconBtn>}
                  {daten.leitung && <IconBtn size={30} variant="danger" onClick={() => loeschen(l)} title="Löschen"><Trash2 size={14} /></IconBtn>}
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}
      <Sheet open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }} title={form?.id ? 'Lieferung bearbeiten' : 'Lieferung planen'} subtitle="Die zuständige Firma sieht die Lieferung und meldet Bestätigung, Verspätung und Eintreffen.">
        {form && (
          <form onSubmit={speichern} className="space-y-4">
            <Field label="Material"><TextInput value={form.material} onChange={set('material')} required placeholder="z. B. Kabeltrassen 200 m" /></Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Menge"><TextInput value={form.menge} onChange={set('menge')} placeholder="z. B. 20 Paletten" /></Field>
              <Field label="Lieferant"><TextInput value={form.lieferant} onChange={set('lieferant')} /></Field>
              <Field label="Zuständige Firma"><Select value={form.firma_id} onChange={set('firma_id')} className="w-full">{daten.firmen.map((f) => <option key={f.id} value={f.eigentuemer ? '' : f.id}>{f.name}{f.eigentuemer ? ' (eigene)' : ''}</option>)}</Select></Field>
              <Field label="Geplanter Liefertermin"><TextInput type="date" value={form.geplant_am} onChange={set('geplant_am')} required /></Field>
              <Field label="Zeitfenster von"><TextInput type="time" value={form.zeitfenster_von} onChange={set('zeitfenster_von')} /></Field>
              <Field label="bis"><TextInput type="time" value={form.zeitfenster_bis} onChange={set('zeitfenster_bis')} /></Field>
              <Field label="Entladeort"><TextInput value={form.entladeort} onChange={set('entladeort')} placeholder="z. B. Tor 3" /></Field>
              <Field label="Ansprechpartner"><TextInput value={form.ansprechpartner} onChange={set('ansprechpartner')} /></Field>
            </div>
            <Field label="Bemerkungen"><TextArea rows={2} value={form.bemerkungen} onChange={set('bemerkungen')} /></Field>
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{form.id ? 'Speichern' : 'Planen'}</Btn></div>
          </form>
        )}
      </Sheet>
      <LieferungDialog lieferungId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} />
    </div>
  );
}

function LieferungDialog({ lieferungId, onOpenChange, onChanged }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const eingabe = useRef(null);
  const laden = useCallback(() => { if (!lieferungId) { setD(null); return; } api.get(`/api/lieferungen/${lieferungId}`).then(setD).catch((err) => toast.error(err.message)); }, [lieferungId]);
  useEffect(() => { laden(); }, [laden]);
  const status = async (st) => { setBusy(st); try { await api.post(`/api/lieferungen/${lieferungId}/status`, { status: st }); toast.success('Status gesetzt'); laden(); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const fotos = async (dateien) => {
    const liste = Array.from(dateien || []).filter((f) => f.type.startsWith('image/'));
    if (!liste.length) return;
    setBusy('foto');
    try { for (const f of liste) { const fd = new FormData(); fd.append('datei', f); fd.append('note', note); await api.upload(`/api/lieferungen/${lieferungId}/fotos`, fd); } toast.success('Foto gespeichert'); setNote(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const l = d?.lieferung;
  const NAMEN = d?.lieferung ? { angefragt: 'Angefragt', bestaetigt: 'Bestätigen', unterwegs: 'Unterwegs', eingetroffen: 'Eingetroffen', entladen: 'Entladen', abgeschlossen: 'Abschließen', verspaetet: 'Verspätet melden', storniert: 'Stornieren' } : {};
  return (
    <Sheet open={!!lieferungId} onOpenChange={onOpenChange} title={l?.material || 'Lieferung'} subtitle={l ? `${l.firma_name} · ${fmtDate(fromKey(l.geplant_am))}${l.zeitfenster_von ? ` · ${l.zeitfenster_von}${l.zeitfenster_bis ? `–${l.zeitfenster_bis}` : ''}` : ''}` : ''}>
      {!l ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">{chip(l.status, l.status_name)}{l.tatsaechlich_am && <span className="text-[12px] text-[#6E6E73]">eingetroffen am {fmtDate(fromKey(l.tatsaechlich_am))}</span>}</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[14px]">
            {l.menge && <div><span className="text-[#6E6E73]">Menge:</span> {l.menge}</div>}
            {l.lieferant && <div><span className="text-[#6E6E73]">Lieferant:</span> {l.lieferant}</div>}
            {l.entladeort && <div><span className="text-[#6E6E73]">Entladeort:</span> {l.entladeort}</div>}
            {l.ansprechpartner && <div><span className="text-[#6E6E73]">Ansprechpartner:</span> {l.ansprechpartner}</div>}
          </div>
          {l.bemerkungen && <p className="text-[14px] whitespace-pre-wrap rounded-2xl bg-[#F5F5F7] px-4 py-3">{l.bemerkungen}</p>}
          {d.status_erlaubt.length > 0 && <div><span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Status melden</span><div className="flex flex-wrap gap-2">{d.status_erlaubt.filter((s) => s !== l.status).map((s) => <Btn key={s} size="sm" variant={s === 'verspaetet' || s === 'storniert' ? 'soft' : 'primary'} onClick={() => status(s)} loading={busy === s}>{NAMEN[s] || s}</Btn>)}</div></div>}
          <div>
            <div className="flex items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Camera size={14} /> Lieferschein / Fotos ({d.fotos.length})</span>{d.rolle !== 'lesen' && <><input ref={eingabe} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { fotos(e.target.files); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'foto'}><Camera size={14} /> Foto</Btn></>}</div>
            {d.rolle !== 'lesen' && <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz, z. B. „Lieferschein“" className="h-9 text-[13px] mb-2" />}
            {d.fotos.length > 0 && <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">{d.fotos.map((f) => <button key={f.id} type="button" className="rounded-xl overflow-hidden aspect-square" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))}><Bild id={f.id} max={300} className="w-full h-full" alt={f.note || ''} /></button>)}</div>}
          </div>
          {(l.verlauf || []).length > 0 && <ul className="text-[12px] text-[#6E6E73] space-y-0.5">{l.verlauf.slice().reverse().map((v, i) => <li key={i}>{new Date(v.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} · {d.lieferung.status_name && (NAMEN[v.status] || v.status)} · {v.user_name}{v.kommentar ? ` · „${v.kommentar}“` : ''}</li>)}</ul>}
        </div>
      )}
    </Sheet>
  );
}
