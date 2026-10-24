import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Timer, Users, FolderKanban, Receipt, CalendarOff, Plus, UserPlus, ChevronRight, Clock, AlertTriangle, Gauge, Lock, Gavel, Megaphone, Inbox, MessageCircleQuestion, BadgeCheck, Building2, BadgeEuro, ClipboardList, FileText, Calculator, BellRing } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import ProjectDialog from '../components/ProjectDialog';
import MitarbeiterDialog from '../components/MitarbeiterDialog';
import { AppIcon, Btn, Card, Sheet } from '../components/ui';
import { OffenePunkte } from './MitteilungenPage';
import { fmtGeld } from '../components/AbosKarte';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDecimalHours, fmtEur, fmtHours, MONTHS_DE, fmtDate, fromKey, toKey, monthLastDay } from '../lib/dates';
import { initials } from '../lib/utils';

function Kachel({ icon: Icon, label, value, sub, to, onClick, accent, warn }) {
  const inner = (
    <Card className={`p-5 h-full flex flex-col gap-2 transition-all hover:shadow-card-hover ${warn ? 'ring-1 ring-[#F59E0B]/50' : ''}`}>
      <div className="flex items-center justify-between text-[13px] text-[#6E6E73]"><span className="flex items-center gap-1.5"><Icon size={15} /> {label}</span>{(to || onClick) && <ChevronRight size={16} className="text-[#C7C7CC]" />}</div>
      <div className={`text-[28px] font-bold tracking-tight leading-none ${accent ? 'text-[#C41E3A]' : warn ? 'text-[#B25E00]' : ''}`}>{value}</div>
      {sub && <div className="text-[12px] text-[#86868B]">{sub}</div>}
    </Card>
  );
  if (to) return <Link to={to} className="block">{inner}</Link>;
  if (onClick) return <button type="button" onClick={onClick} className="block text-left w-full">{inner}</button>;
  return inner;
}

/** Startseite Auftraggeber / Projektleiter: Freigaben, Fristen und Rückfragen zuerst, dann Bauprojekte mit Firmen und Baufortschritt, dann Projektabos. */
function GuBlock({ gu, abos }) {
  const eigene = gu.a.eigene || [];
  const laufend = eigene.filter((a) => ['veroeffentlicht', 'in_vergabe'].includes(a.status));
  const fristen = laufend.filter((a) => a.frist_tage !== null && a.frist_tage >= 0 && a.frist_tage <= 3).length;
  const neu = laufend.reduce((s, a) => s + (a.zaehler?.neu || 0), 0);
  const inPruefung = laufend.reduce((s, a) => s + (a.zaehler?.in_pruefung || 0), 0);
  const fragen = laufend.reduce((s, a) => s + (a.zaehler?.fragen_offen || 0), 0);
  const vergaben = gu.a.vergaben_eigene || [];
  const projekte = gu.p.projekte || [];
  const entscheidungen = vergaben.filter((v) => v.status === 'vorgeschlagen').length + fragen + neu;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kachel icon={BadgeCheck} label="Offene Entscheidungen" value={entscheidungen} sub={`${vergaben.filter((v) => v.status === 'vorgeschlagen').length} Vergaben freigeben · ${neu} neue Angebote · ${fragen} Rückfragen`} to="/ausschreibungen" accent={entscheidungen > 0} />
        <Kachel icon={Megaphone} label="Laufende Ausschreibungen" value={laufend.length} sub={fristen ? `${fristen} mit Frist in den nächsten 3 Tagen` : `${eigene.length - laufend.length} Entwürfe/abgeschlossen`} to="/ausschreibungen" warn={fristen > 0} />
        <Kachel icon={Building2} label="Bauprojekte mit Firmen" value={projekte.length} sub={gu.p.einladungen?.length ? `${gu.p.einladungen.length} offene Einladungen` : `${projekte.reduce((s, p) => s + p.firmen, 0)} beteiligte Firmen`} to="/projekte" />
        <Kachel icon={BadgeEuro} label="Aktive GU-Projekte" value={abos ? abos.gu_projekte_aktiv : '–'} sub={abos ? `${fmtGeld(abos.kosten_projekte_monat)} netto je Monat` : ''} to="/abos" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h2 className="text-[17px] flex items-center gap-2"><Gavel size={17} /> Ausschreibungen</h2><Link to="/ausschreibungen" className="text-[13px] text-[#C41E3A] font-medium">Alle</Link></div>
          {laufend.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Keine laufende Ausschreibung. Ausschreibungen werden im Bauprojekt unter „Ausschreibungen“ angelegt.</p> : (
            <ul className="divide-y divide-black/[0.06]">
              {laufend.slice(0, 6).map((a) => (
                <li key={a.id} className="py-2 flex items-center gap-3 text-[14px]">
                  <Link to={`/ausschreibungen/${a.id}`} className="flex-1 min-w-0"><span className="block font-medium truncate">{a.titel}{a.projekt?.name ? ` – ${a.projekt.name}` : ''}</span><span className="block text-[12px] text-[#6E6E73]">{a.zaehler?.angebote || 0} Angebote{a.zaehler?.neu ? ` (${a.zaehler.neu} neu)` : ''} · {a.zaehler?.einladungen || 0} eingeladen · Frist {a.angebotsfrist ? fmtDate(fromKey(a.angebotsfrist)) : '–'}{a.frist_tage !== null && a.frist_tage >= 0 ? ` (noch ${a.frist_tage} Tage)` : ''}</span></Link>
                  {a.zaehler?.neu ? <span className="text-[11px] font-semibold rounded-full bg-[#C41E3A] text-white px-2 py-0.5"><Inbox size={11} className="inline mr-1" />{a.zaehler.neu}</span> : null}
                  {a.zaehler?.fragen_offen ? <span className="text-[11px] font-semibold rounded-full bg-[#FFF4E5] text-[#B25E00] px-2 py-0.5"><MessageCircleQuestion size={11} className="inline mr-1" />{a.zaehler.fragen_offen}</span> : null}
                  <ChevronRight size={16} className="text-[#C7C7CC]" />
                </li>
              ))}
            </ul>
          )}
          {inPruefung > 0 && <p className="text-[12px] text-[#86868B] mt-2">{inPruefung} Angebote in Prüfung.</p>}
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h2 className="text-[17px] flex items-center gap-2"><Building2 size={17} /> Bauprojekte und Baufortschritt</h2><Link to="/zusammenarbeit" className="text-[13px] text-[#C41E3A] font-medium">Zusammenarbeit</Link></div>
          {projekte.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch kein Bauprojekt mit beteiligten Firmen. Lege ein Bauprojekt an und lade unter „Firmen“ Gewerke ein oder schreibe sie aus.</p> : (
            <ul className="divide-y divide-black/[0.06]">
              {projekte.slice(0, 6).map((p) => (
                <li key={p.id}><Link to={`/projekte/${p.id}`} className="py-2 flex items-center gap-3 text-[14px]">
                  <AppIcon color={p.color} text={initials(p.name)} size={36} className="rounded-xl" />
                  <span className="flex-1 min-w-0"><span className="block font-medium truncate">{p.name}</span><span className="block text-[12px] text-[#6E6E73] truncate">{p.firmen} Firmen{p.eingeladen ? ` (+${p.eingeladen} eingeladen)` : ''} · {p.aufgaben_offen} Aufgaben offen{p.aufgaben_heute ? ` (${p.aufgaben_heute} heute)` : ''} · {p.maengel_offen} Mängel{p.berichte_offen ? ` · ${p.berichte_offen} Berichte freigeben` : ''}{p.lieferungen_heute ? ` · ${p.lieferungen_heute} Lieferungen heute` : ''}</span></span>
                  <ChevronRight size={16} className="text-[#C7C7CC]" />
                </Link></li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

/** Startseite Handwerksbetrieb: eigene Projekte, Team, Stunden und Rechnungen – mit Hinweisen (ArbZG, Budgets, vergessene Stempelungen, Abschluss). */
function BetriebBlock({ d, firma, heute, navigate, onWarnungen, onBeenden }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kachel icon={Timer} label="Gerade im Einsatz" value={d.gestempelt} sub={`${d.heute_eintraege} Einträge heute`} to="/stempeluhr" accent={d.gestempelt > 0} />
        <Kachel icon={Clock} label={`Stunden ${MONTHS_DE[heute.getMonth()]}`} value={fmtDecimalHours(d.monat.minuten)} sub={`≈ ${fmtEur(d.monat.umsatz_netto)} netto`} to="/auswertung" />
        {firma?.art !== 'auftraggeber' && <Kachel icon={Receipt} label="Offene Rechnungen" value={d.rechnungen_offen.anzahl} sub={fmtEur(d.rechnungen_offen.summe)} to="/rechnungen" />}
        {d.zahlungen_ueberfaellig && <Kachel icon={BellRing} label="Überfällige Zahlungen" value={d.zahlungen_ueberfaellig.anzahl} sub={d.zahlungen_ueberfaellig.anzahl ? `${fmtEur(d.zahlungen_ueberfaellig.summe)} · ${d.zahlungen_ueberfaellig.mahnungen_faellig} Mahnschritt${d.zahlungen_ueberfaellig.mahnungen_faellig === 1 ? '' : 'e'} fällig` : 'alles im Zahlungsziel'} to="/mahnwesen" warn={d.zahlungen_ueberfaellig.anzahl > 0} />}
        {d.kostenabweichungen && <Kachel icon={Calculator} label="Projekte mit Kostenabweichung" value={d.kostenabweichungen.anzahl} sub={d.kostenabweichungen.liste?.[0] ? `${d.kostenabweichungen.liste[0].name}` : `${d.kostenabweichungen.projekte} Projekte mit Auftragswert`} to="/nachkalkulation" warn={d.kostenabweichungen.anzahl > 0} />}
        {d.angebote_offen && <Kachel icon={FileText} label="Offene Angebote" value={d.angebote_offen.anzahl} sub={d.angebote_offen.anfragen ? `${fmtEur(d.angebote_offen.summe)} · ${d.angebote_offen.anfragen} neue Anfrage${d.angebote_offen.anfragen === 1 ? '' : 'n'}` : d.angebote_offen.ablaufend ? `${fmtEur(d.angebote_offen.summe)} · ${d.angebote_offen.ablaufend} laufen bald ab` : `${fmtEur(d.angebote_offen.summe)} netto`} to="/angebote" accent={d.angebote_offen.anfragen > 0} warn={d.angebote_offen.ablaufend > 0} />}
        <Kachel icon={CalendarOff} label="Offene Anträge" value={d.antraege_offen} sub={d.abwesend_heute.length ? `${d.abwesend_heute.length} heute abwesend` : 'niemand abwesend'} to="/abwesenheiten" accent={d.antraege_offen > 0} />
        <Kachel icon={AlertTriangle} label="ArbZG-Hinweise im Monat" value={d.arbzg_warnungen} sub={d.arbzg_warnungen ? 'Tage mit Verstoß-Hinweis' : 'alles im Rahmen'} onClick={onWarnungen} warn={d.arbzg_warnungen > 0} />
        <Kachel icon={Gauge} label="Budget-Warnungen" value={d.budget_warnungen.length} sub={d.budget_warnungen[0] ? `${d.budget_warnungen[0].name}: ${d.budget_warnungen[0].prozent} %` : 'kein Objekt über der Grenze'} to="/projekte" warn={d.budget_warnungen.length > 0} />
        <Kachel icon={Timer} label="Vergessen auszustempeln" value={d.lange_stempelungen.length} sub={d.lange_stempelungen[0] ? `${d.lange_stempelungen[0].user_name} seit ${fmtHours(d.lange_stempelungen[0].minuten)}` : 'niemand über 10 h'} to="/stempeluhr" warn={d.lange_stempelungen.length > 0} />
        <Kachel icon={Lock} label={`Abschluss ${MONTHS_DE[d.vormonat.monat - 1]}`} value={d.vormonat.abgeschlossen ? 'erledigt' : 'offen'} sub={d.vormonat.abgeschlossen ? 'Zeiten gesperrt' : 'nach dem Lohnlauf abschließen'} to="/exporte" warn={!d.vormonat.abgeschlossen} />
      </div>
      {d.lange_stempelungen.length > 0 && (
        <Card className="p-4 border border-[#F59E0B]/40">
          <div className="font-semibold text-[14px] flex items-center gap-2 mb-2"><AlertTriangle size={16} className="text-[#B25E00]" /> Laufende Stempelungen über 10 Stunden</div>
          <ul className="divide-y divide-black/[0.06] text-[14px]">{d.lange_stempelungen.map((s) => <li key={s.id} className="py-2 flex items-center justify-between gap-2"><span>{s.user_name} · {s.project_name} · seit {fmtHours(s.minuten)}</span><Btn size="sm" variant="soft" onClick={() => onBeenden(s)}>Jetzt beenden</Btn></li>)}</ul>
        </Card>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h2 className="text-[17px]">Zuletzt aktive Projekte</h2><Link to="/projekte" className="text-[13px] text-[#C41E3A] font-medium">Alle ({d.projekte_aktiv})</Link></div>
          {d.letzte_projekte.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch keine Projekte. Lege das erste Objekt an.</p> : (
            <ul className="divide-y divide-black/[0.06]">
              {d.letzte_projekte.map((p) => {
                const b = d.budget_warnungen.find((x) => x.project_id === p.id);
                return (
                  <li key={p.id} role="button" tabIndex={0} onClick={() => navigate(`/projekte/${p.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/projekte/${p.id}`)} className="py-2.5 flex items-center gap-3 cursor-pointer">
                    <AppIcon color={p.color} text={initials(p.name)} size={40} className="rounded-xl" />
                    <div className="flex-1 min-w-0"><div className="font-semibold text-[15px] truncate">{p.name}{p.verknuepft && <span className="ml-2 text-[11px] font-medium text-[#1D4ED8] bg-[#E8F0FE] rounded-full px-2 py-0.5">Auftrag von {p.verknuepft.owner_firma_name}</span>}{b && <span className="ml-2 text-[11px] font-medium text-[#B25E00] bg-[#FFF4E5] rounded-full px-2 py-0.5">Budget {b.prozent} %</span>}</div><div className="text-[12px] text-[#6E6E73] truncate">{p.customer_name || 'Kein Auftraggeber'} · {fmtDecimalHours(p.total_minutes)} Std.{p.last_activity_at ? ` · zuletzt ${fmtDate(fromKey(p.last_activity_at))}` : ''}</div></div>
                    <ChevronRight size={18} className="text-[#C7C7CC]" />
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
        <div className="space-y-4">
          <Card className="p-5">
            <h2 className="text-[17px] mb-2 flex items-center gap-2"><Users size={17} /> Team</h2>
            <div className="text-[14px] text-[#6E6E73]">{d.mitarbeiter_aktiv} aktive Konten</div>
            {d.abwesend_heute.length > 0 && <ul className="mt-2 text-[13px] space-y-1">{d.abwesend_heute.map((a, i) => <li key={i} className="flex justify-between"><span>{a.user_name}</span><span className="text-[#6E6E73]">{a.type} bis {fmtDate(fromKey(a.to_date))}</span></li>)}</ul>}
            <Btn variant="soft" size="sm" className="mt-3 w-full" onClick={() => navigate('/mitarbeiter')}><Users size={15} /> Mitarbeiter verwalten</Btn>
          </Card>
          <Card className="p-5">
            <h2 className="text-[17px] mb-2 flex items-center gap-2"><FolderKanban size={17} /> Schnell erledigt</h2>
            <div className="flex flex-col gap-2">
              <Btn variant="soft" size="sm" onClick={() => navigate('/plantafel')}><ClipboardList size={15} /> Plantafel: Mitarbeiter einteilen</Btn>
              <Btn variant="soft" size="sm" onClick={() => navigate('/angebote?neu=1')}><FileText size={15} /> Angebot erstellen</Btn>
              <Btn variant="soft" size="sm" onClick={() => navigate('/stempeluhr')}><Timer size={15} /> Selbst stempeln</Btn>
              <Btn variant="soft" size="sm" onClick={() => navigate('/ausschreibungen')}><Gavel size={15} /> Aufträge finden &amp; Angebote</Btn>
              <Btn variant="soft" size="sm" onClick={() => navigate('/exporte')}>Lohnexport, Abschluss &amp; Archiv</Btn>
              <Btn variant="soft" size="sm" onClick={() => navigate('/auswertung')}>Auswertung &amp; Stundenkonten</Btn>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/** Team-Karte für reine Auftraggeber (ohne Stundenzettel-Kennzahlen). */
function TeamKarte({ d, navigate }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Kachel icon={Users} label="Aktive Konten" value={d.mitarbeiter_aktiv} sub="Projektleiter und Mitarbeiter" to="/projektleiter" />
      <Kachel icon={Timer} label="Gerade im Einsatz" value={d.gestempelt} sub={`${d.heute_eintraege} Einträge heute`} to="/stempeluhr" />
      <Kachel icon={CalendarOff} label="Offene Anträge" value={d.antraege_offen} sub={d.abwesend_heute.length ? `${d.abwesend_heute.length} heute abwesend` : 'niemand abwesend'} to="/abwesenheiten" accent={d.antraege_offen > 0} />
      <Kachel icon={ClipboardList} label="Aufgaben" value="Übersicht" sub="Aufgaben und Abnahmen aller Bauprojekte" onClick={() => navigate('/aufgaben')} />
    </div>
  );
}

export default function DashboardPage() {
  const { firma } = useAuth();
  const navigate = useNavigate();
  const art = firma?.art || 'betrieb';
  const gu = art !== 'betrieb';
  const betrieb = art !== 'auftraggeber';
  const [d, setD] = useState(null);
  const [punkte, setPunkte] = useState(null);
  const [guDaten, setGuDaten] = useState(null);
  const [abos, setAbos] = useState(null);
  const [projektDialog, setProjektDialog] = useState(false);
  const [maDialog, setMaDialog] = useState(false);
  const [warnungen, setWarnungen] = useState(null);
  const laden = () => {
    api.get('/api/dashboard').then(setD).catch((err) => toast.error(err.message));
    api.get('/api/dashboard/aufgaben').then((r) => setPunkte(r.punkte)).catch(() => setPunkte([]));
    if (gu) {
      Promise.all([api.get('/api/ausschreibungen/uebersicht'), api.get('/api/plattform/uebersicht')]).then(([a, p]) => setGuDaten({ a, p })).catch(() => setGuDaten(null));
      api.get('/api/firma/abos').then(setAbos).catch(() => setAbos(null));
    }
  };
  useEffect(() => { laden(); }, [gu]);   // eslint-disable-line react-hooks/exhaustive-deps
  const heute = new Date();
  const warnungenZeigen = async () => {
    try { setWarnungen((await api.get(`/api/zeiten/warnungen?von=${toKey(new Date(heute.getFullYear(), heute.getMonth(), 1))}&bis=${toKey(monthLastDay(heute.getFullYear(), heute.getMonth()))}`)).tage); }
    catch (err) { toast.error(err.message); }
  };
  const beenden = async (s) => {
    if (!window.confirm(`Stempelung von ${s.user_name} jetzt beenden?`)) return;
    try { await api.post(`/api/stempel/${s.id}/beenden`, { activity: 'vom Büro beendet' }); toast.success('Beendet'); laden(); } catch (err) { toast.error(err.message); }
  };

  return (
    <Layout title={`Hallo, ${firma?.owner?.split(' ')[0] || firma?.name || ''}`} subtitle={`${fmtDate(heute)} · ${MONTHS_DE[heute.getMonth()]} ${heute.getFullYear()}${art === 'auftraggeber' ? ' · Auftraggeber' : art === 'beides' ? ' · Betrieb und Auftraggeber' : ''}`}
      action={<div className="flex gap-2"><Btn variant="soft" size="sm" onClick={() => setMaDialog(true)}><UserPlus size={16} /> Einladen</Btn><Btn size="sm" onClick={() => setProjektDialog(true)}><Plus size={16} /> {gu ? 'Bauprojekt' : 'Projekt'}</Btn></div>}>
      {!d ? <Ladeanzeige /> : (
        <div className="space-y-5">
          <OffenePunkte punkte={punkte} titel={gu ? 'Freigaben, Fristen und Rückfragen' : 'Jetzt zu erledigen'} />
          {gu && guDaten && <GuBlock gu={guDaten} abos={abos} />}
          {betrieb ? <BetriebBlock d={d} firma={firma} heute={heute} navigate={navigate} onWarnungen={warnungenZeigen} onBeenden={beenden} /> : <TeamKarte d={d} navigate={navigate} />}
        </div>
      )}
      <ProjectDialog open={projektDialog} onOpenChange={setProjektDialog} project={null} defaultRate={firma?.default_hourly_rate || 0} onSaved={(p) => navigate(`/projekte/${p.id}`)} />
      <MitarbeiterDialog open={maDialog} onOpenChange={setMaDialog} onSaved={laden} />
      <Sheet open={!!warnungen} onOpenChange={(o) => { if (!o) setWarnungen(null); }} title="ArbZG-Hinweise" subtitle={`${MONTHS_DE[heute.getMonth()]} ${heute.getFullYear()} · Hinweise, keine Sperre. Prüfen und ggf. mit dem Mitarbeiter klären.`}>
        {warnungen?.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Keine Hinweise in diesem Monat.</p> : (
          <ul className="divide-y divide-black/[0.06] text-[14px]">{(warnungen || []).map((t) => <li key={`${t.user_id}-${t.date}`} className="py-2.5"><div className="font-semibold">{t.user_name || 'Ohne Person'} · {fmtDate(fromKey(t.date))} · {fmtHours(t.minuten)}</div><ul className="text-[13px] text-[#B25E00] mt-0.5 space-y-0.5">{t.warnungen.map((w) => <li key={w.code}>⚠ {w.text}</li>)}</ul></li>)}</ul>
        )}
      </Sheet>
    </Layout>
  );
}
