import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, CheckCircle2, Clock, MapPin, Package, Users } from 'lucide-react';
import { toast } from 'sonner';
import Bild from '../Bild';
import { Btn, Chip, Sheet, TextInput } from '../ui';
import { api, openFile } from '../../lib/api';
import { fmtDate, fromKey } from '../../lib/dates';
import { fotoZeit } from '../../lib/fotos';

const PRIO = { niedrig: 'Niedrig', normal: 'Normal', hoch: 'Hoch', dringend: 'Dringend' };
const STATUS_CLS = { geplant: 'bg-black/[0.06] text-[#6E6E73]', zugewiesen: 'bg-[#E8F0FE] text-[#1D4ED8]', in_bearbeitung: 'bg-[#FFF4E5] text-[#B25E00]', blockiert: 'bg-[#FDE8E8] text-[#C41E3A]',
  eingereicht: 'bg-[#EEE8FD] text-[#6D28D9]', abgeschlossen: 'bg-[#E8F8EC] text-[#1B7F3B]', abgenommen: 'bg-[#1B7F3B] text-white' };
export const statusChip = (status, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[status] || ''}`}>{name || status}</span>;
const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

/** Eine Aufgabe: Details, Status setzen (je nach Rolle), Mitarbeiter zuteilen (beauftragte Firma), Fotos, Verlauf. */
export default function AufgabeDialog({ aufgabeId, onOpenChange, onChanged }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const [zuteilung, setZuteilung] = useState(null);
  const eingabe = useRef(null);
  const laden = useCallback(() => { if (!aufgabeId) { setD(null); return; } api.get(`/api/aufgaben/${aufgabeId}`).then((r) => { setD(r); setZuteilung({ vorarbeiter_user_id: r.aufgabe.vorarbeiter_user_id || '', mitarbeiter_ids: r.aufgabe.mitarbeiter_ids || [] }); }).catch((err) => toast.error(err.message)); }, [aufgabeId]);
  useEffect(() => { laden(); }, [laden]);

  const status = async (st) => {
    setBusy(st);
    try { await api.post(`/api/aufgaben/${aufgabeId}/status`, { status: st }); toast.success(`Status: ${statusName(st)}`); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const fotos = async (dateien) => {
    const liste = Array.from(dateien || []).filter((f) => f.type.startsWith('image/'));
    if (!liste.length) return;
    setBusy('foto');
    try {
      for (const f of liste) { const fd = new FormData(); fd.append('datei', f); fd.append('note', note); await api.upload(`/api/aufgaben/${aufgabeId}/fotos`, fd); }
      toast.success(liste.length === 1 ? 'Foto gespeichert' : `${liste.length} Fotos gespeichert`); setNote(''); laden(); onChanged?.();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const zuteilen = async () => {
    setBusy('zuteilung');
    try { await api.post(`/api/aufgaben/${aufgabeId}/zuteilung`, zuteilung); toast.success('Zuteilung gespeichert'); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const a = d?.aufgabe;
  const kannZuteilen = d && (d.rolle === 'firma' || d.rolle === 'leitung') && d.mitarbeiter.length > 0;
  const toggleMa = (id) => setZuteilung((z) => ({ ...z, mitarbeiter_ids: z.mitarbeiter_ids.includes(id) ? z.mitarbeiter_ids.filter((x) => x !== id) : [...z.mitarbeiter_ids, id] }));

  return (
    <Sheet open={!!aufgabeId} onOpenChange={onOpenChange} title={a?.titel || 'Aufgabe'} subtitle={a ? `${d.projekt.name}${d.projekt.address ? ` · ${d.projekt.address}` : ''}` : ''} width="sm:max-w-2xl">
      {!a ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            {statusChip(a.status, a.status_name)}
            <span className="text-[12px] text-[#6E6E73]">Priorität {PRIO[a.prioritaet] || a.prioritaet}</span>
            <span className="text-[12px] text-[#6E6E73]">· {a.firma_name}{a.gewerk ? ` · ${a.gewerk}` : ''}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[14px]">
            <div className="flex items-center gap-2"><Clock size={15} className="text-[#86868B]" /> {fmtDate(fromKey(a.datum))}{a.start_time ? ` · ${a.start_time}${a.end_time ? ` – ${a.end_time}` : ''}` : ''}</div>
            {a.bereich && <div className="flex items-center gap-2"><MapPin size={15} className="text-[#86868B]" /> {a.bereich}</div>}
            {a.material && <div className="flex items-center gap-2 sm:col-span-2"><Package size={15} className="text-[#86868B]" /> {a.material}</div>}
          </div>
          {a.beschreibung && <p className="text-[14px] whitespace-pre-wrap rounded-2xl bg-[#F5F5F7] px-4 py-3">{a.beschreibung}</p>}

          {d.status_erlaubt.length > 0 && (
            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Status setzen</span>
              <div className="flex flex-wrap gap-2">
                {d.status_erlaubt.filter((s) => s !== a.status).map((s) => <Btn key={s} size="sm" variant={s === 'abgenommen' || s === 'eingereicht' ? 'primary' : 'soft'} onClick={() => status(s)} loading={busy === s}>{s === 'abgenommen' && <CheckCircle2 size={14} />} {statusName(s)}</Btn>)}
              </div>
            </div>
          )}

          {kannZuteilen && (
            <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-3">
              <span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Users size={14} /> Wer macht das? (eigene Mitarbeiter)</span>
              <div>
                <span className="block text-[12px] text-[#86868B] mb-1">Vorarbeiter</span>
                <div className="flex flex-wrap gap-2"><Chip active={!zuteilung.vorarbeiter_user_id} onClick={() => setZuteilung((z) => ({ ...z, vorarbeiter_user_id: '' }))}>–</Chip>{d.mitarbeiter.filter((m) => m.role !== 'mitarbeiter').map((m) => <Chip key={m.id} active={zuteilung.vorarbeiter_user_id === m.id} onClick={() => setZuteilung((z) => ({ ...z, vorarbeiter_user_id: m.id }))}>{m.name}</Chip>)}</div>
              </div>
              <div>
                <span className="block text-[12px] text-[#86868B] mb-1">Mitarbeiter</span>
                <div className="flex flex-wrap gap-2">{d.mitarbeiter.map((m) => <Chip key={m.id} active={zuteilung.mitarbeiter_ids.includes(m.id)} onClick={() => toggleMa(m.id)}>{m.name}</Chip>)}</div>
              </div>
              <Btn size="sm" variant="dark" onClick={zuteilen} loading={busy === 'zuteilung'}>Zuteilung speichern</Btn>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Camera size={14} /> Fotos ({d.fotos.length})</span>
              {d.rolle && <><input ref={eingabe} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { fotos(e.target.files); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'foto'}><Camera size={14} /> Foto</Btn></>}
            </div>
            {d.rolle && <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz zum nächsten Foto (z. B. „Vorher“, „Nachher“)" className="h-9 text-[13px] mb-2" />}
            {d.fotos.length > 0 && (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {d.fotos.map((f) => (
                  <button key={f.id} type="button" className="relative rounded-xl overflow-hidden aspect-square" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))} title={[fotoZeit(f), f.uploaded_by_name, f.note].filter(Boolean).join(' · ')}>
                    <Bild id={f.id} max={300} className="w-full h-full" alt={f.note || ''} />
                    <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[10px] px-1.5 py-0.5 truncate text-left">{[f.uploaded_by_name, f.note].filter(Boolean).join(' · ')}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {(a.verlauf || []).length > 0 && (
            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Verlauf</span>
              <ul className="text-[12px] text-[#6E6E73] space-y-0.5">{a.verlauf.slice().reverse().map((v, i) => <li key={i}>{fmtZeit(v.at)} · {statusName(v.status)} · {v.user_name}{v.kommentar ? ` · „${v.kommentar}“` : ''}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </Sheet>
  );
}

const NAMEN = { geplant: 'Geplant', zugewiesen: 'Zugewiesen', in_bearbeitung: 'In Bearbeitung', blockiert: 'Blockiert', eingereicht: 'Zur Prüfung einreichen', abgeschlossen: 'Abgeschlossen', abgenommen: 'Abnehmen' };
export const statusName = (s) => NAMEN[s] || s;
