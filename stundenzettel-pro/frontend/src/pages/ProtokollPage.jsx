import React, { useEffect, useState } from 'react';
import { FileDown, Mail, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Empty, Segmented, TextInput } from '../components/ui';
import { api, download } from '../lib/api';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const details = (d) => (d && Object.keys(d).length ? Object.entries(d).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ') : '');
const STATUS_CLS = { gesendet: 'bg-[#E8F8EC] text-[#1B7F3B]', offen: 'bg-[#FFF4E5] text-[#B25E00]', fehlgeschlagen: 'bg-[#FDE8E8] text-[#C41E3A]', nicht_konfiguriert: 'bg-black/[0.06] text-[#6E6E73]' };

/** Sicherheitsprotokoll (wer hat wann was geändert) und E-Mail-Nachweise (was wann an wen ging). */
export default function ProtokollPage() {
  const [tab, setTab] = useState('protokoll');
  const [liste, setListe] = useState(null);
  const [q, setQ] = useState('');
  useEffect(() => { api.get('/api/protokoll?limit=500').then((r) => setListe(r.eintraege)).catch((err) => toast.error(err.message)); }, []);
  const s = q.trim().toLowerCase();
  const gefiltert = (liste || []).filter((p) => !s || [p.user_name, p.aktion, p.ziel, details(p.details)].join(' ').toLowerCase().includes(s));
  return (
    <Layout title="Protokoll" subtitle="Wer hat wann was geändert – und welche E-Mails zu Einladungen, Angeboten, Zuschlägen, Nachträgen und Abnahmen gegangen sind." action={tab === 'protokoll' ? <Btn variant="soft" size="sm" onClick={() => download('/api/exporte/protokoll.csv').catch((err) => toast.error(err.message))}><FileDown size={15} /> CSV</Btn> : null}>
      <div className="flex justify-center mb-5"><Segmented value={tab} onChange={setTab} options={[{ value: 'protokoll', label: 'Sicherheitsprotokoll', icon: ShieldCheck }, { value: 'emails', label: 'E-Mail-Nachweise', icon: Mail }]} /></div>
      {tab === 'emails' ? <EmailNachweise /> : (
        <>
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
        </>
      )}
    </Layout>
  );
}

function EmailNachweise() {
  const [d, setD] = useState(null);
  const [offen, setOffen] = useState(null);
  useEffect(() => { api.get('/api/firma/emails').then(setD).catch((err) => toast.error(err.message)); }, []);
  if (!d) return <Ladeanzeige />;
  return (
    <div className="space-y-4">
      {!d.eingerichtet && <Card className="p-4 text-[13px] text-[#7A4100] bg-[#FFF4E5]">Der E-Mail-Versand ist auf diesem Server noch nicht eingerichtet (SMTP). Die Einträge zeigen, was versendet worden wäre; Einladungslinks stehen weiterhin in der App. Einrichtung: Betreiber, siehe BETRIEB.md.</Card>}
      {d.emails.length === 0 ? <Card><Empty icon={Mail} title="Noch keine E-Mails" text="Einladungen, Einreichungsnachweise, Zuschläge, Absagen, Nachträge und Abnahmen erzeugen E-Mails – nie jede Statusänderung." /></Card> : (
        <Card className="divide-y divide-black/[0.06]">
          {d.emails.map((e) => (
            <div key={e.id} className="px-4 py-3 text-[13px]">
              <button type="button" className="w-full text-left" onClick={() => setOffen(offen === e.id ? null : e.id)}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5"><span className="text-[#86868B] whitespace-nowrap">{fmtZeit(e.created_at)}</span><span className="font-semibold truncate">{e.betreff}</span><span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[e.status] || ''}`}>{e.status_name}</span></div>
                <div className="text-[12px] text-[#86868B] mt-0.5">An {e.an} · {e.art_name}{e.versuche > 1 ? ` · ${e.versuche} Versuche` : ''}{e.fehler ? ` · Fehler: ${e.fehler}` : ''}{e.gesendet_at ? ` · gesendet ${fmtZeit(e.gesendet_at)}` : ''}</div>
              </button>
              {offen === e.id && <pre className="mt-2 text-[12px] whitespace-pre-wrap break-words rounded-2xl bg-[#F5F5F7] px-4 py-3">{e.text}</pre>}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
