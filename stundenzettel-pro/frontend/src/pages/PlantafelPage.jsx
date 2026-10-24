import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CalendarRange, ChevronLeft, ChevronRight, Copy, FileText, GripVertical, ListChecks, Plus, Search, Undo2, Users } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { useDialoge } from '../components/Dialoge';
import { Btn, Card, Chip, Field, IconBtn, Segmented, Select, Sheet, TextArea, TextInput, Toggle } from '../components/ui';
import { api, download } from '../lib/api';
import { useAuth } from '../lib/auth';
import { addDays, fmtDate, fmtDateShort, fromKey, mondayOf, toKey, WEEKDAYS_DE } from '../lib/dates';
import { cn } from '../lib/utils';

const ANSICHTEN = [{ value: 'tag', label: 'Tag' }, { value: 'woche', label: 'Woche' }, { value: '2wochen', label: '2 Wochen' }, { value: 'monat', label: 'Monat' }];
const TAGE_JE_ANSICHT = { tag: 1, woche: 7, '2wochen': 14, monat: 28 };
const ABGLEICH_CLS = { freigegeben: 'bg-[#1B7F3B] text-white', passt: 'bg-[#E8F8EC] text-[#1B7F3B]', abweichung: 'bg-[#FFF4E5] text-[#B25E00]', fehlt: 'bg-[#FDE8E8] text-[#C41E3A]', offen: 'bg-black/[0.06] text-[#6E6E73]' };
const ABWESENHEIT = { urlaub: 'Urlaub', krank: 'Krank', sonstiges: 'Abwesend', unbezahlt: 'Unbezahlt', schule: 'Schule', fortbildung: 'Fortbildung' };
const ZEITEN_KEY = 'szpro-plantafel-zeiten';
const stunden = (min) => `${Math.floor(min / 60)}:${String(min % 60).padStart(2, '0')}`;
const lesenZeiten = () => { try { return JSON.parse(localStorage.getItem(ZEITEN_KEY) || 'null') || { start_time: '08:00', end_time: '16:00', pause_minutes: 30 }; } catch { return { start_time: '08:00', end_time: '16:00', pause_minutes: 30 }; } };
const merkenZeiten = (z) => { try { localStorage.setItem(ZEITEN_KEY, JSON.stringify(z)); } catch { /* ignore */ } };

/** Plantafel: Mitarbeiter (nach Kolonnen) × Tage. Projekte per Drag-and-drop auf Zellen ziehen, Einsätze verschieben oder kopieren,
 *  Abwesenheiten und Feiertage sehen, Kapazität je Woche prüfen, vergangene Einsätze mit der Stempelung abgleichen und freigeben.
 *  Tastatur: jede Zelle ist ein Knopf (Enter = Einsatz anlegen), jeder Einsatz ein Knopf (Enter = öffnen). Am Handy: tippen statt ziehen. */
export default function PlantafelPage() {
  const navigate = useNavigate();
  const { kann } = useAuth();
  const [params] = useSearchParams();
  const [ansicht, setAnsicht] = useState(() => (window.innerWidth < 640 ? 'tag' : 'woche'));
  const [von, setVon] = useState(() => (window.innerWidth < 640 ? new Date() : mondayOf(new Date())));
  const [d, setD] = useState(null);
  const [filter, setFilter] = useState({ projekt: '', kolonne: '', suche: '' });
  const [kopiermodus, setKopiermodus] = useState(false);
  const [abgesagte, setAbgesagte] = useState(false);
  const [dialog, setDialog] = useState(null);       // { einsatz } | { neu: { user_id, date, project_id } }
  const [kolonnenDialog, setKolonnenDialog] = useState(false);
  const [abgleich, setAbgleich] = useState(params.get('abgleich') === '1');
  const [pdfProjekt, setPdfProjekt] = useState('');
  const dragRef = useRef(null);
  const tage = useMemo(() => Array.from({ length: TAGE_JE_ANSICHT[ansicht] }, (_, i) => toKey(addDays(von, i))), [von, ansicht]);
  const bis = tage[tage.length - 1];
  const laden = useCallback(() => api.get(`/api/einsatzplan?von=${tage[0]}&bis=${bis}`).then(setD).catch((err) => toast.error(err.message)), [tage, bis]);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => { if (!kann('plantafel')) navigate('/einsaetze', { replace: true }); }, [kann, navigate]);

  const schritt = (n) => setVon((v) => (ansicht === 'tag' ? addDays(v, n) : addDays(v, n * (ansicht === 'monat' ? 28 : ansicht === '2wochen' ? 14 : 7))));
  const heute = () => setVon(ansicht === 'tag' ? new Date() : mondayOf(new Date()));
  const wechselAnsicht = (a) => { setAnsicht(a); setVon((v) => (a === 'tag' ? v : mondayOf(v))); };

  // ---- Aktionen
  const anlegenSchnell = async (projectId, userId, tag) => {
    const z = lesenZeiten();
    try {
      await api.post('/api/einsatzplan', { project_id: projectId, user_ids: [userId], dates: [tag], ...z });
      toast.success(`Einsatz ${fmtDateShort(fromKey(tag))} angelegt (${z.start_time}–${z.end_time})`, { action: { label: 'Öffnen', onClick: () => laden() } });
      laden();
    } catch (err) {
      if (err.status === 409 && err.message.includes('abwesend')) {
        if (window.confirm(`${err.message}\n\nTrotzdem planen?`)) { try { await api.post('/api/einsatzplan', { project_id: projectId, user_ids: [userId], dates: [tag], ...z, erzwingen: true }); laden(); } catch (e2) { toast.error(e2.message); } }
      } else toast.error(err.message);
    }
  };
  const verschieben = async (einsatz, userId, tag, kopie) => {
    if (einsatz.user_id === userId && einsatz.date === tag && !kopie) return;
    try {
      if (kopie) { const r = await api.post(`/api/einsatzplan/${einsatz.id}/kopieren`, { dates: [tag], user_ids: [userId] }); if (r.uebersprungen.length) toast.error(r.uebersprungen[0].grund); else toast.success('Einsatz kopiert'); }
      else { await api.put(`/api/einsatzplan/${einsatz.id}`, { user_id: userId, date: tag }); toast.success('Einsatz verschoben'); }
      laden();
    } catch (err) {
      if (err.status === 409 && err.message.includes('abwesend') && window.confirm(`${err.message}\n\nTrotzdem?`)) {
        try { if (kopie) await api.post(`/api/einsatzplan/${einsatz.id}/kopieren`, { dates: [tag], user_ids: [userId], erzwingen: true }); else await api.put(`/api/einsatzplan/${einsatz.id}`, { user_id: userId, date: tag, erzwingen: true }); laden(); } catch (e2) { toast.error(e2.message); }
      } else toast.error(err.message);
    }
  };

  // ---- Drag-and-drop (Maus); am Handy und per Tastatur über den Dialog
  const dragStart = (daten) => (e) => { dragRef.current = { ...daten, kopie: kopiermodus || e.altKey }; e.dataTransfer.effectAllowed = 'copyMove'; try { e.dataTransfer.setData('text/plain', daten.id); } catch { /* ignore */ } };
  const dropAuf = (userId, tag) => (e) => {
    e.preventDefault();
    const daten = dragRef.current;
    dragRef.current = null;
    if (!daten) return;
    if (daten.art === 'projekt') anlegenSchnell(daten.id, userId, tag);
    else if (daten.art === 'einsatz') verschieben(daten.einsatz, userId, tag, daten.kopie);
  };

  if (!d) return <Layout title="Plantafel" wide><Ladeanzeige /></Layout>;
  const projekte = d.projekte.filter((p) => !filter.suche || p.name.toLowerCase().includes(filter.suche.toLowerCase()));
  const mitarbeiter = d.mitarbeiter.filter((m) => (!filter.kolonne || m.kolonne_id === filter.kolonne || (filter.kolonne === 'ohne' && !m.kolonne_id)));
  const gruppen = [...d.kolonnen.map((k) => ({ id: k.id, name: k.name, farbe: k.farbe, leute: mitarbeiter.filter((m) => m.kolonne_id === k.id) })), { id: 'ohne', name: d.kolonnen.length ? 'Ohne Kolonne' : 'Mitarbeiter', farbe: null, leute: mitarbeiter.filter((m) => !m.kolonne_id) }].filter((g) => g.leute.length);
  const einsaetze = d.einsaetze.filter((e) => (abgesagte || e.status !== 'abgesagt') && (!filter.projekt || e.project_id === filter.projekt));
  const zelle = (uid, tag) => einsaetze.filter((e) => e.user_id === uid && e.date === tag);
  const abwesend = (uid, tag) => d.abwesenheiten.find((a) => a.user_id === uid && a.from_date <= tag && a.to_date >= tag);
  const kapazitaet = (uid) => { const k = d.kapazitaet.filter((x) => x.user_id === uid && x.woche >= toKey(mondayOf(fromKey(tage[0]))) && x.woche <= bis); const g = k.reduce((s, x) => s + x.geplant_minuten, 0); const soll = k[0]?.soll_minuten || 0; return { geplant: g, soll: soll * Math.max(1, Math.round(tage.length / 7)), ueber: k.some((x) => x.ueber) }; };
  const vergangene = einsaetze.filter((e) => e.date < d.heute && e.status === 'geplant');
  const zuPruefen = vergangene.filter((e) => e.abgleich?.status !== 'freigegeben');

  return (
    <Layout wide title="Plantafel" subtitle="Projekte auf Mitarbeiter ziehen, Einsätze verschieben oder kopieren (Alt gedrückt halten oder Kopiermodus), vergangene Tage mit der Stempelung abgleichen und freigeben."
      action={<div className="flex gap-2"><Btn variant="soft" size="sm" onClick={() => setKolonnenDialog(true)}><Users size={15} /> Kolonnen</Btn><Btn size="sm" onClick={() => setDialog({ neu: { date: tage[0] } })}><Plus size={16} /> Einsatz</Btn></div>}>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex items-center gap-1.5"><IconBtn variant="soft" onClick={() => schritt(-1)} title="Zurück"><ChevronLeft size={18} /></IconBtn><Btn variant="ghost" size="sm" onClick={heute}>Heute</Btn><IconBtn variant="soft" onClick={() => schritt(1)} title="Weiter"><ChevronRight size={18} /></IconBtn></div>
        <div className="text-[14px] font-semibold">{fmtDate(fromKey(tage[0]))}{tage.length > 1 ? ` – ${fmtDate(fromKey(bis))}` : ''}</div>
        <Segmented value={ansicht} onChange={wechselAnsicht} options={ANSICHTEN} />
        <Select value={filter.kolonne} onChange={(e) => setFilter({ ...filter, kolonne: e.target.value })}><option value="">Alle Kolonnen</option>{d.kolonnen.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}{d.kolonnen.length > 0 && <option value="ohne">Ohne Kolonne</option>}</Select>
        <Select value={filter.projekt} onChange={(e) => setFilter({ ...filter, projekt: e.target.value })}><option value="">Alle Projekte</option>{d.projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>
        <Chip active={kopiermodus} onClick={() => setKopiermodus((k) => !k)} title="Ziehen kopiert statt verschiebt"><Copy size={13} /> Kopiermodus</Chip>
        <Chip active={abgesagte} onClick={() => setAbgesagte((a) => !a)}>Abgesagte zeigen</Chip>
        <Chip active={abgleich} onClick={() => setAbgleich((a) => !a)}><ListChecks size={13} /> Zeiten prüfen{zuPruefen.length ? ` (${zuPruefen.length})` : ''}</Chip>
      </div>

      {abgleich && (
        <Card className="p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2"><h2 className="text-[16px] flex items-center gap-2"><ListChecks size={16} /> Arbeitszeiten prüfen und freigeben</h2><span className="text-[12px] text-[#6E6E73]">Hinweise sind keine Vorwürfe. Die Freigabe legt die anrechenbare Zeit fest; die Stempelung bleibt dokumentiert.</span></div>
          {vergangene.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Im angezeigten Zeitraum liegen keine vergangenen Einsätze.</p> : (
            <ul className="divide-y divide-black/[0.06]">{vergangene.map((e) => (
              <li key={e.id} className="py-2 flex flex-wrap items-center gap-3 text-[14px]">
                <span className="w-24 text-[#6E6E73]">{fmtDateShort(fromKey(e.date))}</span><span className="font-medium w-40 truncate">{e.mitarbeiter}</span><span className="flex-1 min-w-[160px] truncate">{e.projekt.name} · geplant {e.start_time}–{e.end_time}</span>
                <span className="text-[12px] text-[#6E6E73]">{e.abgleich.status === 'fehlt' ? 'keine Stempelung' : e.abgleich.start_time ? `gestempelt ${e.abgleich.start_time}–${e.abgleich.end_time} (${stunden(e.abgleich.net_minutes || 0)} h)` : ''}{e.abgleich.hinweise?.length ? ` · ${e.abgleich.hinweise.join(', ')}` : ''}</span>
                <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${ABGLEICH_CLS[e.abgleich.status]}`}>{e.abgleich.status_name}</span>
                <Btn size="sm" variant={e.abgleich.status === 'freigegeben' ? 'ghost' : 'soft'} onClick={() => setDialog({ einsatz: e })}>{e.abgleich.status === 'freigegeben' ? 'Ansehen' : 'Prüfen'}</Btn>
              </li>
            ))}</ul>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[13px]"><FileText size={14} className="text-[#6E6E73]" /> Projekt-Stundenzettel aus freigegebenen Zeiten:
            <Select value={pdfProjekt} onChange={(e) => setPdfProjekt(e.target.value)}><option value="">Projekt wählen</option>{d.projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>
            <Btn size="sm" variant="soft" disabled={!pdfProjekt} onClick={() => download(`/api/einsatzplan/stundenzettel.pdf?project_id=${pdfProjekt}&von=${tage[0]}&bis=${bis}`).catch((err) => toast.error(err.message))}>PDF ({fmtDateShort(fromKey(tage[0]))}–{fmtDateShort(fromKey(bis))})</Btn>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        <Card className="p-3 self-start lg:sticky lg:top-4">
          <div className="relative mb-2"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#86868B]" /><TextInput value={filter.suche} onChange={(e) => setFilter({ ...filter, suche: e.target.value })} placeholder="Projekt suchen" className="h-9 pl-8 text-[13px]" /></div>
          <p className="text-[11px] text-[#86868B] mb-1.5 hidden lg:block">Projekt auf eine Zelle ziehen = Einsatz mit den letzten Zeiten ({lesenZeiten().start_time}–{lesenZeiten().end_time}).</p>
          <ul className="space-y-1 max-h-[60vh] overflow-y-auto">{projekte.map((p) => (
            <li key={p.id} draggable onDragStart={dragStart({ art: 'projekt', id: p.id })} className="flex items-center gap-2 rounded-xl px-2 py-1.5 bg-[#F5F5F7] cursor-grab active:cursor-grabbing text-[13px]">
              <GripVertical size={14} className="text-[#C7C7CC] shrink-0" /><span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: p.color || '#C41E3A' }} /><span className="truncate flex-1">{p.name}</span>
              <button type="button" className="text-[11px] text-[#C41E3A] font-medium" onClick={() => setDialog({ neu: { project_id: p.id, date: tage[0] } })} title="Einsatz anlegen">+</button>
            </li>
          ))}</ul>
          {projekte.length === 0 && <p className="text-[13px] text-[#6E6E73]">Kein Projekt gefunden.</p>}
        </Card>

        <Card className="overflow-x-auto">
          <table className="min-w-full text-[12px] border-collapse">
            <thead>
              <tr>
                <th className="sticky left-0 bg-white z-10 text-left px-3 py-2 font-semibold text-[12px] w-44 border-b border-black/[0.06]">Mitarbeiter</th>
                {tage.map((t) => { const dt = fromKey(t); const frei = d.feiertage[t]; const istHeute = t === d.heute; return <th key={t} className={cn('px-1 py-2 font-semibold text-center border-b border-black/[0.06] min-w-[112px]', frei && 'text-[#B25E00]', istHeute && 'text-[#C41E3A]')} title={frei || ''}>{WEEKDAYS_DE[(dt.getDay() + 6) % 7]} {fmtDateShort(dt)}{frei ? <span className="block text-[10px] font-normal">{frei}</span> : null}</th>; })}
                <th className="px-2 py-2 font-semibold text-right border-b border-black/[0.06] whitespace-nowrap">Geplant</th>
              </tr>
            </thead>
            <tbody>
              {gruppen.map((g) => (
                <React.Fragment key={g.id}>
                  <tr><td colSpan={tage.length + 2} className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#6E6E73] bg-[#FAFAFA] border-b border-black/[0.06]"><span className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle" style={{ background: g.farbe || '#C7C7CC' }} />{g.name}</td></tr>
                  {g.leute.map((m) => {
                    const k = kapazitaet(m.id);
                    return (
                      <tr key={m.id} className="border-b border-black/[0.06]">
                        <td className="sticky left-0 bg-white z-10 px-3 py-1.5 font-medium text-[13px] truncate max-w-[176px]">{m.name}<span className="block text-[10px] text-[#86868B] font-normal">{m.role === 'vorarbeiter' ? 'Vorarbeiter' : m.role === 'buero' ? 'Büro' : m.weekly_hours ? `${m.weekly_hours} h/Woche` : ''}</span></td>
                        {tage.map((t) => {
                          const liste = zelle(m.id, t);
                          const a = abwesend(m.id, t);
                          const frei = d.feiertage[t];
                          return (
                            <td key={t} onDragOver={(e) => e.preventDefault()} onDrop={dropAuf(m.id, t)} className={cn('align-top p-1 min-w-[112px] h-14', frei && 'bg-[#FFF8EC]', t === d.heute && 'bg-[#C41E3A]/[0.03]', a && 'bg-[#F5F5F7]')}>
                              <div className="flex flex-col gap-1">
                                {a && <span className={cn('text-[10px] font-semibold rounded-md px-1.5 py-0.5', a.status === 'genehmigt' ? 'bg-[#E8F0FE] text-[#1D4ED8]' : 'bg-[#FFF4E5] text-[#B25E00]')}>{ABWESENHEIT[a.type] || a.type}{a.status === 'beantragt' ? ' (beantragt)' : ''}</span>}
                                {liste.map((e) => (
                                  <button key={e.id} type="button" draggable={e.status === 'geplant' && !e.freigabe} onDragStart={dragStart({ art: 'einsatz', id: e.id, einsatz: e })} onClick={() => setDialog({ einsatz: e })}
                                    className={cn('text-left rounded-lg px-1.5 py-1 leading-tight text-white shadow-sm', e.status === 'abgesagt' && 'opacity-40 line-through', e.status === 'geplant' && !e.freigabe && 'cursor-grab')} style={{ background: e.projekt.color || '#C41E3A' }}
                                    aria-label={`${e.projekt.name} ${e.start_time} bis ${e.end_time}`} title={`${e.projekt.name} · ${e.start_time}–${e.end_time}${e.note ? ` · ${e.note}` : ''}`}>
                                    <span className="block font-semibold truncate">{e.projekt.name}</span>
                                    <span className="block text-[10px] opacity-90">{e.start_time}–{e.end_time}{e.date < d.heute && e.abgleich ? ` · ${e.abgleich.status === 'freigegeben' ? '✓ frei' : e.abgleich.status === 'fehlt' ? '✗ Stempel' : e.abgleich.status === 'abweichung' ? '⚠ Abw.' : '✓'}` : ''}</span>
                                  </button>
                                ))}
                                <button type="button" onClick={() => setDialog({ neu: { user_id: m.id, date: t, project_id: filter.projekt || '' } })} className="h-5 rounded-md text-[11px] text-[#A1A1A6] hover:text-[#C41E3A] hover:bg-black/[0.04]" aria-label={`Einsatz für ${m.name} am ${fmtDate(fromKey(t))} anlegen`}>+</button>
                              </div>
                            </td>
                          );
                        })}
                        <td className={cn('px-2 py-1.5 text-right whitespace-nowrap', k.ueber && 'text-[#C41E3A] font-semibold')} title={k.ueber ? 'Über den Wochenstunden' : ''}>{stunden(k.geplant)}{k.soll ? ` / ${stunden(k.soll)}` : ''} h</td>
                      </tr>
                    );
                  })}
                </React.Fragment>
              ))}
              {gruppen.length === 0 && <tr><td colSpan={tage.length + 2} className="px-3 py-6 text-center text-[#6E6E73]">Keine aktiven Mitarbeiter.</td></tr>}
            </tbody>
          </table>
        </Card>
      </div>

      <EinsatzDialog offen={dialog} onClose={() => setDialog(null)} daten={d} onChanged={laden} />
      <KolonnenDialog open={kolonnenDialog} onOpenChange={setKolonnenDialog} daten={d} onChanged={laden} />
    </Layout>
  );
}

/** Einsatz anlegen (eine oder mehrere Personen, ein Tag oder Zeitraum) oder bearbeiten; dazu Kopieren, Absagen, Rückgängig und – bei vergangenen Tagen – Abgleich und Freigabe. */
function EinsatzDialog({ offen, onClose, daten, onChanged }) {
  const { bestaetigen, fragen } = useDialoge();
  const e = offen?.einsatz || null;
  const neu = offen?.neu || null;
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState('');
  const [kopie, setKopie] = useState({ datum: '', user_ids: [] });
  const [freigabe, setFreigabe] = useState(null);
  useEffect(() => {
    if (e) { setF({ project_id: e.project_id, user_ids: [e.user_id], date: e.date, zeitraum: false, start_time: e.start_time, end_time: e.end_time, pause_minutes: e.pause_minutes, address: e.address || '', taetigkeit: e.taetigkeit || '', note: e.note || '', kolonne_id: e.kolonne_id || '', erzwingen: false }); setFreigabe(e.abgleich?.status !== 'offen' && !e.freigabe ? { start_time: e.abgleich?.start_time || e.start_time, end_time: e.abgleich?.end_time || e.end_time, pause_minutes: e.pause_minutes, grund: '', bestaetigt: false } : null); }
    else if (neu) { const z = lesenZeiten(); setF({ project_id: neu.project_id || daten.projekte[0]?.id || '', user_ids: neu.user_id ? [neu.user_id] : [], date: neu.date, zeitraum: false, from_date: neu.date, to_date: neu.date, weekdays: [0, 1, 2, 3, 4], ...z, address: '', taetigkeit: '', note: '', kolonne_id: '', erzwingen: false }); setFreigabe(null); }
    else setF(null);
    setKopie({ datum: '', user_ids: [] });
  }, [e, neu, daten]);
  if (!f) return <Sheet open={false} onOpenChange={() => {}} title="" />;
  const set = (k) => (ev) => { const v = ev.target.value; setF((x) => ({ ...x, [k]: v })); };
  const toggleUser = (id) => setF((x) => ({ ...x, user_ids: x.user_ids.includes(id) ? x.user_ids.filter((u) => u !== id) : [...x.user_ids, id] }));
  const toggleTag = (t) => setF((x) => ({ ...x, weekdays: x.weekdays.includes(t) ? x.weekdays.filter((y) => y !== t) : [...x.weekdays, t].sort() }));
  const speichern = async (ev) => {
    ev.preventDefault();
    setBusy('speichern');
    try {
      const zeiten = { start_time: f.start_time, end_time: f.end_time, pause_minutes: parseInt(f.pause_minutes, 10) || 0 };
      merkenZeiten(zeiten);
      if (e) await api.put(`/api/einsatzplan/${e.id}`, { project_id: f.project_id, user_id: f.user_ids[0], date: f.date, ...zeiten, address: f.address, taetigkeit: f.taetigkeit, note: f.note, kolonne_id: f.kolonne_id || null, erzwingen: f.erzwingen });
      else { if (!f.user_ids.length) throw new Error('Bitte mindestens eine Person wählen.'); const r = await api.post('/api/einsatzplan', { project_id: f.project_id, user_ids: f.user_ids, ...(f.zeitraum ? { from_date: f.from_date, to_date: f.to_date, weekdays: f.weekdays } : { dates: [f.date] }), ...zeiten, address: f.address, taetigkeit: f.taetigkeit, note: f.note, kolonne_id: f.kolonne_id || null, erzwingen: f.erzwingen }); toast.success(`${r.einsaetze.length} Einsätze geplant`); }
      onChanged(); onClose();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const aktion = async (pfad, body, meldung, methode = 'post') => { setBusy(pfad); try { if (methode === 'del') await api.del(pfad); else await api.post(pfad, body || {}); toast.success(meldung); onChanged(); onClose(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const absagen = async () => { const grund = await fragen({ titel: 'Einsatz absagen', text: 'Die Person wird informiert, wenn der Einsatz heute oder morgen ist. Der Einsatz lässt sich wiederherstellen.', feld: 'Grund (optional)', ok: 'Absagen', gefaehrlich: true }); if (grund !== null) aktion(`/api/einsatzplan/${e.id}?grund=${encodeURIComponent(grund)}`, null, 'Einsatz abgesagt', 'del'); };
  const kopieren = async () => {
    const dates = kopie.datum ? [kopie.datum] : [];
    const user_ids = kopie.user_ids.length ? kopie.user_ids : [];
    if (!dates.length && !user_ids.length) { toast.error('Bitte ein Datum oder Personen wählen.'); return; }
    setBusy('kopieren');
    try { const r = await api.post(`/api/einsatzplan/${e.id}/kopieren`, { dates, user_ids }); toast.success(`${r.einsaetze.length} Kopien angelegt${r.uebersprungen.length ? `, ${r.uebersprungen.length} übersprungen: ${r.uebersprungen[0].grund}` : ''}`); onChanged(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const freigeben = async () => {
    setBusy('freigabe');
    try { await api.post(`/api/einsatzplan/${e.id}/freigabe`, { start_time: freigabe.start_time, end_time: freigabe.end_time, pause_minutes: parseInt(freigabe.pause_minutes, 10) || 0, grund: freigabe.grund, arbeitsleistung_bestaetigt: freigabe.bestaetigt }); toast.success('Arbeitszeit freigegeben'); onChanged(); onClose(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const freigabeZurueck = async () => { if (await bestaetigen({ titel: 'Freigabe zurücknehmen?', text: 'Der Zeiteintrag geht auf die ursprüngliche Stempelung zurück; ein ohne Stempelung angelegter Eintrag wird entfernt.', ok: 'Zurücknehmen', gefaehrlich: true })) aktion(`/api/einsatzplan/${e.id}/freigabe-zuruecknehmen`, {}, 'Freigabe zurückgenommen'); };
  const vergangen = e && e.date < daten.heute;
  const gesperrt = !!e?.freigabe;
  return (
    <Sheet open={!!offen} onOpenChange={(o) => { if (!o) onClose(); }} title={e ? `Einsatz ${fmtDate(fromKey(e.date))}` : 'Einsatz anlegen'} subtitle={e ? `${e.mitarbeiter} · ${e.projekt.name}${e.status === 'abgesagt' ? ' · abgesagt' : ''}` : 'Eine oder mehrere Personen, ein Tag oder ein Zeitraum mit Wochentagen.'} width="sm:max-w-2xl">
      <form onSubmit={speichern} className="space-y-4">
        {gesperrt && <div className="rounded-2xl bg-[#E8F8EC] text-[#1B7F3B] px-4 py-3 text-[13px]">Freigegeben von {e.freigabe.von_name}: {e.freigabe.start_time}–{e.freigabe.end_time}, {stunden(e.freigabe.net_minutes)} h{e.freigabe.grund ? ` – „${e.freigabe.grund}“` : ''}. Zum Ändern zuerst die Freigabe zurücknehmen.</div>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Projekt"><Select value={f.project_id} onChange={set('project_id')} className="w-full" disabled={gesperrt} required>{daten.projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
          <Field label="Kolonne (optional)"><Select value={f.kolonne_id} onChange={set('kolonne_id')} className="w-full" disabled={gesperrt}><option value="">–</option>{daten.kolonnen.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}</Select></Field>
        </div>
        {e ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Mitarbeiter"><Select value={f.user_ids[0]} onChange={(ev) => setF({ ...f, user_ids: [ev.target.value] })} className="w-full" disabled={gesperrt}>{daten.mitarbeiter.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Select></Field>
            <Field label="Datum"><TextInput type="date" value={f.date} onChange={set('date')} disabled={gesperrt} /></Field>
          </div>
        ) : (
          <>
            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Mitarbeiter {f.kolonne_id && <button type="button" className="text-[#C41E3A] font-medium ml-2" onClick={() => setF({ ...f, user_ids: daten.mitarbeiter.filter((m) => m.kolonne_id === f.kolonne_id).map((m) => m.id) })}>ganze Kolonne</button>}</span>
              <div className="flex flex-wrap gap-1.5">{daten.mitarbeiter.map((m) => <Chip key={m.id} active={f.user_ids.includes(m.id)} onClick={() => toggleUser(m.id)}>{m.name}</Chip>)}</div>
            </div>
            <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={f.zeitraum} onChange={(v) => setF({ ...f, zeitraum: v })} label="Zeitraum mit Wochentagen (wiederkehrend)" /></div>
            {f.zeitraum ? (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Von"><TextInput type="date" value={f.from_date} onChange={set('from_date')} /></Field><Field label="Bis"><TextInput type="date" value={f.to_date} onChange={set('to_date')} /></Field>
                <div className="col-span-2 flex flex-wrap gap-1.5">{WEEKDAYS_DE.map((w, i) => <Chip key={w} active={f.weekdays.includes(i)} onClick={() => toggleTag(i)}>{w}</Chip>)}</div>
              </div>
            ) : <Field label="Datum"><TextInput type="date" value={f.date} onChange={set('date')} /></Field>}
          </>
        )}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Beginn"><TextInput type="time" value={f.start_time} onChange={set('start_time')} disabled={gesperrt} /></Field>
          <Field label="Ende"><TextInput type="time" value={f.end_time} onChange={set('end_time')} disabled={gesperrt} /></Field>
          <Field label="Pause (Min.)"><TextInput type="number" min="0" max="600" value={f.pause_minutes} onChange={set('pause_minutes')} disabled={gesperrt} /></Field>
        </div>
        <Field label="Einsatzadresse (leer = Projektadresse)"><TextInput value={f.address} onChange={set('address')} disabled={gesperrt} placeholder="Straße, Ort, Treffpunkt" /></Field>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Tätigkeit"><TextInput value={f.taetigkeit} onChange={set('taetigkeit')} disabled={gesperrt} placeholder="z. B. Unterhaltsreinigung EG" /></Field>
          <Field label="Hinweis für die Person"><TextInput value={f.note} onChange={set('note')} disabled={gesperrt} placeholder="z. B. Treffpunkt Tor B, Schlüssel beim Hausmeister" /></Field>
        </div>
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={f.erzwingen} onChange={(v) => setF({ ...f, erzwingen: v })} label="Trotz Abwesenheit planen" hint="Nur wenn Urlaub oder Krankheit wirklich nicht gelten." /></div>
        {!gesperrt && <div className="flex flex-wrap justify-end gap-2"><Btn type="button" variant="soft" onClick={onClose}>Abbrechen</Btn><Btn type="submit" loading={busy === 'speichern'}>{e ? 'Speichern' : 'Planen'}</Btn></div>}
      </form>
      {e && (
        <div className="mt-5 space-y-4">
          {!gesperrt && (
            <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-2">
              <span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Copy size={14} /> Kopieren</span>
              <div className="flex flex-wrap gap-2 items-end"><Field label="Auf Datum"><TextInput type="date" value={kopie.datum} onChange={(ev) => setKopie({ ...kopie, datum: ev.target.value })} /></Field>
                <div className="flex-1 min-w-[200px]"><span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Für Personen</span><div className="flex flex-wrap gap-1">{daten.mitarbeiter.filter((m) => m.id !== e.user_id).map((m) => <Chip key={m.id} active={kopie.user_ids.includes(m.id)} onClick={() => setKopie({ ...kopie, user_ids: kopie.user_ids.includes(m.id) ? kopie.user_ids.filter((x) => x !== m.id) : [...kopie.user_ids, m.id] })}>{m.name}</Chip>)}</div></div>
                <Btn size="sm" variant="dark" onClick={kopieren} loading={busy === 'kopieren'}>Kopieren</Btn></div>
            </div>
          )}
          {vergangen && !gesperrt && freigabe && e.status === 'geplant' && (
            <div className="rounded-2xl border border-[#F59E0B]/40 p-4 space-y-3">
              <div className="text-[14px] font-semibold flex items-center gap-2"><ListChecks size={15} /> Abgleich mit der Stempelung: <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${ABGLEICH_CLS[e.abgleich.status]}`}>{e.abgleich.status_name}</span></div>
              <p className="text-[13px] text-[#6E6E73]">Geplant {e.start_time}–{e.end_time} ({stunden(e.planned_minutes)} h). {e.abgleich.status === 'fehlt' ? 'Keine Stempelung an diesem Tag.' : `Gestempelt ${e.abgleich.start_time}–${e.abgleich.end_time} (${stunden(e.abgleich.net_minutes || 0)} h).`}{e.abgleich.hinweise?.length ? ` Hinweise: ${e.abgleich.hinweise.join('; ')}.` : ''} Die Stempelung bleibt dokumentiert; hier legst du die anrechenbare Zeit fest.</p>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Anrechenbar von"><TextInput type="time" value={freigabe.start_time} onChange={(ev) => setFreigabe({ ...freigabe, start_time: ev.target.value })} /></Field>
                <Field label="Bis"><TextInput type="time" value={freigabe.end_time} onChange={(ev) => setFreigabe({ ...freigabe, end_time: ev.target.value })} /></Field>
                <Field label="Pause (Min.)"><TextInput type="number" min="0" max="600" value={freigabe.pause_minutes} onChange={(ev) => setFreigabe({ ...freigabe, pause_minutes: ev.target.value })} /></Field>
              </div>
              <Field label="Begründung (bei Abweichung oder fehlender Stempelung Pflicht)"><TextArea rows={2} value={freigabe.grund} onChange={(ev) => setFreigabe({ ...freigabe, grund: ev.target.value })} placeholder="z. B. Vor Ort pünktlich begonnen, Stempeluhr später geöffnet" /></Field>
              <label className="flex items-start gap-2 text-[13px]"><input type="checkbox" className="mt-0.5" checked={freigabe.bestaetigt} onChange={(ev) => setFreigabe({ ...freigabe, bestaetigt: ev.target.checked })} /> Ich habe die tatsächlich geleistete Arbeit geprüft und bestätige sie.</label>
              <div className="flex justify-end"><Btn size="sm" onClick={freigeben} loading={busy === 'freigabe'}>Arbeitszeit freigeben</Btn></div>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {gesperrt && <Btn size="sm" variant="soft" onClick={freigabeZurueck} loading={busy.includes('zuruecknehmen')}><Undo2 size={14} /> Freigabe zurücknehmen</Btn>}
            {!gesperrt && e.status === 'geplant' && e.verlauf?.some((v) => v.vorher && v.aktion !== 'rueckgaengig') && <Btn size="sm" variant="soft" onClick={() => aktion(`/api/einsatzplan/${e.id}/rueckgaengig`, {}, 'Letzte Änderung zurückgenommen')} loading={busy.includes('rueckgaengig')}><Undo2 size={14} /> Rückgängig</Btn>}
            {!gesperrt && e.status === 'geplant' && <Btn size="sm" variant="danger" onClick={absagen} loading={busy.includes(e.id) && busy.includes('grund')}>Absagen</Btn>}
            {e.status === 'abgesagt' && <Btn size="sm" onClick={() => aktion(`/api/einsatzplan/${e.id}/wiederherstellen`, {}, 'Einsatz wiederhergestellt')}>Wiederherstellen</Btn>}
          </div>
          {e.verlauf?.length > 0 && <ul className="text-[12px] text-[#6E6E73] space-y-0.5">{e.verlauf.slice().reverse().slice(0, 8).map((v, i) => <li key={i}>{new Date(v.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} · {v.aktion} · {v.user_name}{v.vorher?.date && v.vorher.date !== e.date ? ` · vorher ${fmtDateShort(fromKey(v.vorher.date))}` : ''}{v.vorher?.start_time && v.vorher.start_time !== e.start_time ? ` · vorher ${v.vorher.start_time}–${v.vorher.end_time}` : ''}{v.text ? ` · ${v.text}` : ''}</li>)}</ul>}
        </div>
      )}
    </Sheet>
  );
}

/** Kolonnen (Trupps): Name, Farbe, Mitglieder, Vorarbeiter. */
function KolonnenDialog({ open, onOpenChange, daten, onChanged }) {
  const { bestaetigen } = useDialoge();
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  const speichern = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    try { if (f.id) await api.put(`/api/einsatzplan/kolonnen/${f.id}`, { name: f.name, user_ids: f.user_ids, vorarbeiter_id: f.vorarbeiter_id || null, farbe: f.farbe }); else await api.post('/api/einsatzplan/kolonnen', { name: f.name, user_ids: f.user_ids, vorarbeiter_id: f.vorarbeiter_id || null, farbe: f.farbe }); toast.success('Kolonne gespeichert'); setF(null); onChanged(); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (k) => { if (!(await bestaetigen({ titel: `Kolonne „${k.name}“ löschen?`, text: 'Einsätze bleiben erhalten, nur die Zuordnung fällt weg.', ok: 'Löschen', gefaehrlich: true }))) return; try { await api.del(`/api/einsatzplan/kolonnen/${k.id}`); onChanged(); } catch (err) { toast.error(err.message); } };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Kolonnen" subtitle="Feste Trupps planen sich mit einem Klick als Ganzes. Mitglieder sehen ihre Kollegen im Einsatz.">
      <div className="space-y-4">
        {daten.kolonnen.length === 0 && !f && <p className="text-[14px] text-[#6E6E73]">Noch keine Kolonne.</p>}
        <ul className="divide-y divide-black/[0.06]">{daten.kolonnen.map((k) => <li key={k.id} className="py-2 flex items-center gap-2 text-[14px]"><span className="w-3 h-3 rounded-full" style={{ background: k.farbe || '#1D4ED8' }} /><span className="flex-1 min-w-0 truncate font-medium">{k.name}<span className="text-[12px] text-[#6E6E73] font-normal"> · {(k.user_ids || []).length} Personen</span></span><Btn size="sm" variant="ghost" onClick={() => setF({ id: k.id, name: k.name, user_ids: k.user_ids || [], vorarbeiter_id: k.vorarbeiter_id || '', farbe: k.farbe || '#1D4ED8' })}>Bearbeiten</Btn><Btn size="sm" variant="ghost" onClick={() => loeschen(k)}>Löschen</Btn></li>)}</ul>
        {f ? (
          <form onSubmit={speichern} className="space-y-3 rounded-2xl bg-[#F5F5F7] p-4">
            <div className="grid grid-cols-[1fr_auto] gap-3"><Field label="Name"><TextInput value={f.name} onChange={(ev) => setF({ ...f, name: ev.target.value })} required placeholder="z. B. Trupp Nord" /></Field><Field label="Farbe"><input type="color" value={f.farbe} onChange={(ev) => setF({ ...f, farbe: ev.target.value })} className="h-11 w-14 rounded-xl border-0 bg-transparent" /></Field></div>
            <div><span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Mitglieder</span><div className="flex flex-wrap gap-1.5">{daten.mitarbeiter.map((m) => <Chip key={m.id} active={f.user_ids.includes(m.id)} onClick={() => setF({ ...f, user_ids: f.user_ids.includes(m.id) ? f.user_ids.filter((x) => x !== m.id) : [...f.user_ids, m.id] })}>{m.name}</Chip>)}</div></div>
            <Field label="Vorarbeiter (optional)"><Select value={f.vorarbeiter_id} onChange={(ev) => setF({ ...f, vorarbeiter_id: ev.target.value })} className="w-full"><option value="">–</option>{daten.mitarbeiter.filter((m) => f.user_ids.includes(m.id)).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Select></Field>
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setF(null)}>Abbrechen</Btn><Btn type="submit" loading={busy}>Speichern</Btn></div>
          </form>
        ) : <Btn variant="soft" onClick={() => setF({ name: '', user_ids: [], vorarbeiter_id: '', farbe: '#1D4ED8' })}><Plus size={15} /> Neue Kolonne</Btn>}
      </div>
    </Sheet>
  );
}
