import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, ChevronLeft, ChevronRight, Settings2, FileText, Download, Loader2, Receipt, FileStack, RotateCcw, Archive } from 'lucide-react';
import ProjectDialog from '../components/ProjectDialog';
import EntryDialog from '../components/EntryDialog';
import { AppHeader, AppIcon, Btn, Card, IconBtn, Select } from '../components/ui';
import { useStore, useProjectEntries, projectInvoices, getOrCreateInvoice, updateInvoiceTotals, deleteInvoice } from '../lib/store';
import { weekPdf, monthPdf, invoicePdf, computeInvoice, preloadLogo } from '../lib/pdf';
import { MIN_YEAR, MAX_YEAR, MONTHS_DE, WEEKDAYS_DE, toKey, fromKey, addDays, isoWeek, monthWeeks, clampMonth, fmtHours, fmtDecimalHours, fmtEur, fmtDateShort, todayKey, monthLastDay, entryMinutes, entryWorkers } from '../lib/dates';
import { initials, deliverPdf } from '../lib/utils';

const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);

/** Calendar of ONE project: month grid, tap a day to enter working time. Entries are loaded per project. */
export default function CalendarPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { state, ready } = useStore();
  const today = useMemo(() => new Date(), []);
  const [{ year, month }, setYm] = useState(() => clampMonth(today.getFullYear(), today.getMonth()));
  const [selectedDate, setSelectedDate] = useState(null);
  const [projectDialog, setProjectDialog] = useState(false);
  const [busy, setBusy] = useState('');

  const project = state.projects.find((p) => p.id === projectId) || null;
  const company = project ? state.companies.find((c) => c.id === project.company_id) || null : null;
  useEffect(() => { if (ready && !project) navigate('/', { replace: true }); }, [ready, project, navigate]);
  useEffect(() => { if (company) preloadLogo(company); }, [company]);

  const { entries: allEntries, loaded } = useProjectEntries(project?.id);

  const weeks = useMemo(() => monthWeeks(year, month), [year, month]);
  const gridStartKey = toKey(weeks[0]);
  const gridEndKey = toKey(addDays(weeks[weeks.length - 1], 6));
  const entries = useMemo(() => allEntries.filter((e) => e.date >= gridStartKey && e.date <= gridEndKey), [allEntries, gridStartKey, gridEndKey]);

  const byDay = useMemo(() => {
    const map = {};
    for (const e of entries) (map[e.date] ||= []).push(e);
    return map;
  }, [entries]);

  const recentActivities = useMemo(() => {
    const seen = [];
    for (let i = allEntries.length - 1; i >= 0 && seen.length < 4; i--) {
      const a = (allEntries[i].activity || '').trim();
      if (a && !seen.includes(a)) seen.push(a);
    }
    return seen;
  }, [allEntries]);

  if (!ready || !project) return <div className="ts-app py-24 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={28} /></div>;

  const comp = company || { name: '', default_hourly_rate: 0 };
  const firstKey = toKey(new Date(year, month, 1));
  const lastKey = toKey(monthLastDay(year, month));
  const monthEntries = entries.filter((e) => e.date >= firstKey && e.date <= lastKey);
  const monthMinutes = monthEntries.reduce((s, e) => s + entryMinutes(e), 0);
  const monthDays = new Set(monthEntries.map((e) => e.date)).size;
  const rate = Number(project.hourly_rate) || Number(comp.default_hourly_rate) || 0;
  const invoice = projectInvoices(project.id).find((i) => i.year === year && i.month === month + 1);
  const lastEntry = allEntries[allEntries.length - 1] || null;

  const weekMinutes = (monday) => {
    const lo = toKey(monday);
    const hi = toKey(addDays(monday, 6));
    return entries.filter((e) => e.date >= lo && e.date <= hi).reduce((s, e) => s + entryMinutes(e), 0);
  };

  const canPrev = year > MIN_YEAR || month > 0;
  const canNext = year < MAX_YEAR || month < 11;
  const prev = () => canPrev && setYm(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 });
  const next = () => canNext && setYm(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 });
  const goToday = () => setYm(clampMonth(today.getFullYear(), today.getMonth()));

  /** PDFs are generated synchronously so the share sheet opens inside the tap gesture (iOS). */
  const deliver = (key, make, mode) => {
    let result;
    try { result = make(); } catch (err) { console.error(err); toast.error('PDF konnte nicht erstellt werden'); return; }
    setBusy(key);
    deliverPdf(result, mode).catch((err) => { console.error(err); toast.error('PDF konnte nicht weitergegeben werden'); }).finally(() => setBusy(''));
  };
  const weekDoc = (monday, mode) => deliver(`week-${toKey(monday)}`, () => weekPdf(project, comp, monday, entries.filter((e) => e.date >= toKey(monday) && e.date <= toKey(addDays(monday, 6)))), mode);
  const withInvoice = () => {
    const calc = computeInvoice(project, comp, year, month, monthEntries);
    const inv = getOrCreateInvoice(project, comp, year, month + 1, calc);
    return updateInvoiceTotals(inv.id, calc) || inv;
  };
  const monthDoc = (mode) => deliver('month', () => monthPdf(project, comp, year, month, entries, withInvoice()), mode);
  const invoiceDoc = (mode) => deliver('invoice', () => invoicePdf(project, comp, year, month, monthEntries, withInvoice()), mode);

  const resetInvoice = () => {
    if (!invoice) return;
    if (!window.confirm(`Rechnungsnummer ${invoice.number} zurücksetzen? Beim nächsten PDF wird eine neue Nummer mit aktuellem Datum vergeben.`)) return;
    deleteInvoice(invoice.id);
    toast.success('Rechnungsnummer zurückgesetzt');
  };

  const tKey = todayKey();
  const color = project.color || '#C41E3A';
  const backTo = `/firma/${project.company_id}`;

  return (
    <div className="ts-app">
      <AppHeader
        left={(
          <>
            <IconBtn onClick={() => navigate(backTo)} title="Zurück zu den Projekten"><ArrowLeft size={20} /></IconBtn>
            <AppIcon color={color} text={initials(project.name)} size={38} className="rounded-xl" />
            <div className="min-w-0">
              <div className="font-semibold text-[16px] leading-tight truncate flex items-center gap-2">
                {project.name}
                {project.archived && <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#6E6E73] bg-black/[0.06] rounded-full px-2 py-0.5"><Archive size={11} /> Archiv</span>}
              </div>
              <div className="text-[12px] text-[#6E6E73] truncate">{[project.customer_name, project.employee_name].filter(Boolean).join(' · ') || 'Projekt'}</div>
            </div>
          </>
        )}
        right={<Btn variant="soft" size="sm" onClick={() => setProjectDialog(true)}><Settings2 size={16} /> <span className="hidden sm:inline">Projekt</span></Btn>}
      />

      <main className="max-w-[1400px] mx-auto px-3 sm:px-6 py-5 sm:py-8 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-5 py-4">
            <div className="flex items-center gap-1.5">
              <IconBtn variant="soft" onClick={prev} disabled={!canPrev} title="Vorheriger Monat"><ChevronLeft size={18} /></IconBtn>
              <Select value={month} onChange={(e) => setYm({ year, month: Number(e.target.value) })}>{MONTHS_DE.map((m, i) => <option key={m} value={i}>{m}</option>)}</Select>
              <Select value={year} onChange={(e) => setYm({ year: Number(e.target.value), month })}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select>
              <IconBtn variant="soft" onClick={next} disabled={!canNext} title="Nächster Monat"><ChevronRight size={18} /></IconBtn>
              <Btn variant="ghost" size="sm" onClick={goToday} className="ml-1">Heute</Btn>
            </div>
            <div className="text-[14px] text-[#6E6E73] flex items-center gap-2">
              {!loaded && <Loader2 size={15} className="animate-spin" />}
              <span><strong className="text-[#1D1D1F] font-semibold">{fmtHours(monthMinutes)}</strong> in {MONTHS_DE[month]}</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <div className="min-w-[720px]">
              <div className="grid grid-cols-[52px_repeat(7,minmax(0,1fr))] text-[11px] font-semibold uppercase tracking-wider text-[#86868B] border-y border-black/[0.06]">
                <div className="py-2 text-center">KW</div>
                {WEEKDAYS_DE.map((d, i) => <div key={d} className={`py-2 text-center ${i >= 5 ? 'text-[#A1A1A6]' : ''}`}>{d}</div>)}
              </div>
              {weeks.map((monday) => {
                const { week } = isoWeek(monday);
                const wMinutes = weekMinutes(monday);
                const bKey = `week-${toKey(monday)}`;
                return (
                  <div key={toKey(monday)} className="grid grid-cols-[52px_repeat(7,minmax(0,1fr))] border-b border-black/[0.06] last:border-b-0">
                    <div className="flex flex-col items-center justify-center gap-0.5 py-2 border-r border-black/[0.06] bg-[#FAFAFA]">
                      <span className="text-[11px] font-semibold text-[#6E6E73]">{week}</span>
                      {wMinutes > 0 && <span className="text-[10px] text-[#86868B]">{fmtDecimalHours(wMinutes)}h</span>}
                      <IconBtn size={28} onClick={() => weekDoc(monday)} disabled={!loaded || busy === bKey} title={`Stundenzettel KW ${week} (PDF)`} className="text-[#C41E3A] mt-0.5">
                        {busy === bKey ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
                      </IconBtn>
                    </div>
                    {Array.from({ length: 7 }, (_, i) => {
                      const d = addDays(monday, i);
                      const key = toKey(d);
                      const inMonth = d.getMonth() === month;
                      const dayEntries = byDay[key] || [];
                      const dayMinutes = dayEntries.reduce((s, e) => s + entryMinutes(e), 0);
                      const isToday = key === tKey;
                      return (
                        <button key={key} onClick={() => loaded && setSelectedDate(key)} className={`relative min-w-0 overflow-hidden min-h-[96px] text-left p-1.5 border-r border-black/[0.06] last:border-r-0 transition-colors hover:bg-black/[0.03] active:bg-black/[0.05] ${inMonth ? '' : 'bg-[#FAFAFA] text-[#C7C7CC]'}`}>
                          <div className="flex items-center justify-between px-0.5">
                            <span className={`text-[13px] font-semibold w-7 h-7 flex items-center justify-center rounded-full ${isToday ? 'bg-[#C41E3A] text-white' : ''}`}>{d.getDate()}</span>
                            {dayMinutes > 0 && <span className="text-[11px] font-semibold" style={{ color: inMonth ? color : undefined }}>{fmtHours(dayMinutes)}</span>}
                          </div>
                          <div className="mt-1 space-y-1">
                            {dayEntries.slice(0, 3).map((e) => (
                              <div key={e.id} className="text-[11px] leading-[1.25] truncate rounded-md px-1.5 py-1" style={{ backgroundColor: `${color}14`, color: inMonth ? '#1D1D1F' : undefined }}>
                                <span className="font-semibold" style={{ color: inMonth ? color : undefined }}>{e.start_time}–{e.end_time}{entryWorkers(e) > 1 ? ` ×${entryWorkers(e)}` : ''}</span>
                                {e.activity ? <span className="text-[#6E6E73]"> {e.activity}</span> : null}
                              </div>
                            ))}
                            {dayEntries.length > 3 && <div className="text-[11px] text-[#86868B] px-1.5">+{dayEntries.length - 3} weitere</div>}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="px-5 py-3 text-[12px] text-[#86868B]">Tag antippen, um Arbeitszeit einzutragen. Links neben jeder Woche: Stundenzettel als PDF.</div>
        </Card>

        <aside className="space-y-4">
          <Card className="p-5">
            <div className="text-[13px] font-medium text-[#6E6E73]">{MONTHS_DE[month]} {year}</div>
            <div className="text-[36px] font-bold tracking-tight leading-none mt-1">{fmtHours(monthMinutes)}</div>
            <div className="text-[13px] text-[#6E6E73] mt-1">{fmtDecimalHours(monthMinutes)} Mitarbeiterstunden an {monthDays} {monthDays === 1 ? 'Tag' : 'Tagen'}</div>
            <div className="mt-4 rounded-2xl bg-[#F5F5F7] px-4 py-3 space-y-1.5 text-[14px]">
              <div className="flex justify-between"><span className="text-[#6E6E73]">Stundensatz</span><span className="font-semibold">{rate > 0 ? fmtEur(rate) : <span className="text-[#C41E3A]">fehlt</span>}</span></div>
              <div className="flex justify-between"><span className="text-[#6E6E73]">Betrag netto</span><span className="font-bold text-[#C41E3A]">{fmtEur((monthMinutes / 60) * rate)}</span></div>
              {invoice && (
                <div className="flex justify-between items-center"><span className="text-[#6E6E73]">Rechnung</span>
                  <span className="font-semibold flex items-center gap-1">{invoice.number}<IconBtn size={24} onClick={resetInvoice} title="Rechnungsnummer zurücksetzen" className="text-[#A1A1A6]"><RotateCcw size={12} /></IconBtn></span>
                </div>
              )}
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex gap-1.5">
                <Btn className="flex-1" onClick={() => monthDoc()} loading={busy === 'month'} disabled={!loaded}><FileStack size={17} /> Monats-PDF</Btn>
                <IconBtn variant="primary" size={44} onClick={() => monthDoc('download')} disabled={!loaded || busy === 'month'} title="Herunterladen"><Download size={17} /></IconBtn>
              </div>
              <p className="text-[12px] text-[#86868B] px-1">Stundenzettel aller Wochen + Übersicht + Rechnung in einer Datei.</p>
              <div className="flex gap-1.5">
                <Btn variant="soft" className="flex-1" onClick={() => invoiceDoc()} loading={busy === 'invoice'} disabled={!loaded}><Receipt size={17} /> Nur Rechnung</Btn>
                <IconBtn variant="soft" size={44} onClick={() => invoiceDoc('download')} disabled={!loaded || busy === 'invoice'} title="Herunterladen"><Download size={17} /></IconBtn>
              </div>
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="text-[15px] font-semibold">Stundenzettel pro Woche</h3>
            <ul className="mt-2 divide-y divide-black/[0.06]">
              {weeks.map((monday) => {
                const { week, year: wy } = isoWeek(monday);
                const m = weekMinutes(monday);
                const bKey = `week-${toKey(monday)}`;
                return (
                  <li key={toKey(monday)} className="py-2.5 flex items-center gap-2 text-[14px]">
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold">KW {week} <span className="text-[#A1A1A6] font-normal text-[12px]">{wy}</span></div>
                      <div className="text-[12px] text-[#86868B]">{fmtDateShort(monday)} – {fmtDateShort(addDays(monday, 6))} · {fmtHours(m)}</div>
                    </div>
                    <IconBtn size={32} variant="danger" onClick={() => weekDoc(monday)} disabled={!loaded || busy === bKey} title="PDF teilen / öffnen">{busy === bKey ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}</IconBtn>
                    <IconBtn size={32} onClick={() => weekDoc(monday, 'download')} disabled={!loaded || busy === bKey} title="PDF herunterladen" className="text-[#6E6E73]"><Download size={15} /></IconBtn>
                  </li>
                );
              })}
            </ul>
          </Card>
        </aside>
      </main>

      <EntryDialog
        open={!!selectedDate}
        onOpenChange={(o) => { if (!o) setSelectedDate(null); }}
        projectId={project.id}
        dateKey={selectedDate}
        entries={selectedDate ? (byDay[selectedDate] || []) : []}
        lastEntry={lastEntry}
        recentActivities={recentActivities}
        defaultWorkers={project.default_workers || 1}
        onWeekPdf={() => selectedDate && weekDoc(fromKey(selectedDate))}
      />
      <ProjectDialog open={projectDialog} onOpenChange={setProjectDialog} project={project} companyId={project.company_id} defaultRate={comp.default_hourly_rate || 0} onSaved={() => {}} onDeleted={() => navigate(backTo)} />
    </div>
  );
}
