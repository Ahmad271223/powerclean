import React, { useEffect, useState } from 'react';
import { FileDown, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Empty, TextInput } from '../components/ui';
import { api, download } from '../lib/api';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const details = (d) => (d && Object.keys(d).length ? Object.entries(d).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ') : '');

export default function ProtokollPage() {
  const [liste, setListe] = useState(null);
  const [q, setQ] = useState('');
  useEffect(() => { api.get('/api/protokoll?limit=500').then((r) => setListe(r.eintraege)).catch((err) => toast.error(err.message)); }, []);
  const s = q.trim().toLowerCase();
  const gefiltert = (liste || []).filter((p) => !s || [p.user_name, p.aktion, p.ziel, details(p.details)].join(' ').toLowerCase().includes(s));
  return (
    <Layout title="Sicherheitsprotokoll" subtitle="Wer hat wann was geändert. Zeiteinträge mit vorher/nachher – für Zoll- und Kundenprüfungen." action={<Btn variant="soft" size="sm" onClick={() => download('/api/exporte/protokoll.csv').catch((err) => toast.error(err.message))}><FileDown size={15} /> CSV</Btn>}>
      <TextInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Suchen (Name, Aktion, Projekt …)" className="mb-4 bg-white shadow-card border-0" />
      {!liste ? <Ladeanzeige /> : gefiltert.length === 0 ? <Card><Empty icon={ShieldCheck} title="Keine Einträge" /></Card> : (
        <Card className="divide-y divide-black/[0.06]">
          {gefiltert.map((p) => (
            <div key={p.id} className="px-4 py-3 text-[13px]">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5"><span className="text-[#86868B] whitespace-nowrap">{fmtZeit(p.created_at)}</span><span className="font-semibold">{p.user_name}</span><span className="font-mono text-[12px] bg-black/[0.05] rounded px-1.5 py-0.5">{p.aktion}</span><span className="text-[#6E6E73] truncate">{p.ziel}</span></div>
              {details(p.details) && <div className="text-[12px] text-[#86868B] mt-1 break-words">{details(p.details)}</div>}
            </div>
          ))}
        </Card>
      )}
    </Layout>
  );
}
