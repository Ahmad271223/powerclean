import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Timer, Users, FolderKanban, Receipt, CalendarOff, Plus, UserPlus, ChevronRight, Clock, AlertTriangle, Gauge, Lock } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import ProjectDialog from '../components/ProjectDialog';
import MitarbeiterDialog from '../components/MitarbeiterDialog';
import { AppIcon, Btn, Card, Sheet } from '../components/ui';
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

export default function DashboardPage() {
  const { firma } = useAuth();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [projektDialog, setProjektDialog] = useState(false);
  const [maDialog, setMaDialog] = useState(false);
  const [warnungen, setWarnungen] = useState(null);
  const laden = () => api.get('/api/dashboard').then(setD).catch((err) => toast.error(err.message));
  useEffect(() => { laden(); }, []);
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
    <Layout title={`Hallo, ${firma?.owner?.split(' ')[0] || firma?.name || ''}`} subtitle={`${fmtDate(heute)} · ${MONTHS_DE[heute.getMonth()]} ${heute.getFullYear()}`}
      action={<div className="flex gap-2"><Btn variant="soft" size="sm" onClick={() => setMaDialog(true)}><UserPlus size={16} /> Einladen</Btn><Btn size="sm" onClick={() => setProjektDialog(true)}><Plus size={16} /> Projekt</Btn></div>}>
      {!d ? <Ladeanzeige /> : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Kachel icon={Timer} label="Gerade im Einsatz" value={d.gestempelt} sub={`${d.heute_eintraege} Einträge heute`} to="/stempeluhr" accent={d.gestempelt > 0} />
            <Kachel icon={Clock} label={`Stunden ${MONTHS_DE[heute.getMonth()]}`} value={fmtDecimalHours(d.monat.minuten)} sub={`≈ ${fmtEur(d.monat.umsatz_netto)} netto`} to="/auswertung" />
            <Kachel icon={Receipt} label="Offene Rechnungen" value={d.rechnungen_offen.anzahl} sub={fmtEur(d.rechnungen_offen.summe)} to="/rechnungen" />
            <Kachel icon={CalendarOff} label="Offene Anträge" value={d.antraege_offen} sub={d.abwesend_heute.length ? `${d.abwesend_heute.length} heute abwesend` : 'niemand abwesend'} to="/abwesenheiten" accent={d.antraege_offen > 0} />
            <Kachel icon={AlertTriangle} label="ArbZG-Hinweise im Monat" value={d.arbzg_warnungen} sub={d.arbzg_warnungen ? 'Tage mit Verstoß-Hinweis' : 'alles im Rahmen'} onClick={warnungenZeigen} warn={d.arbzg_warnungen > 0} />
            <Kachel icon={Gauge} label="Budget-Warnungen" value={d.budget_warnungen.length} sub={d.budget_warnungen[0] ? `${d.budget_warnungen[0].name}: ${d.budget_warnungen[0].prozent} %` : 'kein Objekt über der Grenze'} to="/projekte" warn={d.budget_warnungen.length > 0} />
            <Kachel icon={Timer} label="Vergessen auszustempeln" value={d.lange_stempelungen.length} sub={d.lange_stempelungen[0] ? `${d.lange_stempelungen[0].user_name} seit ${fmtHours(d.lange_stempelungen[0].minuten)}` : 'niemand über 10 h'} to="/stempeluhr" warn={d.lange_stempelungen.length > 0} />
            <Kachel icon={Lock} label={`Abschluss ${MONTHS_DE[d.vormonat.monat - 1]}`} value={d.vormonat.abgeschlossen ? 'erledigt' : 'offen'} sub={d.vormonat.abgeschlossen ? 'Zeiten gesperrt' : 'nach dem Lohnlauf abschließen'} to="/exporte" warn={!d.vormonat.abgeschlossen} />
          </div>

          {d.lange_stempelungen.length > 0 && (
            <Card className="p-4 border border-[#F59E0B]/40">
              <div className="font-semibold text-[14px] flex items-center gap-2 mb-2"><AlertTriangle size={16} className="text-[#B25E00]" /> Laufende Stempelungen über 10 Stunden</div>
              <ul className="divide-y divide-black/[0.06] text-[14px]">{d.lange_stempelungen.map((s) => <li key={s.id} className="py-2 flex items-center justify-between gap-2"><span>{s.user_name} · {s.project_name} · seit {fmtHours(s.minuten)}</span><Btn size="sm" variant="soft" onClick={() => beenden(s)}>Jetzt beenden</Btn></li>)}</ul>
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
                        <div className="flex-1 min-w-0"><div className="font-semibold text-[15px] truncate">{p.name}{b && <span className="ml-2 text-[11px] font-medium text-[#B25E00] bg-[#FFF4E5] rounded-full px-2 py-0.5">Budget {b.prozent} %</span>}</div><div className="text-[12px] text-[#6E6E73] truncate">{p.customer_name || 'Kein Auftraggeber'} · {fmtDecimalHours(p.total_minutes)} Std.{p.last_activity_at ? ` · zuletzt ${fmtDate(fromKey(p.last_activity_at))}` : ''}</div></div>
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
                  <Btn variant="soft" size="sm" onClick={() => navigate('/stempeluhr')}><Timer size={15} /> Selbst stempeln</Btn>
                  <Btn variant="soft" size="sm" onClick={() => navigate('/exporte')}>Lohnexport &amp; Monatsabschluss</Btn>
                  <Btn variant="soft" size="sm" onClick={() => navigate('/auswertung')}>Auswertung &amp; Stundenkonten</Btn>
                  <Btn variant="soft" size="sm" onClick={() => navigate('/firma')}>Firmendaten, Leistungen, Stempel</Btn>
                </div>
              </Card>
            </div>
          </div>
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
