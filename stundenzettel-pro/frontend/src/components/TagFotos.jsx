import React, { useRef, useState } from 'react';
import { Camera, ExternalLink, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Bild from './Bild';
import { Btn, IconBtn, TextInput } from './ui';
import { api, openFile } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fotoZeit } from '../lib/fotos';

/** Fotos eines Arbeitstags im Projekt: ansehen, aufnehmen/hochladen (mit Datum des Tages), eigene oder als Büro löschen. */
export default function TagFotos({ projectId, dateKey, fotos = [], onChanged, darfHochladen = true }) {
  const { user, isBuero } = useAuth();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const eingabe = useRef(null);

  const hochladen = async (dateien) => {
    const liste = Array.from(dateien || []).filter((f) => f.type.startsWith('image/'));
    if (!liste.length) return;
    setBusy(true);
    try {
      for (const datei of liste) {
        const fd = new FormData();
        fd.append('datei', datei);
        fd.append('kategorie', 'Fotos');
        fd.append('date', dateKey);
        fd.append('note', note);
        await api.upload(`/api/projekte/${projectId}/dateien`, fd);
      }
      toast.success(liste.length === 1 ? 'Foto gespeichert' : `${liste.length} Fotos gespeichert`);
      setNote('');
      onChanged?.();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (f) => {
    if (!window.confirm('Foto wirklich löschen?')) return;
    try { await api.del(`/api/dokumente/${f.id}`); onChanged?.(); } catch (err) { toast.error(err.message); }
  };

  return (
    <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Camera size={14} /> Fotos an diesem Tag ({fotos.length})</span>
        {darfHochladen && (
          <>
            <input ref={eingabe} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { hochladen(e.target.files); e.target.value = ''; }} />
            <Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy}><Camera size={14} /> Foto aufnehmen / hochladen</Btn>
          </>
        )}
      </div>
      {darfHochladen && <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz zum nächsten Foto, z. B. „Vorher Treppenhaus“" className="h-9 text-[13px]" />}
      {fotos.length === 0 ? <p className="text-[12px] text-[#86868B]">Noch keine Fotos. Vorher/Nachher-Bilder landen hier und auf Wunsch in der PDF.</p> : (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {fotos.map((f) => (
            <div key={f.id} className="relative rounded-xl overflow-hidden aspect-square group">
              <button type="button" className="w-full h-full" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))} title="Groß anzeigen">
                <Bild id={f.id} max={300} className="w-full h-full" alt={f.note || f.filename} />
              </button>
              <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[10px] px-1.5 py-0.5 truncate text-left">{[fotoZeit(f), f.uploaded_by_name].filter(Boolean).join(' · ')}{f.note ? ` · ${f.note}` : ''}</span>
              <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                <IconBtn size={26} variant="soft" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))} title="Öffnen"><ExternalLink size={12} /></IconBtn>
                {(isBuero || f.uploaded_by === user?.id) && <IconBtn size={26} variant="danger" onClick={() => loeschen(f)} title="Löschen"><Trash2 size={12} /></IconBtn>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
