import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, BadgeCheck, Gavel, Inbox, Megaphone, Search, Send, Store } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Empty, Segmented, Select, TextInput, Toggle } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { ANGEBOT_CLS, ANGEBOT_NAMEN, STATUS_CLS, VERGABE_CLS, VERGABE_NAMEN, fmtGeld, fmtTag, fristText } from '../lib/ausschreibung';

const TABS = [{ value: 'entdecken', label: 'Entdecken', icon: Store }, { value: 'einladungen', label: 'Einladungen', icon: Inbox }, { value: 'angebote', label: 'Meine Angebote', icon: Send },
  { value: 'auftraege', label: 'Erhaltene Aufträge', icon: BadgeCheck }, { value: 'eigene', label: 'Meine Ausschreibungen', icon: Megaphone }];
const FILTER_LEER = { q: '', gewerk: '', ort: '', abrechnungsart: '', frist_bis: '', nur_einladungen: false };

function Karte({ a, extra }) {
  return (
    <Card className="p-4 flex flex-col gap-2">
      <div className="flex items-start gap-2"><div className="flex-1 min-w-0"><Link to={`/ausschreibungen/${a.id}`} className="font-semibold text-[15px] leading-tight line-clamp-2">{a.titel}{a.projekt?.name ? ` – ${a.projekt.name}` : ''}</Link><div className="text-[12px] text-[#6E6E73] mt-0.5">{a.nummer}</div></div><span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 shrink-0 ${STATUS_CLS[a.status] || ''}`}>{a.status_name}</span></div>
      <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-0.5 text-[13px]">
        <dt className="text-[#6E6E73]">Auftraggeber</dt><dd>{a.auftraggeber?.name}</dd>
        <dt className="text-[#6E6E73]">Standort</dt><dd className="truncate">{a.ausfuehrungsort || a.auftraggeber?.city || '–'}</dd>
        <dt className="text-[#6E6E73]">Gewerk</dt><dd>{a.gewerk}{a.leistungsart ? ` · ${a.leistungsart}` : ''}</dd>
        <dt className="text-[#6E6E73]">Ausführung</dt><dd>{a.ausfuehrung_von ? `${fmtTag(a.ausfuehrung_von)} – ${fmtTag(a.ausfuehrung_bis)}` : '–'}</dd>
        <dt className="text-[#6E6E73]">Angebotsfrist</dt><dd className={a.frist_tage !== null && a.frist_tage <= 3 && a.frist_tage >= 0 ? 'text-[#C41E3A] font-semibold' : ''}>{fristText(a)}</dd>
        {a.abrechnungsart_name && <><dt className="text-[#6E6E73]">Abrechnung</dt><dd>{a.abrechnungsart_name}{a.budget ? ` · Budget ${fmtGeld(a.budget)}` : ''}</dd></>}
      </dl>
      <div className="flex flex-wrap items-center gap-2 mt-1">
        {a.eingeladen && <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FFF4E5] text-[#B25E00]">Direkt eingeladen</span>}
        {a.angebot && <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${ANGEBOT_CLS[a.angebot.status] || ''}`}>Angebot: {ANGEBOT_NAMEN[a.angebot.status] || a.angebot.status}{a.angebot.summe_netto ? ` · ${fmtGeld(a.angebot.summe_netto)}` : ''}</span>}
        {extra}
        <Link to={`/ausschreibungen/${a.id}`} className="ml-auto"><Btn size="sm" variant="soft">Ausschreibung ansehen</Btn></Link>
      </div>
    </Card>
  );
}

/** Ausschreibungen: Marktplatz mit Filtern, Einladungen, eigene Angebote, erhaltene Aufträge (Vergaben) und eigene Ausschreibungen als Auftraggeber. */
export default function AusschreibungenPage() {
  const { firma } = useAuth();
  const nurAuftraggeber = firma?.art === 'auftraggeber';
  const [tab, setTab] = useState(() => (nurAuftraggeber ? 'eigene' : 'entdecken'));
  const [ue, setUe] = useState(null);
  const [markt, setMarkt] = useState(null);
  const [filter, setFilter] = useState(FILTER_LEER);
  const ladenUe = useCallback(() => api.get('/api/ausschreibungen/uebersicht').then(setUe).catch((err) => toast.error(err.message)), []);
  const ladenMarkt = useCallback(() => {
    const p = new URLSearchParams();
    Object.entries(filter).forEach(([k, v]) => { if (v) p.set(k, v === true ? 'true' : v); });
    return api.get(`/api/ausschreibungen?${p.toString()}`).then(setMarkt).catch((err) => toast.error(err.message));
  }, [filter]);
  useEffect(() => { ladenUe(); }, [ladenUe]);
  useEffect(() => { const t = setTimeout(ladenMarkt, 250); return () => clearTimeout(t); }, [ladenMarkt]);
  const setF = (k) => (e) => { const v = e.target.value; setFilter((f) => ({ ...f, [k]: v })); };
  if (!ue) return <Layout title="Ausschreibungen"><Ladeanzeige /></Layout>;
  const zaehler = { einladungen: ue.einladungen.filter((e) => e.status === 'veroeffentlicht' && !e.angebot).length, auftraege: ue.vergaben.filter((v) => v.status === 'mitgeteilt').length };
  const tabs = TABS.filter((t) => (nurAuftraggeber ? t.value === 'eigene' : (firma?.art || 'betrieb') === 'betrieb' ? t.value !== 'eigene' : true)).map((t) => ({ ...t, label: t.value === 'einladungen' && zaehler.einladungen ? `${t.label} (${zaehler.einladungen})` : t.value === 'auftraege' && zaehler.auftraege ? `${t.label} (${zaehler.auftraege})` : t.label }));
  return (
    <Layout wide title="Ausschreibungen" subtitle={nurAuftraggeber ? 'Gewerke ausschreiben, Firmen einladen, Angebote vergleichen und vergeben – Ausschreibungen werden im Bauprojekt angelegt.' : firma?.art === 'beides' ? 'Aufträge finden und Angebote abgeben – und eigene Gewerke ausschreiben, Angebote vergleichen und vergeben.' : 'Aufträge finden, Angebote abgeben, Aufträge annehmen – alles in einem Programm.'}>
      {ue.fristen_bald.length > 0 && <div className="mb-4 rounded-2xl bg-[#FDE8E8] text-[#C41E3A] px-4 py-3 text-[13px] flex items-start gap-2"><AlertTriangle size={15} className="shrink-0 mt-0.5" /><span>Bald endende Angebotsfrist: {ue.fristen_bald.map((a) => <Link key={a.id} to={`/ausschreibungen/${a.id}`} className="underline mr-2">{a.titel} ({fristText(a)})</Link>)}</span></div>}
      {zaehler.auftraege > 0 && <div className="mb-4 rounded-2xl bg-[#E8F8EC] text-[#1B7F3B] px-4 py-3 text-[13px] flex items-start gap-2"><BadgeCheck size={15} className="shrink-0 mt-0.5" /><span>Ihr habt eine Vergabe erhalten – bitte unter „Erhaltene Aufträge“ die Annahme bestätigen.</span></div>}
      <div className="flex justify-center mb-5 overflow-x-auto no-scrollbar"><Segmented value={tab} onChange={setTab} options={tabs} /></div>

      {tab === 'entdecken' && (
        <div className="space-y-4">
          <Card className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2 items-end">
            <div className="relative lg:col-span-2"><Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#86868B]" /><TextInput value={filter.q} onChange={setF('q')} className="pl-10" placeholder="Suche: Titel, Leistung, Projekt" /></div>
            <Select value={filter.gewerk} onChange={setF('gewerk')} className="w-full"><option value="">Alle Gewerke</option>{(ue.gewerke || []).map((g) => <option key={g} value={g}>{g}</option>)}</Select>
            <TextInput value={filter.ort} onChange={setF('ort')} placeholder="Ort / Standort" />
            <Select value={filter.abrechnungsart} onChange={setF('abrechnungsart')} className="w-full"><option value="">Alle Abrechnungsarten</option>{Object.entries(ue.abrechnungsarten || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
            <TextInput type="date" value={filter.frist_bis} onChange={setF('frist_bis')} title="Angebotsfrist bis" />
            <div className="sm:col-span-2 lg:col-span-6 flex flex-wrap items-center justify-between gap-2"><Toggle checked={filter.nur_einladungen} onChange={(v) => setFilter((f) => ({ ...f, nur_einladungen: v }))} label="Nur direkte Einladungen" />{Object.values(filter).some(Boolean) && <Btn size="sm" variant="ghost" onClick={() => setFilter(FILTER_LEER)}>Filter zurücksetzen</Btn>}</div>
          </Card>
          {!markt ? <Ladeanzeige /> : markt.ausschreibungen.length === 0 ? <Card><Empty icon={Store} title="Keine passende Ausschreibung" text="Plattformweit sichtbare Ausschreibungen und direkte Einladungen erscheinen hier. Pflegt unter „Zusammenarbeit“ Gewerke und Regionen, um über neue passende Ausschreibungen benachrichtigt zu werden." /></Card>
            : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{markt.ausschreibungen.map((a) => <Karte key={a.id} a={a} />)}</div>}
        </div>
      )}

      {tab === 'einladungen' && (ue.einladungen.length === 0 ? <Card><Empty icon={Inbox} title="Keine Einladungen" text="Lädt ein Auftraggeber eure Firma direkt zu einer Ausschreibung ein, erscheint sie hier." /></Card>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{ue.einladungen.map((a) => <Karte key={a.id} a={a} extra={a.nachricht ? <span className="text-[12px] text-[#6E6E73] italic">„{a.nachricht}“</span> : null} />)}</div>)}

      {tab === 'angebote' && (ue.angebote.length === 0 ? <Card><Empty icon={Send} title="Noch keine Angebote" text="Angebote (Entwürfe und eingereichte) erscheinen hier mit Status und Version." /></Card>
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{ue.angebote.map((a) => <Karte key={a.id} a={a} extra={a.angebot?.nachreichen_bis ? <span className="text-[11px] font-semibold text-[#C41E3A]">Nachreichung bis {fmtTag(a.angebot.nachreichen_bis)}</span> : null} />)}</div>)}

      {tab === 'auftraege' && (ue.vergaben.length === 0 ? <Card><Empty icon={BadgeCheck} title="Noch keine Aufträge" text="Wird euch eine Ausschreibung zugeschlagen, erscheint die Vergabe hier – mit Vertragsunterlagen und der verbindlichen Annahme." /></Card>
        : <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{ue.vergaben.map((v) => (
          <Card key={v.id} className="p-4 space-y-2">
            <div className="flex items-start gap-2"><div className="flex-1 min-w-0"><Link to={`/ausschreibungen/${v.ausschreibung_id}`} className="font-semibold text-[15px]">{v.ausschreibung.titel}</Link><div className="text-[12px] text-[#6E6E73]">{v.auftraggeber?.name} · {v.ausschreibung.projekt?.name}</div></div><span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${VERGABE_CLS[v.status] || ''}`}>{VERGABE_NAMEN[v.status] || v.status}</span></div>
            <div className="text-[13px]">Auftragssumme {fmtGeld(v.summe_netto)} netto{v.mitgeteilt_at ? ` · mitgeteilt ${fmtTag(v.mitgeteilt_at.slice(0, 10))}` : ''}</div>
            <div className="flex flex-wrap gap-2">{v.status === 'mitgeteilt' && <Link to={`/ausschreibungen/${v.ausschreibung_id}`}><Btn size="sm"><BadgeCheck size={14} /> Annahme bestätigen</Btn></Link>}{v.lokales_project_id && <Link to={`/projekte/${v.lokales_project_id}`}><Btn size="sm" variant="soft">Zur Baustelle</Btn></Link>}</div>
          </Card>
        ))}</div>)}

      {tab === 'eigene' && (
        <div className="space-y-5">
          {ue.vergaben_eigene.length > 0 && (
            <Card className="p-4 space-y-2"><h2 className="text-[15px] flex items-center gap-2"><Gavel size={15} /> Laufende Vergaben</h2>
              <ul className="divide-y divide-black/[0.06] text-[13px]">{ue.vergaben_eigene.map((v) => <li key={v.id} className="py-2 flex flex-wrap items-center gap-2"><Link to={`/ausschreibungen/${v.ausschreibung_id}`} className="font-medium flex-1 min-w-[200px]">{v.ausschreibung.titel} → {v.firma_name}</Link><span>{fmtGeld(v.summe_netto)}</span><span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${VERGABE_CLS[v.status] || ''}`}>{VERGABE_NAMEN[v.status]}</span></li>)}</ul>
            </Card>
          )}
          {ue.eigene.length === 0 ? <Card><Empty icon={Megaphone} title="Noch keine eigenen Ausschreibungen" text="Ausschreibungen werden im Projekt angelegt: Projekt öffnen → Reiter „Ausschreibungen“ → Neue Ausschreibung." /></Card>
            : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{ue.eigene.map((a) => <Karte key={a.id} a={a} extra={a.zaehler ? <span className="text-[12px] text-[#6E6E73]">{a.zaehler.angebote} Angebote · {a.zaehler.in_pruefung} in Prüfung · {a.zaehler.rueckfragen} Rückfragen · {a.zaehler.einladungen} eingeladen</span> : null} />)}</div>}
        </div>
      )}
    </Layout>
  );
}
