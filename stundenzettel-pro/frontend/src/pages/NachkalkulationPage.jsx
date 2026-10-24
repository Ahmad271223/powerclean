import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Calculator, ChevronDown, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Card, Empty } from '../components/ui';
import NachkalkulationTab from '../components/material/NachkalkulationTab';
import { api } from '../lib/api';
import { fmtGeld } from '../lib/angebot';

const g = (x) => (x === null || x === undefined ? '–' : fmtGeld(x));

/** Nachkalkulation über alle Projekte mit Auftragswert: Umsatz, Plan, Ist, Abweichung, Deckungsbeitrag – aufklappbar je Projekt. */
export default function NachkalkulationPage() {
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [offen, setOffen] = useState(null);
  useEffect(() => { api.get('/api/nachkalkulation').then(setD).catch((err) => toast.error(err.message)); }, []);
  const liste = d?.projekte || [];
  const warnungen = liste.filter((p) => p.warnung);
  return (
    <Layout title="Nachkalkulation" subtitle="Was ein Auftrag voraussichtlich bringt und was er tatsächlich kostet – nach Kostenarten, ohne geplante und tatsächliche Zeit zu vermischen." wide>
      {!d ? <Ladeanzeige /> : liste.length === 0 ? <Card><Empty icon={Calculator} title="Noch keine Projekte mit Auftragswert" text="Sobald ein Angebot angenommen und als Auftrag angelegt ist (oder ein Projekt eine Pauschale hat), erscheint es hier." /></Card> : (
        <>
          {warnungen.length > 0 && <Card className="p-4 mb-4 border border-[#F59E0B]/40 text-[14px] flex items-center gap-2"><AlertTriangle size={16} className="text-[#B25E00]" /> {warnungen.length} Projekt{warnungen.length === 1 ? '' : 'e'} mit Kostenabweichung über 10 % oder negativem Deckungsbeitrag.</Card>}
          <Card className="overflow-hidden">
            <table className="w-full text-[13px]">
              <thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="px-4 py-2">Projekt</th><th className="py-2 pr-2 text-right">Umsatz</th><th className="py-2 pr-2 text-right">Plan</th><th className="py-2 pr-2 text-right">Ist</th><th className="py-2 pr-2 text-right">Abweichung</th><th className="py-2 pr-2 text-right">DB aktuell</th><th className="py-2 pr-4">Stand</th></tr></thead>
              <tbody>
                {liste.map((p) => (
                  <React.Fragment key={p.project_id}>
                    <tr role="button" tabIndex={0} onClick={() => setOffen((o) => (o === p.project_id ? null : p.project_id))} onKeyDown={(e) => e.key === 'Enter' && setOffen((o) => (o === p.project_id ? null : p.project_id))} className={`border-t border-black/[0.06] cursor-pointer hover:bg-black/[0.02] ${p.warnung ? 'bg-[#FFF4E5]/40' : ''}`}>
                      <td className="px-4 py-2 font-medium flex items-center gap-1.5">{offen === p.project_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}<button type="button" className="hover:underline" onClick={(e) => { e.stopPropagation(); navigate(`/projekte/${p.project_id}`); }}>{p.name}</button></td>
                      <td className="py-2 pr-2 text-right">{g(p.umsatz)}</td><td className="py-2 pr-2 text-right">{g(p.plan)}</td><td className="py-2 pr-2 text-right">{fmtGeld(p.ist)}</td>
                      <td className={`py-2 pr-2 text-right ${p.abweichung !== null && p.abweichung > 0 ? 'text-[#B25E00] font-semibold' : ''}`}>{p.abweichung === null ? '–' : `${p.abweichung > 0 ? '+' : ''}${fmtGeld(p.abweichung)}`}</td>
                      <td className={`py-2 pr-2 text-right ${p.deckungsbeitrag !== null && p.deckungsbeitrag < 0 ? 'text-[#C41E3A] font-semibold' : ''}`}>{g(p.deckungsbeitrag)}</td>
                      <td className="py-2 pr-4">{p.vollstaendig ? <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#E8F8EC] text-[#1B7F3B]">vollständig</span> : <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FFF4E5] text-[#B25E00]">{p.hinweise} Hinweis{p.hinweise === 1 ? '' : 'e'}</span>}</td>
                    </tr>
                    {offen === p.project_id && <tr><td colSpan={7} className="px-4 py-4 bg-[#FAFAFA]"><NachkalkulationTab projekt={{ id: p.project_id }} /></td></tr>}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </Layout>
  );
}
