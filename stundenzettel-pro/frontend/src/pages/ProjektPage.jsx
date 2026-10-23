import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import QRCode from 'qrcode';
import {
  ArrowLeft, ChevronLeft, ChevronRight, Settings2, FileText, Download, Loader2, Receipt, FileStack, Archive, PenLine, Check,
  Repeat, MessageSquare, Paperclip, ListChecks, Trash2, Plus, ExternalLink, Image as ImageIcon, QrCode, Lock, AlertTriangle, Printer, Camera,
} from 'lucide-react';
import Layout from '../components/Layout';
import ProjectDialog from '../components/ProjectDialog';
import EntryDialog from '../components/EntryDialog';
import SerieDialog from '../components/SerieDialog';
import UnterschriftDialog from '../components/UnterschriftDialog';
import FotoAuswahlDialog from '../components/FotoAuswahlDialog';
import TagFotos from '../components/TagFotos';
import Bild from '../components/Bild';
import { AppIcon, Btn, Card, IconBtn, Segmented, Select, Sheet, TextArea, TextInput, Field } from '../components/ui';
import { api, openFile } from '../lib/api';
import { useAuth } from '../lib/auth';
import { weekPdf, monthPdf, invoicePdf, preloadLogo, signatureMap } from '../lib/pdf';
import { MIN_YEAR, MAX_YEAR, MONTHS_DE, WEEKDAYS_DE, toKey, fromKey, addDays, isoWeek, monthWeeks, clampMonth, fmtHours, fmtDecimalHours, fmtEur, fmtDateShort, fmtDate, todayKey, monthLastDay, entryMinutes, entryWorkers, fmtDecimal } from '../lib/dates';
import { initials, deliverPdf, downloadBlob } from '../lib/utils';
import { fotosNachTag, fotosImZeitraum, ladeFotoDaten } from '../lib/fotos';

const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);
const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

/** Ein Projekt: Kalender (Zeiten, Stundenzettel, Rechnung, Budget, Feiertage), Akte, Checklisten, Objekt-QR-Code. */
export default function ProjektPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { isBuero } = useAuth();
  const today = useMemo(() => new Date(), []);
  const [{ year, month }, setYm] = useState(() => clampMonth(today.getFullYear(), today.getMonth()));
  const [tab, setTab] = useState('kalender');
  const [data, setData] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);
  const [projectDialog, setProjectDialog] = useState(false);
  const [serie, setSerie] = useState(false);
  const [sigMonday, setSigMonday] = useState(null);
  const [qr, setQr] = useState(false);
  const [busy, setBusy] = useState('');
  const [fotoWahl, setFotoWahl] = useState(null);   // { art: 'week'|'month'|'invoice', monday, fotos } – Auswahl vor der PDF

  const laden = useCallback(async () => {
    try {
      const r = await api.get(`/api/projekte/${projectId}/monat?jahr=${year}&monat=${month + 1}`);
      setData(r);
      preloadLogo(r.firma);
    } catch (err) {
      toast.error(err.message);
      if (err.status === 404) navigate('/projekte', { replace: true });
    }
  }, [projectId, year, month, navigate]);
  useEffect(() => { laden(); }, [laden]);

  const project = data?.projekt;
  const firma = data?.firma || { name: '', default_hourly_rate: 0 };
  const entries = data?.eintraege || [];
  const leitung = !!data?.leitung;
  const feiertage = data?.feiertage || {};
  const sigs = useMemo(() => signatureMap(data?.unterschriften), [data]);
  const weeks = useMemo(() => monthWeeks(year, month), [year, month]);
  const byDay = useMemo(() => { const m = {}; for (const e of entries) (m[e.date] ||= []).push(e); return m; }, [entries]);
  const fotos = data?.fotos || [];
  const fotosByDay = useMemo(() => fotosNachTag(fotos), [fotos]);
  const recentActivities = useMemo(() => { const seen = []; for (let i = entries.length - 1; i >= 0 && seen.length < 4; i--) { const a = (entries[i].activity || '').trim(); if (a && !seen.includes(a)) seen.push(a); } return seen; }, [entries]);

  if (!project) return <Layout><div className="py-24 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={28} /></div></Layout>;

  const firstKey = toKey(new Date(year, month, 1));
  const lastKey = toKey(monthLastDay(year, month));
  const monthEntries = entries.filter((e) => e.date >= firstKey && e.date <= lastKey);
  const monthMinutes = monthEntries.reduce((s, e) => s + entryMinutes(e), 0);
  const monthDays = new Set(monthEntries.map((e) => e.date)).size;
  const rate = Number(project.hourly_rate) || Number(firma.default_hourly_rate) || 0;
  const invoice = data.rechnung;
  const lastEntry = entries[entries.length - 1] || null;
  const gesperrt = data.abgeschlossen ? `${MONTHS_DE[month]} ${year} ist abgeschlossen. Das Büro kann den Monat unter „Exporte & Abschluss“ wieder öffnen.`
    : invoice?.status === 'bezahlt' ? `Die Rechnung ${invoice.number} für diesen Monat ist bezahlt – Zeiten sind gesperrt.` : '';
  const weekMinutes = (monday) => { const lo = toKey(monday); const hi = toKey(addDays(monday, 6)); return entries.filter((e) => e.date >= lo && e.date <= hi).reduce((s, e) => s + entryMinutes(e), 0); };
  const canPrev = year > MIN_YEAR || month > 0;
  const canNext = year < MAX_YEAR || month < 11;
  const prev = () => canPrev && setYm(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 });
  const next = () => canNext && setYm(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 });

  const deliver = (key, make, mode) => {
    let result;
    try { result = make(); } catch (err) { console.error(err); toast.error('PDF konnte nicht erstellt werden'); return; }
    setBusy(key);
    deliverPdf(result, mode).catch((err) => { console.error(err); toast.error('PDF konnte nicht weitergegeben werden'); }).finally(() => setBusy(''));
  };
  // Fotos im Zeitraum: gibt es welche, fragt ein Dialog vor der PDF, welche mit hinein sollen (bilder === null → noch nicht gefragt)
  const weekMake = (monday, bilder) => weekPdf(project, firma, monday, entries.filter((e) => e.date >= toKey(monday) && e.date <= toKey(addDays(monday, 6))), sigs, bilder);
  const weekDoc = (monday, mode) => {
    const f = fotosImZeitraum(fotos, toKey(monday), toKey(addDays(monday, 6)));
    if (f.length) { setFotoWahl({ art: 'week', monday, fotos: f }); return; }
    deliver(`week-${toKey(monday)}`, () => weekMake(monday, []), mode);
  };
  const rechnungHolen = async () => (await api.post('/api/rechnungen/anlegen', { project_id: project.id, year, month: month + 1 })).rechnung;
  const monthDoc = async (mode, bilder = null) => {
    if (bilder === null) { const f = fotosImZeitraum(fotos, firstKey, lastKey); if (f.length) { setFotoWahl({ art: 'month', fotos: f }); return; } bilder = []; }
    setBusy('month');
    try {
      let inv = null;
      try { inv = await rechnungHolen(); } catch (err) { if (err.status !== 400) throw err; toast.info('Keine Zeiten im Monat – Mappe ohne Rechnung'); }
      await deliverPdf(monthPdf(project, firma, year, month, entries, inv, sigs, bilder), mode);
      laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const invoiceDoc = async (mode, bilder = null) => {
    if (bilder === null) { const f = fotosImZeitraum(fotos, firstKey, lastKey); if (f.length) { setFotoWahl({ art: 'invoice', fotos: f }); return; } bilder = []; }
    setBusy('invoice');
    try { const inv = await rechnungHolen(); await deliverPdf(invoicePdf(project, firma, year, month, monthEntries, inv, bilder), mode); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const fotoWahlBestaetigt = async (ausgewaehlt, mode) => {
    const wahl = fotoWahl;
    if (!wahl) return;
    setBusy('fotos');
    try {
      const bilder = ausgewaehlt.length ? await ladeFotoDaten(ausgewaehlt) : [];
      setFotoWahl(null);
      if (wahl.art === 'week') await deliverPdf(weekMake(wahl.monday, bilder), mode);
      else if (wahl.art === 'month') await monthDoc(mode, bilder);
      else await invoiceDoc(mode, bilder);
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };

  const tKey = todayKey();
  const color = project.color || '#C41E3A';
  const budget = data.budget;

  return (
    <Layout wide>
      <div className="flex items-center gap-3 mb-5">
        <IconBtn onClick={() => navigate('/projekte')} title="Zurück"><ArrowLeft size={20} /></IconBtn>
        <AppIcon color={color} text={initials(project.name)} size={40} className="rounded-xl" />
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-[18px] leading-tight truncate flex items-center gap-2">{project.name}{project.archived && <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#6E6E73] bg-black/[0.06] rounded-full px-2 py-0.5"><Archive size={11} /> Archiv</span>}</div>
          <div className="text-[12px] text-[#6E6E73] truncate">{[project.customer_name, project.address, project.schedule].filter(Boolean).join(' · ') || 'Projekt'}</div>
        </div>
        {leitung && <IconBtn variant="soft" onClick={() => setQr(true)} title="QR-Code fürs Objekt"><QrCode size={18} /></IconBtn>}
        {isBuero && <Btn variant="soft" size="sm" onClick={() => setProjectDialog(true)}><Settings2 size={16} /> <span className="hidden sm:inline">Projekt</span></Btn>}
      </div>
      <div className="flex justify-center mb-5">
        <Segmented value={tab} onChange={setTab} options={[{ value: 'kalender', label: 'Kalender', icon: FileText }, { value: 'akte', label: 'Akte', icon: Paperclip }, { value: 'checklisten', label: 'Checklisten', icon: ListChecks }]} />
      </div>

      {tab === 'kalender' && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-5 py-4">
              <div className="flex items-center gap-1.5">
                <IconBtn variant="soft" onClick={prev} disabled={!canPrev}><ChevronLeft size={18} /></IconBtn>
                <Select value={month} onChange={(e) => setYm({ year, month: Number(e.target.value) })}>{MONTHS_DE.map((m, i) => <option key={m} value={i}>{m}</option>)}</Select>
                <Select value={year} onChange={(e) => setYm({ year: Number(e.target.value), month })}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select>
                <IconBtn variant="soft" onClick={next} disabled={!canNext}><ChevronRight size={18} /></IconBtn>
                <Btn variant="ghost" size="sm" onClick={() => setYm(clampMonth(today.getFullYear(), today.getMonth()))} className="ml-1">Heute</Btn>
              </div>
              <div className="text-[14px] text-[#6E6E73] flex items-center gap-2">{gesperrt && <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-black/[0.06] rounded-full px-2 py-0.5"><Lock size={11} /> gesperrt</span>}<span><strong className="text-[#1D1D1F] font-semibold">{fmtHours(monthMinutes)}</strong> in {MONTHS_DE[month]}</span></div>
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-[720px]">
                <div className="grid grid-cols-[64px_repeat(7,minmax(0,1fr))] text-[11px] font-semibold uppercase tracking-wider text-[#86868B] border-y border-black/[0.06]">
                  <div className="py-2 text-center">KW</div>
                  {WEEKDAYS_DE.map((d, i) => <div key={d} className={`py-2 text-center ${i >= 5 ? 'text-[#A1A1A6]' : ''}`}>{d}</div>)}
                </div>
                {weeks.map((monday) => {
                  const { week } = isoWeek(monday);
                  const mKey = toKey(monday);
                  const wMinutes = weekMinutes(monday);
                  const bKey = `week-${mKey}`;
                  const signed = !!sigs[mKey];
                  return (
                    <div key={mKey} className="grid grid-cols-[64px_repeat(7,minmax(0,1fr))] border-b border-black/[0.06] last:border-b-0">
                      <div className="flex flex-col items-center justify-center gap-0.5 py-2 border-r border-black/[0.06] bg-[#FAFAFA]">
                        <span className="text-[11px] font-semibold text-[#6E6E73]">{week}</span>
                        {wMinutes > 0 && <span className="text-[10px] text-[#86868B]">{fmtDecimalHours(wMinutes)}h</span>}
                        <div className="flex gap-0.5 mt-0.5">
                          <IconBtn size={26} onClick={() => weekDoc(monday)} disabled={busy === bKey} title={`Stundenzettel KW ${week} (PDF)`} className="text-[#C41E3A]">{busy === bKey ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />}</IconBtn>
                          <IconBtn size={26} onClick={() => setSigMonday(mKey)} title={signed ? `Unterschrieben von ${sigs[mKey].signer_name}` : 'Kunde unterschreiben lassen'} className={signed ? 'text-[#34C759]' : 'text-[#86868B]'}>{signed ? <Check size={13} /> : <PenLine size={13} />}</IconBtn>
                        </div>
                      </div>
                      {Array.from({ length: 7 }, (_, i) => {
                        const d = addDays(monday, i);
                        const key = toKey(d);
                        const inMonth = d.getMonth() === month;
                        const dayEntries = byDay[key] || [];
                        const dayMinutes = dayEntries.reduce((s, e) => s + entryMinutes(e), 0);
                        const frei = feiertage[key];
                        return (
                          <button key={key} onClick={() => setSelectedDate(key)} className={`relative min-w-0 overflow-hidden min-h-[96px] text-left p-1.5 border-r border-black/[0.06] last:border-r-0 transition-colors hover:bg-black/[0.03] ${inMonth ? (frei ? 'bg-[#FFF8EC]' : '') : 'bg-[#FAFAFA] text-[#C7C7CC]'}`}>
                            <div className="flex items-center justify-between px-0.5">
                              <span className={`text-[13px] font-semibold w-7 h-7 flex items-center justify-center rounded-full ${key === tKey ? 'bg-[#C41E3A] text-white' : ''}`}>{d.getDate()}</span>
                              {dayMinutes > 0 && <span className="text-[11px] font-semibold" style={{ color: inMonth ? color : undefined }}>{fmtHours(dayMinutes)}</span>}
                            </div>
                            {frei && <div className="text-[10px] text-[#B25E00] px-0.5 truncate">{frei}</div>}
                            {(fotosByDay[key]?.length || 0) > 0 && <span className="absolute bottom-1 right-1 inline-flex items-center gap-0.5 text-[10px] font-semibold rounded-full bg-black/[0.07] text-[#6E6E73] px-1.5 py-0.5" title={`${fotosByDay[key].length} Fotos`}><Camera size={10} /> {fotosByDay[key].length}</span>}
                            <div className="mt-1 space-y-1">
                              {dayEntries.slice(0, 3).map((e) => (
                                <div key={e.id} className="text-[11px] leading-[1.25] truncate rounded-md px-1.5 py-1" style={{ backgroundColor: `${color}14`, color: inMonth ? '#1D1D1F' : undefined }}>
                                  <span className="font-semibold" style={{ color: inMonth ? color : undefined }}>{e.start_time}–{e.end_time}{entryWorkers(e) > 1 ? ` ×${entryWorkers(e)}` : ''}</span>
                                  {e.warnungen?.length ? <AlertTriangle size={10} className="inline ml-1 text-[#B25E00]" /> : null}
                                  <span className="text-[#6E6E73]"> {e.user_name || e.service_name || e.activity}</span>
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
            <div className="px-5 py-3 text-[12px] text-[#86868B]">Tag antippen: Zeit eintragen, Fotos ansehen oder aufnehmen. Links je Woche: Stundenzettel als PDF und Kunden-Unterschrift. Feiertage sind hell markiert.</div>
          </Card>

          <aside className="space-y-4">
            <Card className="p-5">
              <div className="text-[13px] font-medium text-[#6E6E73]">{MONTHS_DE[month]} {year}</div>
              <div className="text-[36px] font-bold tracking-tight leading-none mt-1">{fmtHours(monthMinutes)}</div>
              <div className="text-[13px] text-[#6E6E73] mt-1">{fmtDecimalHours(monthMinutes)} Mitarbeiterstunden an {monthDays} {monthDays === 1 ? 'Tag' : 'Tagen'}</div>
              {budget && (
                <div className="mt-3">
                  <div className="flex justify-between text-[12px] text-[#6E6E73]"><span>Budget {fmtDecimal(budget.stunden_monat, 1)} Std./Monat</span><span className={budget.ueberschritten ? 'text-[#C41E3A] font-semibold' : budget.warnung ? 'text-[#B25E00] font-semibold' : ''}>{budget.prozent} %</span></div>
                  <div className="h-2 rounded-full bg-black/[0.06] mt-1 overflow-hidden"><div className={`h-full rounded-full ${budget.ueberschritten ? 'bg-[#C41E3A]' : budget.warnung ? 'bg-[#F59E0B]' : 'bg-[#34C759]'}`} style={{ width: `${Math.min(100, budget.prozent)}%` }} /></div>
                </div>
              )}
              {isBuero && (
                <>
                  <div className="mt-4 rounded-2xl bg-[#F5F5F7] px-4 py-3 space-y-1.5 text-[14px]">
                    <div className="flex justify-between"><span className="text-[#6E6E73]">Stundensatz</span><span className="font-semibold">{rate > 0 ? fmtEur(rate) : <span className="text-[#C41E3A]">fehlt</span>}</span></div>
                    <div className="flex justify-between"><span className="text-[#6E6E73]">Betrag netto</span><span className="font-bold text-[#C41E3A]">{invoice ? fmtEur(invoice.net) : fmtEur((monthMinutes / 60) * rate)}</span></div>
                    {project.reverse_charge && <div className="text-[12px] text-[#6E6E73]">Rechnung ohne USt (§ 13b)</div>}
                    {invoice && <div className="flex justify-between items-center"><span className="text-[#6E6E73]">Rechnung</span><span className="font-semibold">{invoice.number} <span className="text-[11px] font-normal text-[#6E6E73]">({invoice.status}{invoice.extras?.length ? `, ${invoice.extras.length} Zusatzpos.` : ''})</span></span></div>}
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="flex gap-1.5">
                      <Btn className="flex-1" onClick={() => monthDoc()} loading={busy === 'month'}><FileStack size={17} /> Monats-PDF</Btn>
                      <IconBtn variant="primary" size={44} onClick={() => monthDoc('download')} disabled={busy === 'month'} title="Herunterladen"><Download size={17} /></IconBtn>
                    </div>
                    <div className="flex gap-1.5">
                      <Btn variant="soft" className="flex-1" onClick={() => invoiceDoc()} loading={busy === 'invoice'}><Receipt size={17} /> Nur Rechnung</Btn>
                      <IconBtn variant="soft" size={44} onClick={() => invoiceDoc('download')} disabled={busy === 'invoice'} title="Herunterladen"><Download size={17} /></IconBtn>
                    </div>
                  </div>
                </>
              )}
              {leitung && !gesperrt && <Btn variant="ghost" size="sm" className="w-full mt-2" onClick={() => setSerie(true)}><Repeat size={15} /> Zeiten als Serie eintragen</Btn>}
            </Card>
            <Card className="p-5">
              <h3 className="text-[15px] font-semibold">Stundenzettel pro Woche</h3>
              <ul className="mt-2 divide-y divide-black/[0.06]">
                {weeks.map((monday) => {
                  const { week, year: wy } = isoWeek(monday);
                  const mKey = toKey(monday);
                  const bKey = `week-${mKey}`;
                  return (
                    <li key={mKey} className="py-2.5 flex items-center gap-2 text-[14px]">
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold">KW {week} <span className="text-[#A1A1A6] font-normal text-[12px]">{wy}</span>{sigs[mKey] && <span className="ml-2 text-[11px] text-[#34C759] font-medium">✓ {sigs[mKey].signer_name}</span>}</div>
                        <div className="text-[12px] text-[#86868B]">{fmtDateShort(monday)} – {fmtDateShort(addDays(monday, 6))} · {fmtHours(weekMinutes(monday))}</div>
                      </div>
                      <IconBtn size={32} variant="danger" onClick={() => weekDoc(monday)} disabled={busy === bKey} title="PDF teilen / öffnen">{busy === bKey ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}</IconBtn>
                      <IconBtn size={32} onClick={() => weekDoc(monday, 'download')} disabled={busy === bKey} title="PDF herunterladen" className="text-[#6E6E73]"><Download size={15} /></IconBtn>
                    </li>
                  );
                })}
              </ul>
            </Card>
          </aside>
        </div>
      )}

      {tab === 'akte' && <Akte projectId={project.id} leitung={leitung} />}
      {tab === 'checklisten' && <Checklisten projectId={project.id} leitung={leitung} />}

      <EntryDialog open={!!selectedDate} onOpenChange={(o) => { if (!o) setSelectedDate(null); }} projectId={project.id} dateKey={selectedDate}
        entries={selectedDate ? (byDay[selectedDate] || []) : []} lastEntry={lastEntry} recentActivities={recentActivities}
        defaultWorkers={project.default_workers || 1} mitarbeiter={data.mitarbeiter || []} leistungen={data.leistungen || []} kannPersonen={leitung}
        fotoBereich={selectedDate ? <TagFotos projectId={project.id} dateKey={selectedDate} fotos={fotosByDay[selectedDate] || []} onChanged={laden} darfHochladen={!project.archived} /> : null}
        gesperrt={gesperrt} feiertag={selectedDate ? feiertage[selectedDate] || '' : ''} onChanged={laden} onWeekPdf={() => selectedDate && weekDoc(fromKey(selectedDate))} />
      <SerieDialog open={serie} onOpenChange={setSerie} projectId={project.id} year={year} month0={month} mitarbeiter={data.mitarbeiter || []} leistungen={data.leistungen || []} defaultWorkers={project.default_workers || 1} onDone={laden} />
      <UnterschriftDialog open={!!sigMonday} onOpenChange={(o) => { if (!o) setSigMonday(null); }} projectId={project.id} mondayKey={sigMonday} customerName={sigs[sigMonday]?.signer_name || ''} onSaved={laden} />
      <ProjectDialog open={projectDialog} onOpenChange={setProjectDialog} project={project} defaultRate={firma.default_hourly_rate || 0} onSaved={laden} onDeleted={() => navigate('/projekte')} />
      <QrDialog open={qr} onOpenChange={setQr} project={project} />
      <FotoAuswahlDialog open={!!fotoWahl} onOpenChange={(o) => { if (!o) setFotoWahl(null); }} fotos={fotoWahl?.fotos || []} busy={busy === 'fotos'} onConfirm={fotoWahlBestaetigt}
        titel={fotoWahl?.art === 'week' ? `Stundenzettel KW ${fotoWahl.monday ? isoWeek(fotoWahl.monday).week : ''} als PDF` : fotoWahl?.art === 'month' ? `Monats-PDF ${MONTHS_DE[month]} ${year}` : `Rechnung ${MONTHS_DE[month]} ${year} als PDF`} />
    </Layout>
  );
}

/** QR-Code fürs Objekt: scannen öffnet die Stempeluhr mit vorgewähltem Projekt. */
function QrDialog({ open, onOpenChange, project }) {
  const [bild, setBild] = useState('');
  const url = `${window.location.origin}${window.location.pathname}#/stempeln/${project.id}`;
  useEffect(() => { if (open) QRCode.toDataURL(url, { width: 640, margin: 1, color: { dark: '#1D1D1F' } }).then(setBild).catch(() => toast.error('QR-Code konnte nicht erzeugt werden')); }, [open, url]);
  const drucken = () => {
    const w = window.open('', '_blank');
    if (!w) { toast.error('Pop-up blockiert'); return; }
    w.document.write(`<html><head><title>QR ${project.name}</title></head><body style="font-family:Arial;text-align:center;padding:40px"><h1 style="font-size:28px">${project.name}</h1><p style="color:#555">${project.address || project.customer_name || ''}</p><img src="${bild}" style="width:70vw;max-width:520px"/><p style="font-size:20px;margin-top:24px">QR-Code scannen → Stempeluhr öffnet sich mit diesem Objekt.</p><p style="color:#888;font-size:12px">${url}</p></body></html>`);
    w.document.close();
    setTimeout(() => w.print(), 300);
  };
  const herunterladen = async () => { try { downloadBlob(await (await fetch(bild)).blob(), `QR_${project.name.replace(/[^\w-]+/g, '_')}.png`); } catch { toast.error('Download fehlgeschlagen'); } };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="QR-Code fürs Objekt" subtitle="Ausdrucken und am Objekt aufhängen. Mitarbeiter scannen ihn und sind mit einem Tipp eingestempelt.">
      <div className="space-y-4 text-center">
        {bild ? <img src={bild} alt="QR-Code" className="mx-auto w-64 h-64 rounded-2xl bg-white shadow-card p-3" /> : <div className="py-16 flex justify-center"><Loader2 className="animate-spin" /></div>}
        <div className="text-[12px] text-[#86868B] break-all">{url}</div>
        <div className="flex justify-center gap-2"><Btn variant="soft" onClick={herunterladen}><Download size={16} /> PNG</Btn><Btn onClick={drucken}><Printer size={16} /> Drucken</Btn></div>
      </div>
    </Sheet>
  );
}

/** Projektakte: Notizen/Kommentare, Dateien und Fotos, Kunden-Unterschriften. */
function Akte({ projectId, leitung }) {
  const { isBuero, user } = useAuth();
  const [akte, setAkte] = useState(null);
  const [text, setText] = useState('');
  const [kategorie, setKategorie] = useState('Fotos');
  const [datum, setDatum] = useState(todayKey());   // Arbeitstag, an dem das Foto im Kalender erscheint
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/akte`).then(setAkte).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  if (!akte) return <div className="py-16 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={26} /></div>;

  const senden = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    try { await api.post(`/api/projekte/${projectId}/kommentare`, { text }); setText(''); laden(); } catch (err) { toast.error(err.message); }
  };
  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('datei', file);
    fd.append('kategorie', kategorie);
    fd.append('date', datum);
    setBusy(true);
    try { await api.upload(`/api/projekte/${projectId}/dateien`, fd); toast.success('Datei gespeichert'); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (id, pfad) => { if (!window.confirm('Wirklich löschen?')) return; try { await api.del(pfad); laden(); } catch (err) { toast.error(err.message); } };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card className="p-5">
        <h2 className="text-[16px] mb-3 flex items-center gap-2"><MessageSquare size={16} /> Notizen &amp; Kommentare</h2>
        <form onSubmit={senden} className="flex gap-2 mb-4"><TextInput value={text} onChange={(e) => setText(e.target.value)} placeholder="z. B. Schlüssel beim Hausmeister, Tür hinten klemmt" /><Btn type="submit" size="md"><Plus size={16} /></Btn></form>
        {akte.kommentare.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine Notizen.</p> : (
          <ul className="divide-y divide-black/[0.06]">
            {akte.kommentare.map((k) => (
              <li key={k.id} className="py-2.5 flex gap-3 text-[14px]">
                <div className="flex-1 min-w-0"><div className="whitespace-pre-wrap break-words">{k.text}</div><div className="text-[12px] text-[#86868B] mt-0.5">{k.user_name} · {fmtZeit(k.created_at)}</div></div>
                {(isBuero || k.user_id === user?.id) && <IconBtn size={28} variant="danger" onClick={() => loeschen(k.id, `/api/kommentare/${k.id}`)} title="Löschen"><Trash2 size={14} /></IconBtn>}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <div className="space-y-5">
        <Card className="p-5">
          <h2 className="text-[16px] mb-3 flex items-center gap-2"><ImageIcon size={16} /> Fotos &amp; Dateien</h2>
          <div className="flex flex-wrap gap-2 items-center mb-3">
            <Select value={kategorie} onChange={(e) => setKategorie(e.target.value)}>{akte.kategorien.map((k) => <option key={k} value={k}>{k}</option>)}</Select>
            <TextInput type="date" value={datum} onChange={(e) => setDatum(e.target.value)} className="w-[160px]" title="Arbeitstag (so erscheint das Foto im Kalender)" />
            <label className="inline-flex"><input type="file" accept="image/*,application/pdf" className="hidden" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ''; }} /><span className="inline-flex items-center gap-2 h-10 px-4 rounded-full bg-[#1D1D1F] text-white text-[14px] font-semibold cursor-pointer">{busy ? <Loader2 size={15} className="animate-spin" /> : <Paperclip size={15} />} Hochladen / Foto</span></label>
          </div>
          {akte.dateien.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine Dateien. Fotos landen hier und im Kalender am gewählten Arbeitstag.</p> : (
            <ul className="divide-y divide-black/[0.06]">
              {akte.dateien.map((d) => (
                <li key={d.id} className="py-2.5 flex items-center gap-3 text-[14px]">
                  {d.mime?.startsWith('image/') ? <Bild id={d.id} max={120} className="w-9 h-9 rounded-xl shrink-0" alt="" /> : <span className="w-9 h-9 rounded-xl bg-[#F5F5F7] flex items-center justify-center text-[#6E6E73] shrink-0"><FileText size={16} /></span>}
                  <div className="flex-1 min-w-0"><div className="font-medium truncate">{d.note || d.filename}</div><div className="text-[12px] text-[#86868B]">{d.category}{d.date ? ` · Arbeitstag ${fmtDate(fromKey(d.date))}` : ''} · {d.uploaded_by_name} · {fmtZeit(d.created_at)} · {Math.round(d.size / 1024)} KB</div></div>
                  <IconBtn size={30} onClick={() => openFile(`/api/dokumente/${d.id}/datei`).catch((err) => toast.error(err.message))} title="Öffnen"><ExternalLink size={15} /></IconBtn>
                  {isBuero && <IconBtn size={30} variant="danger" onClick={() => loeschen(d.id, `/api/dokumente/${d.id}`)} title="Löschen"><Trash2 size={14} /></IconBtn>}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="text-[16px] mb-3 flex items-center gap-2"><PenLine size={16} /> Kunden-Unterschriften</h2>
          {akte.unterschriften.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine. Im Kalender neben der Woche auf den Stift tippen.</p> : (
            <ul className="divide-y divide-black/[0.06] text-[14px]">
              {akte.unterschriften.map((s) => <li key={s.id} className="py-2 flex items-center justify-between gap-2"><span>KW {isoWeek(fromKey(s.week_monday)).week} · {fmtDate(fromKey(s.week_monday))}</span><span className="text-[#6E6E73] truncate">{s.signer_name} · {fmtZeit(s.signed_at)}</span>{isBuero && <IconBtn size={28} variant="danger" onClick={() => loeschen(s.id, `/api/unterschriften/${s.id}`)} title="Löschen"><Trash2 size={14} /></IconBtn>}</li>)}
            </ul>
          )}
        </Card>
        {leitung ? null : <p className="text-[12px] text-[#86868B]">Fotos und Notizen kann jeder im Projekt anlegen.</p>}
      </div>
    </div>
  );
}

/** Checklisten je Projekt: Büro und Vorarbeiter legen an, alle haken ab (mit Name und Zeit). */
function Checklisten({ projectId, leitung }) {
  const { isBuero } = useAuth();
  const [listen, setListen] = useState(null);
  const [neu, setNeu] = useState(false);
  const [form, setForm] = useState({ name: '', items: '', date: '' });
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/akte`).then((a) => setListen(a.checklisten)).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  if (!listen) return <div className="py-16 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={26} /></div>;

  const toggle = async (liste, item) => {
    const items = liste.items.map((i) => (i.id === item.id ? { ...i, done: !i.done } : i));
    setListen((l) => l.map((x) => (x.id === liste.id ? { ...x, items } : x)));
    try { await api.put(`/api/checklisten/${liste.id}`, { items: items.map((i) => ({ id: i.id, text: i.text, done: i.done })) }); laden(); } catch (err) { toast.error(err.message); laden(); }
  };
  const anlegen = async (e) => {
    e.preventDefault();
    const items = form.items.split('\n').map((t) => t.trim()).filter(Boolean).map((text) => ({ text }));
    if (!form.name.trim() || !items.length) { toast.error('Name und mindestens ein Punkt'); return; }
    try { await api.post(`/api/projekte/${projectId}/checklisten`, { name: form.name.trim(), items, date: form.date || null }); setNeu(false); setForm({ name: '', items: '', date: '' }); laden(); } catch (err) { toast.error(err.message); }
  };
  const loeschen = async (id) => { if (!window.confirm('Checkliste löschen?')) return; try { await api.del(`/api/checklisten/${id}`); laden(); } catch (err) { toast.error(err.message); } };

  return (
    <div className="space-y-4">
      {leitung && <div className="flex justify-end"><Btn onClick={() => setNeu(true)}><Plus size={16} /> Neue Checkliste</Btn></div>}
      {listen.length === 0 ? <Card className="p-8 text-center text-[14px] text-[#6E6E73]">Noch keine Checklisten. {leitung ? 'Lege z. B. „Unterhaltsreinigung“ mit allen Punkten an – die Mitarbeiter haken am Handy ab.' : ''}</Card> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {listen.map((l) => {
            const done = l.items.filter((i) => i.done).length;
            return (
              <Card key={l.id} className="p-5">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div><h3 className="text-[16px] font-semibold">{l.name}</h3><div className="text-[12px] text-[#86868B]">{l.date ? `${fmtDate(fromKey(l.date))} · ` : ''}{done}/{l.items.length} erledigt</div></div>
                  {isBuero && <IconBtn size={30} variant="danger" onClick={() => loeschen(l.id)} title="Löschen"><Trash2 size={14} /></IconBtn>}
                </div>
                <div className="h-1.5 rounded-full bg-black/[0.06] mb-3"><div className="h-full rounded-full bg-[#34C759] transition-all" style={{ width: `${l.items.length ? (done / l.items.length) * 100 : 0}%` }} /></div>
                <ul className="divide-y divide-black/[0.06]">
                  {l.items.map((i) => (
                    <li key={i.id}>
                      <button type="button" onClick={() => toggle(l, i)} className="w-full flex items-start gap-3 py-2.5 text-left">
                        <span className={`mt-0.5 w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 ${i.done ? 'bg-[#34C759] border-[#34C759] text-white' : 'border-black/20'}`}>{i.done && <Check size={14} />}</span>
                        <span className="flex-1 min-w-0"><span className={`text-[15px] ${i.done ? 'line-through text-[#86868B]' : ''}`}>{i.text}</span>{i.done && i.done_by && <span className="block text-[11px] text-[#86868B]">{i.done_by} · {fmtZeit(i.done_at)}</span>}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </Card>
            );
          })}
        </div>
      )}
      <Sheet open={neu} onOpenChange={setNeu} title="Neue Checkliste" subtitle="Ein Punkt je Zeile.">
        <form onSubmit={anlegen} className="space-y-4">
          <Field label="Name"><TextInput value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="z. B. Unterhaltsreinigung EG" required /></Field>
          <Field label="Einsatztag (optional, leer = Dauerliste)"><TextInput type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
          <Field label="Punkte"><TextArea rows={6} value={form.items} onChange={(e) => setForm({ ...form, items: e.target.value })} placeholder={'Böden wischen\nMülleimer leeren\nSanitär reinigen\nFenster innen'} /></Field>
          <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setNeu(false)}>Abbrechen</Btn><Btn type="submit">Anlegen</Btn></div>
        </form>
      </Sheet>
    </div>
  );
}
