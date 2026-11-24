import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Bell, CalendarRange, Check, CheckCircle2, Clock, MapPin, Navigation, Play, Users } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { AppIcon, Btn, Card, Empty } from '../components/ui';
import { api } from '../lib/api';
import { fmtDate, fromKey, WEEKDAYS_LONG_DE } from '../lib/dates';
import { initials } from '../lib/utils';

const ABGLEICH_CLS = { freigegeben: 'bg-[#E8F8EC] text-[#1B7F3B]', passt: 'bg-[#E8F8EC] text-[#1B7F3B]', abweichung: 'bg-[#FFF4E5] text-[#B25E00]', fehlt: 'bg-[#FDE8E8] text-[#C41E3A]', offen: 'bg-black/[0.06] text-[#6E6E73]' };
const tagText = (key) => `${WEEKDAYS_LONG_DE[fromKey(key).getDay() === 0 ? 6 : fromKey(key).getDay() - 1]}, ${fmtDate(fromKey(key))}`;

/** Eine Einsatzkarte: Projekt, Zeit, Adresse mit Navigation, Hinweise, Kolonne – und die passenden Aktionen für den Tag. */
export function EinsatzKarte({ e: start, heute, kompakt = false }) {
  const navigate = useNavigate();
  const [e, setE] = useState(start);
  const [sendet, setSendet] = useState(false);
  useEffect(() => setE(start), [start]);
  const istHeute = e.date === heute;
  const vergangen = e.date < heute;
  const q = e.quittung || {};
  // Lesebestätigung (wie in der iPhone-App): gilt für die aktuelle Version, nach einer Planänderung wieder offen
  const bestaetigen = async () => {
    setSendet(true);
    try { setE((await api.post(`/api/einsatzplan/${e.id}/bestaetigen`)).einsatz); toast.success('Einsatz bestätigt'); }
    catch (err) { toast.error(err.message); }
    finally { setSendet(false); }
  };
  return (
    <Card className={`p-4 ${istHeute ? 'ring-2 ring-[#C41E3A]/40' : ''}`}>
      <div className="flex items-start gap-3">
        <AppIcon color={e.projekt?.color || '#C41E3A'} text={initials(e.projekt?.name)} size={40} className="rounded-xl shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-[12px] text-[#6E6E73]">{tagText(e.date)}{e.kolonne ? ` · Kolonne ${e.kolonne}` : ''}</div>
          <div className="font-semibold text-[16px] leading-tight truncate">{e.projekt?.name}</div>
          <div className="text-[14px] mt-1 flex items-center gap-1.5"><Clock size={14} className="text-[#6E6E73]" /> {e.start_time}–{e.end_time} Uhr{e.pause_minutes ? ` · ${e.pause_minutes} Min. Pause` : ''}{e.planned_minutes ? ` · ${(e.planned_minutes / 60).toFixed(2).replace('.', ',')} h` : ''}</div>
          {e.projekt?.address && <div className="text-[13px] text-[#6E6E73] mt-0.5 flex items-center gap-1.5"><MapPin size={14} /> {e.projekt.address}</div>}
          {e.taetigkeit && <div className="text-[13px] mt-1"><span className="text-[#6E6E73]">Tätigkeit:</span> {e.taetigkeit}</div>}
          {e.note && <div className="text-[13px] mt-0.5"><span className="text-[#6E6E73]">Hinweis vom Büro:</span> {e.note}</div>}
          {e.kollegen?.length > 0 && <div className="text-[12px] text-[#6E6E73] mt-0.5 flex items-center gap-1"><Users size={12} /> mit {e.kollegen.join(', ')}</div>}
          {vergangen && e.abgleich && <span className={`inline-block mt-1.5 text-[11px] font-semibold rounded-full px-2 py-0.5 ${ABGLEICH_CLS[e.abgleich.status] || ''}`}>{e.abgleich.status_name}</span>}
        </div>
      </div>
      {!kompakt && !vergangen && e.status === 'geplant' && (
        q.bestaetigt
          ? <div className="mt-3 flex items-center gap-1.5 text-[13px] font-semibold text-[#1B7F3B]"><CheckCircle2 size={16} /> Bestätigt</div>
          : <Btn className="mt-3 w-full" onClick={bestaetigen} disabled={sendet}><Check size={16} /> Gelesen & bestätigt</Btn>
      )}
      {!kompakt && (
        <div className="mt-3 flex flex-wrap gap-2">
          {e.navigation && <a href={e.navigation} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-full bg-[#1D1D1F] text-white text-[13px] font-semibold"><Navigation size={14} /> Navigation</a>}
          {istHeute && !vergangen && <Btn size="sm" onClick={() => navigate(`/stempeln/${e.project_id}`)}><Play size={14} /> Einstempeln</Btn>}
          <Btn size="sm" variant="soft" onClick={() => navigate(`/projekte/${e.project_id}`)}>Projekt öffnen</Btn>
          {vergangen && <Btn size="sm" variant="ghost" onClick={() => navigate('/meine-zeiten')}>Meine Zeiten</Btn>}
        </div>
      )}
    </Card>
  );
}

function Abschnitt({ titel, liste, heute, leer }) {
  return (
    <section>
      <h2 className="text-[17px] mb-2">{titel}{liste.length ? <span className="text-[#6E6E73] font-normal"> · {liste.length}</span> : null}</h2>
      {liste.length === 0 ? <p className="text-[14px] text-[#6E6E73] mb-2">{leer}</p> : <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">{liste.map((e) => <EinsatzKarte key={e.id} e={e} heute={heute} />)}</div>}
    </section>
  );
}

/** Mein Einsatzplan (Mitarbeiter und Vorarbeiter): heute, morgen, diese Woche, nächste Woche – nie die Einsätze anderer. */
export default function MeinEinsatzplanPage() {
  const [d, setD] = useState(null);
  // Aus einer Push-Nachricht geöffnet: /einsaetze?einsatz=<id> → genau diesen Einsatz oben zeigen
  const [params] = useSearchParams();
  const zielId = params.get('einsatz');
  const [ziel, setZiel] = useState(null);
  useEffect(() => {
    if (!zielId) { setZiel(null); return; }
    api.get(`/api/einsatzplan/${encodeURIComponent(zielId)}`).then(async (r) => {
      let e = r.einsatz;
      if (e.status === 'geplant' && !e.quittung?.gelesen) e = (await api.post(`/api/einsatzplan/${e.id}/gelesen`).catch(() => r)).einsatz;
      setZiel(e);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }).catch((err) => toast.error(err.message));
  }, [zielId]);
  const [erinnerung, setErinnerung] = useState(null);
  const laden = useCallback(() => {
    api.get('/api/einsatzplan/meine?tage=28').then(setD).catch((err) => toast.error(err.message));
    const h = new Date().toISOString().slice(0, 10);
    api.get(`/api/einsatzplan?von=${h}&bis=${h}`).then((r) => setErinnerung(r.erinnerung)).catch(() => {});
  }, []);
  useEffect(() => { laden(); }, [laden]);
  // Angesehene kommende Einsätze als „gelesen“ melden (einmal je Version; der Chef sieht zugestellt → gelesen → bestätigt)
  useEffect(() => {
    if (!d) return;
    const tag = new Date().toISOString().slice(0, 10);
    [...d.heute, ...d.morgen, ...d.woche, ...d.naechste_woche]
      .filter((e, i, alle) => e.date >= tag && e.status === 'geplant' && !e.quittung?.gelesen && alle.findIndex((x) => x.id === e.id) === i)
      .forEach((e) => api.post(`/api/einsatzplan/${e.id}/gelesen`).catch(() => {}));
  }, [d]);
  if (!d) return <Layout title="Meine Einsätze"><Ladeanzeige /></Layout>;
  const heute = new Date().toISOString().slice(0, 10);
  const nichts = !d.heute.length && !d.morgen.length && !d.woche.length && !d.naechste_woche.length && !d.spaeter.length;
  return (
    <Layout title="Meine Einsätze" subtitle="Wo du wann eingeplant bist – mit Adresse, Zeiten und Hinweisen vom Büro. Zeiten anderer Mitarbeiter siehst du hier nie.">
      {erinnerung && <p className="text-[13px] text-[#6E6E73] mb-4 flex items-center gap-1.5"><Bell size={14} /> Jeden Abend um {erinnerung.uhrzeit} Uhr bekommst du eine Erinnerung für den nächsten Tag{erinnerung.email ? ' (in der App und per E-Mail)' : ' (in der App)'}.</p>}
      {nichts && !ziel ? <Card><Empty icon={CalendarRange} title="Noch nichts eingeplant" text="Sobald das Büro dich einteilt, stehen deine Einsätze hier." /></Card> : (
        <div className="space-y-6">
          {ziel && (
            <section>
              <h2 className="text-[17px] mb-2">Aus der Benachrichtigung{ziel.status === 'abgesagt' ? ' · abgesagt' : ''}</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3"><EinsatzKarte e={ziel} heute={heute} /></div>
            </section>
          )}
          <Abschnitt titel="Heute" liste={d.heute} heute={heute} leer="Heute kein Einsatz geplant." />
          <Abschnitt titel="Morgen" liste={d.morgen} heute={heute} leer="Morgen kein Einsatz geplant." />
          <Abschnitt titel="Diese Woche" liste={d.woche.filter((e) => e.date > heute && !d.morgen.some((m) => m.id === e.id))} heute={heute} leer="Keine weiteren Einsätze in dieser Woche." />
          <Abschnitt titel="Nächste Woche" liste={d.naechste_woche} heute={heute} leer="Nächste Woche noch nichts geplant." />
          {d.spaeter.length > 0 && <Abschnitt titel="Später" liste={d.spaeter} heute={heute} leer="" />}
          {d.vergangen.length > 0 && (
            <section>
              <h2 className="text-[17px] mb-2">Letzte Tage</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">{d.vergangen.slice(-6).reverse().map((e) => <EinsatzKarte key={e.id} e={e} heute={heute} kompakt />)}</div>
              <p className="text-[12px] text-[#86868B] mt-2">„Weicht vom Plan ab“ ist nur ein Hinweis für die Prüfung durch das Büro, kein Vorwurf. <Link to="/meine-zeiten" className="text-[#C41E3A] font-medium">Meine Zeiten</Link></p>
            </section>
          )}
        </div>
      )}
    </Layout>
  );
}
