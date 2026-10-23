import React, { useEffect, useMemo, useState } from 'react';
import { Check, Download, FileText, Share2 } from 'lucide-react';
import Bild from './Bild';
import { Btn, IconBtn, Sheet, Toggle } from './ui';
import { fmtDate, fromKey } from '../lib/dates';
import { fotoTag, fotoZeit, fotosNachTag } from '../lib/fotos';

/**
 * Vor dem Erzeugen einer PDF: Fotos mit übernehmen? Alle sind vorausgewählt, einzelne lassen sich abwählen.
 * onConfirm(ausgewaehlteFotos, modus) – modus 'share' (öffnen/teilen) oder 'download'.
 */
export default function FotoAuswahlDialog({ open, onOpenChange, fotos = [], titel = 'PDF erstellen', hinweis = '', onConfirm, busy = false }) {
  const [mit, setMit] = useState(true);
  const [abgewaehlt, setAbgewaehlt] = useState(() => new Set());
  useEffect(() => { if (open) { setMit(true); setAbgewaehlt(new Set()); } }, [open]);
  const nachTag = useMemo(() => fotosNachTag(fotos), [fotos]);
  const gewaehlt = fotos.filter((f) => !abgewaehlt.has(f.id));
  const umschalten = (id) => setAbgewaehlt((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const bestaetigen = (modus) => onConfirm?.(mit ? gewaehlt : [], modus);

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={titel} subtitle={hinweis || `${fotos.length} ${fotos.length === 1 ? 'Foto' : 'Fotos'} im Zeitraum. Angetippte Fotos bleiben draußen.`} width="sm:max-w-2xl"
      footer={(
        <div className="flex items-center justify-between gap-3">
          <div className="text-[13px] text-[#6E6E73]">{mit ? `${gewaehlt.length} von ${fotos.length} Fotos kommen als „Fotodokumentation“ ans Ende der PDF.` : 'PDF ohne Fotos.'}</div>
          <div className="flex gap-2">
            <IconBtn size={40} variant="soft" onClick={() => bestaetigen('download')} disabled={busy} title="PDF herunterladen"><Download size={17} /></IconBtn>
            <Btn onClick={() => bestaetigen('share')} loading={busy}>{typeof navigator !== 'undefined' && navigator.share ? <Share2 size={16} /> : <FileText size={16} />} PDF erstellen</Btn>
          </div>
        </div>
      )}>
      <div className="space-y-4">
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={mit} onChange={setMit} label="Fotos mit in die PDF übernehmen" hint="Als Anhang „Fotodokumentation“: Datum, Uhrzeit, wer fotografiert hat, Notiz." /></div>
        {mit && (
          <>
            <div className="flex gap-2">
              <Btn size="sm" variant="soft" onClick={() => setAbgewaehlt(new Set())}>Alle</Btn>
              <Btn size="sm" variant="ghost" onClick={() => setAbgewaehlt(new Set(fotos.map((f) => f.id)))}>Keine</Btn>
            </div>
            {Object.keys(nachTag).sort().map((tag) => (
              <div key={tag}>
                <div className="text-[13px] font-medium text-[#6E6E73] mb-2">{fmtDate(fromKey(tag))}</div>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                  {nachTag[tag].map((f) => {
                    const an = !abgewaehlt.has(f.id);
                    return (
                      <button key={f.id} type="button" onClick={() => umschalten(f.id)} className={`relative rounded-xl overflow-hidden aspect-square border-2 transition-all ${an ? 'border-[#C41E3A]' : 'border-transparent opacity-45'}`} title={[fotoZeit(f), f.uploaded_by_name, f.note].filter(Boolean).join(' · ')}>
                        <Bild id={f.id} max={300} className="w-full h-full" alt={f.note || f.filename} />
                        <span className={`absolute top-1.5 right-1.5 w-6 h-6 rounded-full flex items-center justify-center ${an ? 'bg-[#C41E3A] text-white' : 'bg-white/90 text-transparent'}`}><Check size={14} /></span>
                        {(f.note || fotoZeit(f)) && <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[10px] px-1.5 py-0.5 truncate text-left">{[fotoZeit(f), f.note].filter(Boolean).join(' · ')}</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </Sheet>
  );
}

