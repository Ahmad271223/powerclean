import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw, Users } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card } from '../ui';
import { api } from '../../lib/api';

/** Baustellen-Anwesenheit je Firma: eingestempelt, heute gearbeitet, heute eingeplant. Namen fremder Firmen nur nach deren Freigabe. */
export default function AnwesenheitTab({ projectId }) {
  const [d, setD] = useState(null);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/anwesenheit`).then(setD).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); const t = setInterval(laden, 60000); return () => clearInterval(t); }, [laden]);
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[16px] flex items-center gap-2"><Users size={16} /> Anwesenheit heute</h2>
        <Btn size="sm" variant="ghost" onClick={laden}><RefreshCw size={14} /> Aktualisieren</Btn>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[['aktiv', 'Eingestempelt'], ['heute', 'Heute gearbeitet'], ['geplant', 'Eingeplant']].map(([k, l]) => <div key={k} className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">{l}</div><div className="text-[24px] font-bold tracking-tight">{d.gesamt[k]}</div></div>)}
      </div>
      <table className="w-full text-[13px]">
        <thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-3 font-medium">Firma</th><th className="py-1 pr-3 text-right font-medium">Eingestempelt</th><th className="py-1 pr-3 text-right font-medium">Heute</th><th className="py-1 pr-3 text-right font-medium">Geplant</th></tr></thead>
        <tbody>{d.firmen.map((f) => (
          <tr key={f.firma_id} className="border-t border-black/[0.06] align-top">
            <td className="py-2 pr-3"><div className="font-semibold">{f.name}{f.eigentuemer ? ' (eigene)' : ''}</div><div className="text-[12px] text-[#6E6E73]">{f.gewerk}{f.namen_freigegeben ? (f.namen_aktiv.length || f.namen_heute.length ? ` · ${[...new Set([...f.namen_aktiv, ...f.namen_heute])].join(', ')}` : '') : f.eigentuemer ? '' : ' · Namen nicht freigegeben'}</div></td>
            <td className="py-2 pr-3 text-right">{f.aktiv}</td><td className="py-2 pr-3 text-right">{f.heute}</td><td className="py-2 pr-3 text-right">{f.geplant}</td>
          </tr>
        ))}</tbody>
      </table>
      <p className="text-[12px] text-[#86868B]">{d.hinweis}</p>
    </Card>
  );
}
