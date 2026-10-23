import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, ChevronRight, Users } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import MitarbeiterDialog from '../components/MitarbeiterDialog';
import { AppIcon, Btn, Card, Empty } from '../components/ui';
import { api } from '../lib/api';
import { initials } from '../lib/utils';

const STATUS = (m) => (!m.active ? ['Deaktiviert', 'bg-black/[0.06] text-[#6E6E73]'] : m.eingeladen ? ['Eingeladen', 'bg-[#FFF4E5] text-[#B25E00]'] : ['Aktiv', 'bg-[#E8F8EC] text-[#1B7F3B]']);

export default function MitarbeiterPage() {
  const navigate = useNavigate();
  const [liste, setListe] = useState(null);
  const [alle, setAlle] = useState(false);
  const [dialog, setDialog] = useState(false);
  const laden = () => api.get(`/api/mitarbeiter?alle=${alle}`).then((r) => setListe(r.mitarbeiter)).catch((err) => toast.error(err.message));
  useEffect(() => { laden(); }, [alle]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Layout title="Mitarbeiter" subtitle="Konten, Rollen, Abwesenheiten, Stundenübersicht und Personalakte."
      action={<div className="flex gap-2"><Btn variant={alle ? 'dark' : 'soft'} size="sm" onClick={() => setAlle((v) => !v)}>{alle ? 'Nur aktive' : 'Auch deaktivierte'}</Btn><Btn onClick={() => setDialog(true)}><UserPlus size={18} /> <span className="hidden sm:inline">Einladen</span></Btn></div>}>
      {!liste ? <Ladeanzeige /> : liste.length === 0 ? <Card><Empty icon={Users} title="Noch keine Mitarbeiter" /></Card> : (
        <div className="space-y-2">
          {liste.map((m) => {
            const [label, cls] = STATUS(m);
            return (
              <Card key={m.id} role="button" tabIndex={0} onClick={() => navigate(`/mitarbeiter/${m.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/mitarbeiter/${m.id}`)} className="p-4 flex items-center gap-4 cursor-pointer transition-all hover:shadow-card-hover">
                <AppIcon color="#1D1D1F" text={initials(m.name)} size={44} className="rounded-xl" />
                <div className="flex-1 min-w-0">
                  <div className="text-[15px] font-semibold truncate">{m.name} <span className="text-[12px] font-normal text-[#6E6E73]">· {m.rolle_name}</span></div>
                  <div className="text-[13px] text-[#6E6E73] truncate">{m.email}{m.personalnummer ? ` · Nr. ${m.personalnummer}` : ''}{m.phone ? ` · ${m.phone}` : ''}</div>
                </div>
                <span className={`text-[11px] font-semibold rounded-full px-2.5 py-1 ${cls}`}>{label}</span>
                <ChevronRight size={18} className="text-[#C7C7CC]" />
              </Card>
            );
          })}
        </div>
      )}
      <MitarbeiterDialog open={dialog} onOpenChange={setDialog} onSaved={laden} />
    </Layout>
  );
}
