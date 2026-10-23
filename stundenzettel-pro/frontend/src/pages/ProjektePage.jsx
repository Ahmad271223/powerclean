import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Pencil, FolderKanban, Search, Archive, X, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import ProjectDialog from '../components/ProjectDialog';
import { AppIcon, Btn, Card, Empty, IconBtn, TextInput } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDecimalHours, fmtDate, fromKey } from '../lib/dates';
import { initials } from '../lib/utils';

export default function ProjektePage() {
  const navigate = useNavigate();
  const { isBuero, firma } = useAuth();
  const [projekte, setProjekte] = useState(null);
  const [archiv, setArchiv] = useState(false);
  const [search, setSearch] = useState('');
  const [dialog, setDialog] = useState(false);
  const [edit, setEdit] = useState(null);

  const laden = () => api.get(`/api/projekte?archiviert=${archiv}`).then((r) => setProjekte(r.projekte)).catch((err) => toast.error(err.message));
  useEffect(() => { setProjekte(null); laden(); }, [archiv]); // eslint-disable-line react-hooks/exhaustive-deps

  const q = search.trim().toLowerCase();
  const liste = useMemo(() => (projekte || []).filter((p) => !q || p.name.toLowerCase().includes(q) || (p.customer_name || '').toLowerCase().includes(q)), [projekte, q]);

  return (
    <Layout title={archiv ? 'Archiv' : 'Projekte'} subtitle={archiv ? 'Abgeschlossene Objekte, alle Daten bleiben erhalten.' : 'Objekt antippen: Kalender, Stundenzettel, Akte.'}
      action={isBuero ? <Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={18} /> <span className="hidden sm:inline">Neues Projekt</span><span className="sm:hidden">Neu</span></Btn> : null}>
      <div className="flex flex-wrap items-center gap-2 mb-5">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#86868B]" />
          <TextInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Projekt oder Kunde suchen" className="pl-10 bg-white shadow-card border-0" />
          {search && <button type="button" onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/[0.06] flex items-center justify-center" aria-label="Suche löschen"><X size={13} /></button>}
        </div>
        {isBuero && <Btn variant={archiv ? 'dark' : 'soft'} size="sm" onClick={() => setArchiv((v) => !v)}><Archive size={15} /> {archiv ? 'Aktive' : 'Archiv'}</Btn>}
      </div>
      {!projekte ? <Ladeanzeige /> : liste.length === 0 ? (
        <Card>{projekte.length === 0
          ? <Empty icon={FolderKanban} title={archiv ? 'Nichts archiviert' : 'Noch keine Projekte'} text={isBuero ? 'Jedes Objekt bekommt seinen eigenen Kalender, Stundenzettel und Rechnungen.' : 'Dir ist noch kein Projekt zugewiesen.'} action={isBuero && !archiv ? <Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={18} /> Erstes Projekt anlegen</Btn> : null} />
          : <Empty icon={Search} title="Nichts gefunden" />}</Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {liste.map((p) => (
            <Card key={p.id} role="button" tabIndex={0} onClick={() => navigate(`/projekte/${p.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/projekte/${p.id}`)} className="p-5 flex items-center gap-4 cursor-pointer transition-all hover:shadow-card-hover active:scale-[0.99]">
              <AppIcon color={p.color} text={initials(p.name)} size={56} className={p.archived ? 'opacity-50 grayscale' : ''} />
              <div className="flex-1 min-w-0">
                <div className="text-[16px] font-semibold truncate">{p.name}</div>
                <div className="text-[13px] text-[#6E6E73] truncate">{p.customer_name || 'Kein Auftraggeber'}{p.schedule ? ` · ${p.schedule}` : ''}</div>
                <div className="text-[12px] text-[#86868B] mt-1">{fmtDecimalHours(p.total_minutes)} Std. · {p.entry_count} Einträge{p.last_activity_at ? ` · zuletzt ${fmtDate(fromKey(p.last_activity_at))}` : ''}</div>
              </div>
              {isBuero && <IconBtn size={32} onClick={(e) => { e.stopPropagation(); setEdit(p); setDialog(true); }} title="Bearbeiten" className="text-[#86868B]"><Pencil size={15} /></IconBtn>}
              <ChevronRight size={20} className="text-[#C7C7CC] -ml-1" />
            </Card>
          ))}
        </div>
      )}
      <ProjectDialog open={dialog} onOpenChange={setDialog} project={edit} defaultRate={firma?.default_hourly_rate || 0} onSaved={laden} onDeleted={laden} />
    </Layout>
  );
}
