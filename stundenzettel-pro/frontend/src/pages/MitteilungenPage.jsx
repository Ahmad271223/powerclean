import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, CheckCheck, ChevronRight, ListTodo } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Empty } from '../components/ui';
import { api } from '../lib/api';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const PRIO_CLS = { 1: 'bg-[#FDE8E8] text-[#C41E3A]', 2: 'bg-[#FFF4E5] text-[#B25E00]', 3: 'bg-black/[0.06] text-[#6E6E73]' };

/** Offene Punkte (aus /api/dashboard/aufgaben) – auf Startseiten und unter Mitteilungen. */
export function OffenePunkte({ punkte, titel = 'Jetzt zu erledigen', className = '' }) {
  if (!punkte) return null;
  return (
    <Card className={`p-5 ${className}`}>
      <h2 className="text-[17px] flex items-center gap-2 mb-2"><ListTodo size={17} /> {titel}</h2>
      {punkte.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Nichts offen – alles erledigt.</p> : (
        <ul className="divide-y divide-black/[0.06]">
          {punkte.map((p) => (
            <li key={p.art}><Link to={p.link} className="py-2 flex items-center gap-3 text-[14px]"><span className={`text-[12px] font-semibold rounded-full min-w-[28px] text-center px-2 py-0.5 ${PRIO_CLS[p.prio] || PRIO_CLS[3]}`}>{p.anzahl}</span><span className="flex-1 min-w-0 truncate font-medium">{p.text}</span><ChevronRight size={16} className="text-[#C7C7CC]" /></Link></li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Mitteilungen: In-App-Benachrichtigungen (Einladungen, Angebote, Vergaben, Aufgaben, Nachträge, Abnahmen) und offene Punkte. */
export default function MitteilungenPage() {
  const [ben, setBen] = useState(null);
  const [punkte, setPunkte] = useState(null);
  const laden = useCallback(() => {
    api.get('/api/benachrichtigungen').then(setBen).catch((err) => toast.error(err.message));
    api.get('/api/dashboard/aufgaben').then((r) => setPunkte(r.punkte)).catch(() => setPunkte([]));
  }, []);
  useEffect(() => { laden(); }, [laden]);
  const alleGelesen = async () => { try { await api.post('/api/benachrichtigungen/alle-gelesen'); laden(); } catch (err) { toast.error(err.message); } };
  if (!ben) return <Layout title="Mitteilungen"><Ladeanzeige /></Layout>;
  return (
    <Layout title="Mitteilungen" subtitle="Was sich bewegt hat und was jetzt eine Entscheidung braucht. E-Mails zu wichtigen Vorgängen stehen unter „Protokoll → E-Mail-Nachweise“."
      action={ben.ungelesen > 0 ? <Btn size="sm" variant="soft" onClick={alleGelesen}><CheckCheck size={15} /> Alle gelesen</Btn> : null}>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
        <Card className="p-5">
          <h2 className="text-[17px] flex items-center gap-2 mb-2"><Bell size={17} /> Benachrichtigungen {ben.ungelesen > 0 && <span className="text-[11px] font-semibold rounded-full bg-[#C41E3A] text-white px-2 py-0.5">{ben.ungelesen}</span>}</h2>
          {ben.benachrichtigungen.length === 0 ? <Empty icon={Bell} title="Nichts Neues" text="Einladungen, Angebote, Aufgaben, Nachträge und Abnahmen erscheinen hier." /> : (
            <ul className="divide-y divide-black/[0.06]">
              {ben.benachrichtigungen.map((n) => (
                <li key={n.id} className={`py-2.5 text-[14px] ${n.gelesen ? 'text-[#6E6E73]' : 'font-medium'}`}>
                  {n.link ? <Link to={n.link} className="block">{n.text}</Link> : n.text}
                  <span className="block text-[11px] text-[#A1A1A6] font-normal mt-0.5">{fmtZeit(n.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <OffenePunkte punkte={punkte} />
      </div>
    </Layout>
  );
}
