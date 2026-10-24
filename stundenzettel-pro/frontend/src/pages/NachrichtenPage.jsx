import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MessageSquare, Users, Gavel, Handshake, ClipboardList, Lock } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import ChatPanel from '../components/nachrichten/ChatPanel';
import { Card, Empty } from '../components/ui';
import { api } from '../lib/api';

const ICON = { projekt_intern: Lock, projekt_gu: Users, bieter: Gavel, kontakt: Handshake, aufgabe: ClipboardList };
const fmtZeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

/** Nachrichten: alle Chats, in denen man Zugang hat (Projekt intern, mit Partnern, Bieter, Kontakt, Aufgabe). Rechte prüft der Server je Chat. */
export default function NachrichtenPage() {
  const [params, setParams] = useSearchParams();
  const aktiv = params.get('chat') || '';
  const [d, setD] = useState(null);
  const laden = useCallback((leise = false) => api.get('/api/chats').then(setD).catch((err) => { if (!leise) toast.error(err.message); }), []);
  useEffect(() => { laden(); const t = setInterval(() => laden(true), 30000); return () => clearInterval(t); }, [laden]);
  const waehlen = (id) => setParams(id ? { chat: id } : {});
  if (!d) return <Layout title="Nachrichten"><Ladeanzeige /></Layout>;
  const chat = d.chats.find((c) => c.id === aktiv);
  return (
    <Layout title="Nachrichten" subtitle="Projektchats, Partnerchats, Bieterchats, Kontaktanfragen und Aufgaben – jede Nachricht bleibt gespeichert. Ungelesenes wird nach kurzer Zeit per E-Mail angekündigt." wide>
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        <Card className={`p-2 ${aktiv ? 'hidden lg:block' : ''}`}>
          {d.chats.length === 0 ? <Empty icon={MessageSquare} title="Noch keine Chats" text="Chats öffnet ihr im Projekt (Reiter „Chat“), in einer Ausschreibung, im Firmenverzeichnis oder an einer Aufgabe." /> : (
            <ul className="divide-y divide-black/[0.06]" data-testid="chat-liste">
              {d.chats.map((c) => { const Icon = ICON[c.art] || MessageSquare; return (
                <li key={c.id}>
                  <button type="button" onClick={() => waehlen(c.id)} className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-3 ${c.id === aktiv ? 'bg-[#C41E3A]/10' : 'hover:bg-black/[0.03]'}`}>
                    <span className="mt-0.5 w-8 h-8 rounded-full bg-[#F5F5F7] flex items-center justify-center text-[#6E6E73] shrink-0"><Icon size={15} /></span>
                    <span className="flex-1 min-w-0">
                      <span className="flex items-center gap-2"><span className={`flex-1 truncate text-[14px] ${c.ungelesen ? 'font-semibold' : 'font-medium'}`}>{c.titel}</span>{c.ungelesen > 0 && <span className="text-[11px] font-semibold rounded-full bg-[#C41E3A] text-white px-2 py-0.5">{c.ungelesen}</span>}</span>
                      <span className="block text-[12px] text-[#6E6E73] truncate">{c.letzter_von ? `${c.letzter_von}: ` : ''}{c.letzter_text || c.art_name}</span>
                      <span className="block text-[11px] text-[#A1A1A6]">{c.art_name}{c.letzte_nachricht_at ? ` · ${fmtZeit(c.letzte_nachricht_at)}` : ''}</span>
                    </span>
                  </button>
                </li>
              ); })}
            </ul>
          )}
        </Card>
        <Card className={`p-4 ${aktiv ? '' : 'hidden lg:block'}`}>
          {!aktiv ? <p className="text-[14px] text-[#6E6E73] py-10 text-center">Chat links auswählen.</p> : (
            <>
              <div className="flex items-center gap-2 mb-2">
                <button type="button" className="lg:hidden text-[13px] text-[#C41E3A] font-medium" onClick={() => waehlen('')}>‹ Alle</button>
                <h2 className="text-[16px] flex-1 truncate">{chat?.titel || 'Chat'}</h2>
                {chat && <span className="text-[11px] text-[#6E6E73]">{chat.art_name}</span>}
              </div>
              <ChatPanel chatId={aktiv} onGelesen={() => laden(true)} />
            </>
          )}
        </Card>
      </div>
    </Layout>
  );
}
