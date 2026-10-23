import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, FileText, Timer, Clock } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige, Warnungen } from '../components/Layout';
import EntryDialog from '../components/EntryDialog';
import { Btn, Card, IconBtn, Select } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { MONTHS_DE, WEEKDAYS_LONG_DE, clampMonth, fmtDate, fmtHours, fmtDecimalHours, fmtSigned, fromKey, monthLastDay, toKey, MIN_YEAR, MAX_YEAR } from '../lib/dates';
import { milogPdf } from '../lib/pdf';
import { deliverPdf } from '../lib/utils';

const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);

/** Mitarbeiter: eigene Zeiten je Monat, Soll/Ist, antippen zum Ändern, Arbeitszeitnachweis als PDF. */
export default function MeineZeitenPage() {
  const { user } = useAuth();
  const today = new Date();
  const [{ year, month }, setYm] = useState(clampMonth(today.getFullYear(), today.getMonth()));
  const [eintraege, setEintraege] = useState(null);
  const [konto, setKonto] = useState(null);
  const [auswahl, setAuswahl] = useState(null); // {project_id, date}
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => {
    api.get(`/api/zeiten/meine?von=${toKey(new Date(year, month, 1))}&bis=${toKey(monthLastDay(year, month))}`).then((r) => setEintraege(r.eintraege)).catch((err) => toast.error(err.message));
    if (user?.id) api.get(`/api/mitarbeiter/${user.id}/konto?jahr=${year}&monat=${month + 1}`).then(setKonto).catch(() => {});
  }, [year, month, user?.id]);
  useEffect(() => { setEintraege(null); laden(); }, [laden]);

  const tage = useMemo(() => { const m = {}; for (const e of eintraege || []) (m[e.date] ||= []).push(e); return Object.entries(m).sort((a, b) => b[0].localeCompare(a[0])); }, [eintraege]);
  const summe = (eintraege || []).reduce((s, e) => s + (e.net_minutes || 0), 0);
  const prev = () => setYm(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 });
  const next = () => setYm(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 });
  const nachweis = async () => {
    setBusy(true);
    try { const d = await api.get(`/api/exporte/milog?jahr=${year}&monat=${month + 1}&user_id=${user.id}`); await deliverPdf(milogPdf(d.firma, d.mitarbeiter, year, month + 1, d.eintraege, d.abwesenheiten, d.feiertage || {})); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const tagEintraege = auswahl ? (eintraege || []).filter((e) => e.date === auswahl.date && e.project_id === auswahl.project_id) : [];
  const m = konto?.monat;

  return (
    <Layout title="Meine Zeiten" subtitle={`${fmtDecimalHours(summe)} Stunden in ${MONTHS_DE[month]}`} action={<Btn variant="soft" size="sm" onClick={nachweis} loading={busy}><FileText size={15} /> Nachweis PDF</Btn>}>
      <div className="flex items-center gap-1.5 mb-4">
        <IconBtn variant="soft" onClick={prev}><ChevronLeft size={18} /></IconBtn>
        <Select value={month} onChange={(e) => setYm({ year, month: Number(e.target.value) })}>{MONTHS_DE.map((mm, i) => <option key={mm} value={i}>{mm}</option>)}</Select>
        <Select value={year} onChange={(e) => setYm({ year: Number(e.target.value), month })}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select>
        <IconBtn variant="soft" onClick={next}><ChevronRight size={18} /></IconBtn>
      </div>
      {m && konto.mitarbeiter.weekly_hours > 0 && (
        <Card className="p-4 mb-4 grid grid-cols-3 divide-x divide-black/[0.06] text-center">
          <div><div className="text-[12px] text-[#6E6E73]">Soll</div><div className="text-[18px] font-bold">{fmtHours(m.soll_minuten)}</div></div>
          <div><div className="text-[12px] text-[#6E6E73]">Ist</div><div className="text-[18px] font-bold">{fmtHours(m.ist_minuten)}</div></div>
          <div><div className="text-[12px] text-[#6E6E73]">Saldo Monat</div><div className={`text-[18px] font-bold ${m.saldo_minuten < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{fmtSigned(m.saldo_minuten)}</div></div>
        </Card>
      )}
      {!eintraege ? <Ladeanzeige /> : tage.length === 0 ? <Card className="p-8 text-center text-[14px] text-[#6E6E73]">Keine Zeiten in diesem Monat. Stempel dich bei der Arbeit ein – oder trage im Projektkalender nach.</Card> : (
        <div className="space-y-3">
          {tage.map(([datum, liste]) => {
            const d = fromKey(datum);
            return (
              <Card key={datum} className="p-4">
                <div className="flex items-center justify-between mb-2"><div className="font-semibold text-[15px]">{WEEKDAYS_LONG_DE[(d.getDay() + 6) % 7]}, {fmtDate(d)}</div><div className="text-[#C41E3A] font-semibold">{fmtHours(liste.reduce((s, e) => s + (e.net_minutes || 0), 0))}</div></div>
                <ul className="divide-y divide-black/[0.06]">
                  {liste.map((e) => (
                    <li key={e.id}><button type="button" onClick={() => setAuswahl({ project_id: e.project_id, date: e.date })} className="w-full flex items-center gap-3 py-2 text-left">
                      <span className="w-9 h-9 rounded-xl flex items-center justify-center text-white" style={{ backgroundColor: e.project_color || '#C41E3A' }}>{e.source?.startsWith('stempel') ? <Timer size={16} /> : <Clock size={16} />}</span>
                      <span className="flex-1 min-w-0"><span className="block text-[14px] font-medium">{e.start_time} – {e.end_time}{e.pause_minutes ? ` · Pause ${e.pause_minutes} Min.` : ''}</span><span className="block text-[12px] text-[#6E6E73] truncate">{e.project_name}{e.service_name ? ` · ${e.service_name}` : ''}{e.activity ? ` · ${e.activity}` : ''}</span><Warnungen liste={e.warnungen} klein /></span>
                      <span className="text-[14px] font-semibold">{fmtHours(e.net_minutes)}</span>
                    </button></li>
                  ))}
                </ul>
              </Card>
            );
          })}
        </div>
      )}
      <EntryDialog open={!!auswahl} onOpenChange={(o) => { if (!o) setAuswahl(null); }} projectId={auswahl?.project_id} dateKey={auswahl?.date} entries={tagEintraege} lastEntry={tagEintraege[0] || null} onChanged={laden} />
    </Layout>
  );
}
