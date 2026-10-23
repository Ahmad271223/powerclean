import React, { useCallback, useEffect, useState } from 'react';
import { FileCheck2, PenLine } from 'lucide-react';
import { toast } from 'sonner';
import { Card, Empty } from '../ui';
import { api } from '../../lib/api';
import { fmtDate, fmtHours, fromKey } from '../../lib/dates';

/** Eigentümerseite: von Partnerfirmen freigegebene Wochen-Nachweise (Zeiten, Namen, Kunden-Unterschrift). */
export default function NachweiseTab({ projectId }) {
  const [d, setD] = useState(null);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/nachweise`).then(setD).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  if (d.nachweise.length === 0) return <Card><Empty icon={FileCheck2} title="Noch keine freigegebenen Nachweise" text="Beteiligte Firmen geben ihre Wochen unter Projekt → Freigaben frei. Erst dann erscheinen Zeiten und Namen hier." /></Card>;
  return (
    <div className="space-y-4">
      {d.nachweise.map((n) => (
        <Card key={n.id} className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div><div className="text-[16px] font-semibold">{n.firma_name}</div><div className="text-[12px] text-[#6E6E73]">Woche {fmtDate(fromKey(n.week_monday))} – {fmtDate(fromKey(n.bis))} · freigegeben von {n.freigegeben_von}</div></div>
            <div className="text-right"><div className="text-[20px] font-bold tracking-tight">{fmtHours(n.minuten)}</div>{n.unterschrift ? <div className="text-[12px] text-[#1B7F3B] flex items-center gap-1 justify-end"><PenLine size={12} /> unterschrieben: {n.unterschrift.signer_name}</div> : <div className="text-[12px] text-[#86868B]">keine Kundenunterschrift</div>}</div>
          </div>
          <table className="w-full text-[13px]">
            <thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-3 font-medium">Datum</th><th className="py-1 pr-3 font-medium">Mitarbeiter</th><th className="py-1 pr-3 font-medium">Zeit</th><th className="py-1 pr-3 text-right font-medium">Netto</th><th className="py-1 font-medium">Tätigkeit</th></tr></thead>
            <tbody>{n.zeiten.map((z, i) => <tr key={i} className="border-t border-black/[0.06]"><td className="py-1.5 pr-3">{fmtDate(fromKey(z.date))}</td><td className="py-1.5 pr-3">{z.user_name || '–'}{(z.workers || 1) > 1 ? ` ×${z.workers}` : ''}</td><td className="py-1.5 pr-3">{z.start_time}–{z.end_time}{z.pause_minutes ? ` (${z.pause_minutes} Min. Pause)` : ''}</td><td className="py-1.5 pr-3 text-right">{fmtHours((z.net_minutes || 0) * (z.workers || 1))}</td><td className="py-1.5 text-[#6E6E73]">{z.activity}</td></tr>)}</tbody>
          </table>
        </Card>
      ))}
    </div>
  );
}
