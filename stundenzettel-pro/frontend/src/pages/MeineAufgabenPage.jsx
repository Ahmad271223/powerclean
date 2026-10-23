import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardList } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import AufgabeDialog, { statusChip } from '../components/plattform/AufgabeDialog';
import { Card, Empty } from '../components/ui';
import { api } from '../lib/api';
import { WEEKDAYS_LONG_DE, fmtDate, fromKey } from '../lib/dates';

/** Mitarbeiter und Vorarbeiter: Was ist heute und demnächst zu tun? Antippen öffnet Details, Status und Fotos. */
export default function MeineAufgabenPage() {
  const [d, setD] = useState(null);
  const [offen, setOffen] = useState(null);
  const laden = useCallback(() => api.get('/api/aufgaben/meine').then(setD).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  if (!d) return <Layout title="Aufgaben"><Ladeanzeige /></Layout>;
  const tage = {};
  for (const a of d.aufgaben) (tage[a.datum] ||= []).push(a);
  const titel = (tag) => (tag === d.heute ? 'Heute' : `${WEEKDAYS_LONG_DE[(fromKey(tag).getDay() + 6) % 7]}, ${fmtDate(fromKey(tag))}`);
  return (
    <Layout title="Aufgaben" subtitle="Was heute und demnächst ansteht. Antippen: Details, Status melden, Fotos anhängen.">
      {d.aufgaben.length === 0 ? <Card><Empty icon={ClipboardList} title="Keine offenen Aufgaben" text="Sobald euch ein Auftraggeber oder euer Büro Aufgaben zuteilt, stehen sie hier." /></Card> : (
        <div className="space-y-4">
          {Object.keys(tage).sort().map((tag) => (
            <div key={tag}>
              <div className={`text-[13px] font-semibold mb-2 ${tag < d.heute ? 'text-[#C41E3A]' : 'text-[#6E6E73]'}`}>{titel(tag)}{tag < d.heute ? ' · überfällig' : ''}</div>
              <div className="space-y-2">
                {tage[tag].map((a) => (
                  <Card key={a.id} className="p-4"><button type="button" className="w-full text-left" onClick={() => setOffen(a.id)}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0"><div className="text-[16px] font-semibold leading-tight">{a.titel}</div><div className="text-[13px] text-[#6E6E73] mt-0.5">{a.projekt?.name}{a.projekt?.address ? ` · ${a.projekt.address}` : ''}</div><div className="text-[12px] text-[#86868B] mt-0.5">{[a.start_time && `${a.start_time}${a.end_time ? `–${a.end_time}` : ''}`, a.bereich, a.gewerk, a.projekt?.auftraggeber && `für ${a.projekt.auftraggeber}`].filter(Boolean).join(' · ')}</div></div>
                      {statusChip(a.status, a.status_name)}
                    </div>
                  </button></Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      <AufgabeDialog aufgabeId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} />
    </Layout>
  );
}
