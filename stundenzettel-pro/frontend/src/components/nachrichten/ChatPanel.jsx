import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Paperclip, Send } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, IconBtn, TextArea } from '../ui';
import { api, openFile } from '../../lib/api';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const fmtGroesse = (b) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

/** Ein Chat: Verlauf (alle 20 s nachgeladen), eigene Nachrichten rechts, Anhänge als Dateien mit den Rechten des Chats. */
export default function ChatPanel({ chatId, hoehe = 'h-[60vh]', onGelesen }) {
  const [d, setD] = useState(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState('');
  const ende = useRef(null);
  const eingabe = useRef(null);
  const laden = useCallback((leise = false) => {
    if (!chatId) { setD(null); return; }
    api.get(`/api/chats/${chatId}`).then((r) => { setD(r); onGelesen?.(); }).catch((err) => { if (!leise) toast.error(err.message); });
  }, [chatId, onGelesen]);
  useEffect(() => { laden(); const t = setInterval(() => laden(true), 20000); return () => clearInterval(t); }, [laden]);
  useEffect(() => { ende.current?.scrollIntoView({ block: 'end' }); }, [d?.nachrichten?.length]);
  const senden = async (e) => {
    e?.preventDefault();
    if (!text.trim()) return;
    setBusy('senden');
    try { await api.post(`/api/chats/${chatId}/nachrichten`, { text: text.trim() }); setText(''); laden(true); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const anhang = async (datei) => {
    if (!datei) return;
    setBusy('anhang');
    try { const fd = new FormData(); fd.append('datei', datei); fd.append('text', text.trim()); await api.upload(`/api/chats/${chatId}/anhaenge`, fd); setText(''); laden(true); toast.success('Datei gesendet'); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  if (!chatId) return null;
  if (!d) return <div className="text-[14px] text-[#A1A1A6] p-4">Wird geladen …</div>;
  return (
    <div className="flex flex-col min-h-0">
      <div className={`${hoehe} overflow-y-auto px-1 py-2 space-y-2`} data-testid="chat-verlauf">
        {d.nachrichten.length === 0 && <p className="text-[13px] text-[#A1A1A6] text-center py-6">Noch keine Nachrichten. Alles, was hier steht, bleibt gespeichert und landet in der Projektakte.</p>}
        {d.nachrichten.map((n) => (
          <div key={n.id} className={`flex ${n.eigene ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-[14px] ${n.eigene ? 'bg-[#C41E3A] text-white' : 'bg-[#F5F5F7] text-[#1D1D1F]'}`}>
              {!n.eigene && <div className="text-[11px] font-semibold opacity-80 mb-0.5">{n.user_name}{n.firma_name ? ` · ${n.firma_name}` : ''}</div>}
              {n.text && <div className="whitespace-pre-wrap break-words">{n.text}</div>}
              {(n.anhaenge || []).map((a) => (
                <button key={a.id} type="button" onClick={() => openFile(`/api/dokumente/${a.id}/datei`).catch((err) => toast.error(err.message))} className={`mt-1 flex items-center gap-1.5 text-[13px] underline ${n.eigene ? 'text-white' : 'text-[#1D4ED8]'}`}><Paperclip size={13} /> {a.filename} <span className="opacity-70 no-underline">({fmtGroesse(a.size || 0)})</span></button>
              ))}
              <div className={`text-[10px] mt-0.5 ${n.eigene ? 'text-white/70' : 'text-[#86868B]'}`}>{fmtZeit(n.created_at)}</div>
            </div>
          </div>
        ))}
        <div ref={ende} />
      </div>
      {d.chat.schreiben ? (
        <form onSubmit={senden} className="flex items-end gap-2 pt-2 border-t border-black/[0.06]">
          <input ref={eingabe} type="file" className="hidden" onChange={(e) => { anhang(e.target.files?.[0]); e.target.value = ''; }} />
          <IconBtn type="button" size={40} variant="soft" title="Datei anhängen" onClick={() => eingabe.current?.click()} disabled={!!busy}><Paperclip size={17} /></IconBtn>
          <TextArea rows={1} value={text} onChange={(e) => setText(e.target.value)} placeholder="Nachricht schreiben …" className="flex-1 min-h-[40px] max-h-32" data-testid="chat-eingabe"
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); senden(); } }} />
          <Btn type="submit" loading={busy === 'senden'} disabled={!text.trim()} aria-label="Senden"><Send size={16} /> Senden</Btn>
        </form>
      ) : <p className="text-[12px] text-[#86868B] pt-2">In diesem Chat kannst du nur lesen.</p>}
    </div>
  );
}
