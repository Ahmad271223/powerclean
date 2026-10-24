import React, { useCallback, useEffect, useState } from 'react';
import { Gavel, Plus } from 'lucide-react';
import { toast } from 'sonner';
import ChatPanel from './ChatPanel';
import { Btn, Card, Select } from '../ui';
import { api } from '../../lib/api';

/** Ausschreibung → „Nachrichten“: Bieter sehen nur ihren eigenen Chat mit der Leitung; die Leitung hat je Bieterfirma einen getrennten Chat. */
export default function BieterChats({ ausschreibung, leitung }) {
  const [chats, setChats] = useState(null);
  const [aktiv, setAktiv] = useState('');
  const [neu, setNeu] = useState('');
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get('/api/chats').then((r) => setChats(r.chats.filter((c) => c.art === 'bieter' && c.ausschreibung_id === ausschreibung.id))).catch((err) => toast.error(err.message)), [ausschreibung.id]);
  useEffect(() => { laden(); }, [laden]);
  const oeffnen = async (bieter_firma_id) => {
    setBusy(true);
    try { const r = await api.post('/api/chats/oeffnen', { art: 'bieter', ausschreibung_id: ausschreibung.id, ...(bieter_firma_id ? { bieter_firma_id } : {}) }); await laden(); setAktiv(r.chat.id); setNeu(''); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  // Bieter: eigener Chat wird beim ersten Öffnen angelegt
  useEffect(() => { if (!leitung && chats && chats.length === 0 && !busy && !aktiv) oeffnen(); }, [leitung, chats]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (chats?.length && !aktiv) setAktiv(chats[0].id); }, [chats, aktiv]);
  if (!chats) return <Card className="p-6 text-[#A1A1A6] text-center">Wird geladen …</Card>;
  const offenFirmen = (ausschreibung.einladungen || []).filter((e) => !chats.some((c) => c.bieter_firma_id === e.firma_id) && e.firma_id);
  return (
    <div className="space-y-3">
      <p className="text-[13px] text-[#6E6E73]">{leitung ? 'Je Bieterfirma ein eigener, privater Chat – kein Bieter sieht Nachrichten eines anderen. Öffentliche Antworten gehören in „Rückfragen“.' : 'Privater Chat mit der ausschreibenden Projektleitung. Andere Bieter sehen ihn nie.'}</p>
      {leitung && (
        <div className="flex flex-wrap items-center gap-2">
          {chats.map((c) => <Btn key={c.id} size="sm" variant={c.id === aktiv ? 'primary' : 'soft'} onClick={() => setAktiv(c.id)}><Gavel size={14} /> {c.titel.split(' – ').slice(-1)[0]}{c.ungelesen > 0 && <span className="ml-1 text-[10px] font-semibold rounded-full bg-white/90 text-[#C41E3A] px-1.5">{c.ungelesen}</span>}</Btn>)}
          {offenFirmen.length > 0 && (
            <span className="flex items-center gap-1">
              <Select value={neu} onChange={(e) => setNeu(e.target.value)} className="h-9 text-[13px]"><option value="">Chat mit eingeladener Firma …</option>{offenFirmen.map((e) => <option key={e.firma_id} value={e.firma_id}>{e.firma_name}</option>)}</Select>
              <Btn size="sm" variant="dark" disabled={!neu} loading={busy} onClick={() => oeffnen(neu)}><Plus size={14} /> Öffnen</Btn>
            </span>
          )}
        </div>
      )}
      <Card className="p-4">{aktiv ? <ChatPanel chatId={aktiv} hoehe="h-[50vh]" onGelesen={laden} /> : <p className="text-[14px] text-[#6E6E73] text-center py-6">{leitung ? 'Noch kein Bieterchat. Bieter können ihn selbst eröffnen, oder du wählst oben eine eingeladene Firma.' : 'Chat wird geöffnet …'}</p>}</Card>
    </div>
  );
}
