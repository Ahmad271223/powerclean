import React, { useCallback, useEffect, useState } from 'react';
import { Lock, Users } from 'lucide-react';
import { toast } from 'sonner';
import ChatPanel from './ChatPanel';
import { Card, Segmented, Toggle } from '../ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';

/** Projekt-Reiter „Chat“: interner Projektchat der eigenen Firma (vom Büro je Projekt abschaltbar) und – auf Plattform-Projekten –
 *  der Partnerchat zwischen Projektleitung des Auftraggebers und der Leitung beteiligter Firmen. */
export default function ProjektChatTab({ projekt, plattformId, leitung }) {
  const { isBuero, isVorarbeiter } = useAuth();
  const partnerMoeglich = (isBuero || isVorarbeiter) && (!!projekt.verknuepft || leitung);
  const [bereich, setBereich] = useState('intern');
  const [chats, setChats] = useState({});
  const [fehler, setFehler] = useState({});
  const [offen, setOffen] = useState(projekt.chat_intern !== false);
  const oeffnen = useCallback(async (art) => {
    const koerper = art === 'intern' ? { art: 'projekt_intern', project_id: projekt.id } : { art: 'projekt_gu', project_id: plattformId };
    try { const r = await api.post('/api/chats/oeffnen', koerper); setChats((c) => ({ ...c, [art]: r.chat.id })); setFehler((f) => ({ ...f, [art]: '' })); }
    catch (err) { setFehler((f) => ({ ...f, [art]: err.message })); }
  }, [projekt.id, plattformId]);
  useEffect(() => { if (!chats[bereich] && !fehler[bereich]) oeffnen(bereich); }, [bereich, chats, fehler, oeffnen]);
  const umschalten = async (v) => {
    try { await api.put(`/api/projekte/${projekt.id}/chat`, { chat_intern: v }); setOffen(v); toast.success(v ? 'Projektchat für Mitarbeiter geöffnet' : 'Projektchat für Mitarbeiter geschlossen – das Büro liest weiter'); }
    catch (err) { toast.error(err.message); }
  };
  const optionen = [{ value: 'intern', label: 'Intern', icon: Lock }, ...(partnerMoeglich ? [{ value: 'partner', label: 'Mit Partnern', icon: Users }] : [])];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {optionen.length > 1 ? <Segmented value={bereich} onChange={setBereich} options={optionen} /> : <span className="text-[13px] text-[#6E6E73] flex items-center gap-1.5"><Lock size={14} /> Interner Projektchat</span>}
        {isBuero && bereich === 'intern' && <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={offen} onChange={umschalten} label="Für zugewiesene Mitarbeiter offen" /></div>}
      </div>
      <Card className="p-4">
        <p className="text-[12px] text-[#86868B] mb-2">{bereich === 'intern'
          ? 'Nur die eigene Firma: Büro, Projektleitung und zugewiesene Mitarbeiter. Nachrichten bleiben gespeichert und landen in der Projektakte.'
          : 'Projektleitung des Auftraggebers und Leitung der beteiligten Firmen. Mitarbeiter sehen nur ihre Aufgabenchats.'}</p>
        {fehler[bereich] ? <p className="text-[14px] text-[#C41E3A] py-6 text-center">{fehler[bereich]}</p> : <ChatPanel chatId={chats[bereich]} hoehe="h-[55vh]" />}
      </Card>
    </div>
  );
}
