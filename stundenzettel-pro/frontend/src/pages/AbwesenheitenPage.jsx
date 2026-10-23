import React, { useCallback, useEffect, useState } from 'react';
import { Plus, Check, X, Trash2, CalendarOff, Pencil, List, CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import AbwesenheitDialog, { ABWESENHEIT_LABEL } from '../components/AbwesenheitDialog';
import { Btn, Card, Chip, Empty, IconBtn, Segmented, Select } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate, fromKey, MONTHS_DE, monthLastDay, toKey, addDays, clampMonth, MIN_YEAR, MAX_YEAR } from '../lib/dates';

const STATUS_CLS = { genehmigt: 'bg-[#E8F8EC] text-[#1B7F3B]', abgelehnt: 'bg-[#C41E3A]/10 text-[#C41E3A]', beantragt: 'bg-[#FFF4E5] text-[#B25E00]' };
const FARBEN = { urlaub: '#34C759', krank: '#C41E3A', feiertag: '#1D4ED8', unbezahlt: '#86868B', sonstiges: '#7C3AED' };
const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);

export default function AbwesenheitenPage() {
  const { isBuero, user } = useAuth();
  const [ansicht, setAnsicht] = useState('liste');
  const [liste, setListe] = useState(null);
  const [filter, setFilter] = useState('alle');
  const [mitarbeiter, setMitarbeiter] = useState([]);
  const [dialog, setDialog] = useState(false);
  const [edit, setEdit] = useState(null);
  const laden = useCallback(async () => {
    try {
      const r = await api.get('/api/abwesenheiten');
      setListe(r.abwesenheiten);
      if (isBuero) setMitarbeiter((await api.get('/api/mitarbeiter')).mitarbeiter);
    } catch (err) { toast.error(err.message); }
  }, [isBuero]);
  useEffect(() => { laden(); }, [laden]);

  const status = async (a, st) => { try { await api.put(`/api/abwesenheiten/${a.id}/status`, { status: st }); toast.success(st === 'genehmigt' ? 'Genehmigt' : 'Abgelehnt'); laden(); } catch (err) { toast.error(err.message); } };
  const loeschen = async (a) => { if (!window.confirm('Eintrag löschen?')) return; try { await api.del(`/api/abwesenheiten/${a.id}`); laden(); } catch (err) { toast.error(err.message); } };
  const tage = (a) => Math.round((fromKey(a.to_date) - fromKey(a.from_date)) / 86400000) + 1;
  const gefiltert = (liste || []).filter((a) => filter === 'alle' || a.status === filter);
  const offen = (liste || []).filter((a) => a.status === 'beantragt').length;

  return (
    <Layout title={isBuero ? 'Abwesenheiten' : 'Meine Abwesenheiten'} subtitle={isBuero ? `${offen} offene Anträge` : 'Urlaub beantragen, Krankheit melden.'} wide={ansicht === 'kalender'}
      action={<Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={18} /> {isBuero ? 'Eintragen' : 'Beantragen'}</Btn>}>
      {isBuero && (
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <Segmented value={ansicht} onChange={setAnsicht} options={[{ value: 'liste', label: 'Liste', icon: List }, { value: 'kalender', label: 'Teamkalender', icon: CalendarDays }]} />
          {ansicht === 'liste' && <div className="flex gap-2 flex-wrap">{[['alle', 'Alle'], ['beantragt', `Offen (${offen})`], ['genehmigt', 'Genehmigt'], ['abgelehnt', 'Abgelehnt']].map(([v, l]) => <Chip key={v} active={filter === v} onClick={() => setFilter(v)}>{l}</Chip>)}</div>}
        </div>
      )}
      {ansicht === 'kalender' && isBuero ? <Teamkalender mitarbeiter={mitarbeiter} /> : !liste ? <Ladeanzeige /> : gefiltert.length === 0 ? <Card><Empty icon={CalendarOff} title="Keine Einträge" /></Card> : (
        <div className="space-y-2">
          {gefiltert.map((a) => (
            <Card key={a.id} className="p-4 flex flex-wrap items-center gap-3">
              <span className="w-2.5 h-10 rounded-full shrink-0" style={{ backgroundColor: FARBEN[a.type] || '#86868B' }} />
              <div className="flex-1 min-w-[220px]">
                <div className="text-[15px] font-semibold">{isBuero ? `${a.user_name} · ` : ''}{ABWESENHEIT_LABEL[a.type] || a.type}</div>
                <div className="text-[13px] text-[#6E6E73]">{fmtDate(fromKey(a.from_date))} – {fmtDate(fromKey(a.to_date))} · {tage(a)} {tage(a) === 1 ? 'Tag' : 'Tage'}{a.note ? ` · ${a.note}` : ''}</div>
                {a.decided_by && a.status !== 'beantragt' && <div className="text-[12px] text-[#86868B]">{a.status} von {a.decided_by}{a.decision_note ? ` · ${a.decision_note}` : ''}</div>}
              </div>
              <span className={`text-[11px] font-semibold rounded-full px-2.5 py-1 ${STATUS_CLS[a.status] || ''}`}>{a.status}</span>
              {isBuero && a.status === 'beantragt' && <><Btn size="sm" onClick={() => status(a, 'genehmigt')}><Check size={15} /> Genehmigen</Btn><Btn size="sm" variant="soft" onClick={() => status(a, 'abgelehnt')}><X size={15} /> Ablehnen</Btn></>}
              {(isBuero || (a.user_id === user?.id && a.status === 'beantragt')) && <><IconBtn size={32} onClick={() => { setEdit(a); setDialog(true); }} title="Bearbeiten"><Pencil size={15} /></IconBtn><IconBtn size={32} variant="danger" onClick={() => loeschen(a)} title="Löschen"><Trash2 size={15} /></IconBtn></>}
            </Card>
          ))}
        </div>
      )}
      <AbwesenheitDialog open={dialog} onOpenChange={setDialog} abwesenheit={edit} mitarbeiter={mitarbeiter} onSaved={laden} />
    </Layout>
  );
}

/** Monatsraster: Zeile je Mitarbeiter, Spalte je Tag; Urlaub/Krank farbig, Feiertage und Wochenenden grau. */
function Teamkalender({ mitarbeiter }) {
  const today = new Date();
  const [{ year, month }, setYm] = useState(clampMonth(today.getFullYear(), today.getMonth()));
  const [daten, setDaten] = useState(null);
  useEffect(() => {
    setDaten(null);
    const von = toKey(new Date(year, month, 1));
    const bis = toKey(monthLastDay(year, month));
    Promise.all([api.get(`/api/abwesenheiten?von=${von}&bis=${bis}`), api.get(`/api/feiertage?jahr=${year}`)])
      .then(([a, f]) => setDaten({ abwesenheiten: a.abwesenheiten.filter((x) => x.status !== 'abgelehnt'), feiertage: Object.fromEntries(f.feiertage.map((x) => [x.date, x.name])) }))
      .catch((err) => toast.error(err.message));
  }, [year, month]);
  const prev = () => setYm(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 });
  const next = () => setYm(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 });
  const tageImMonat = monthLastDay(year, month).getDate();
  const tage = Array.from({ length: tageImMonat }, (_, i) => new Date(year, month, i + 1));
  const heute = toKey(today);
  const zelle = (uid, key) => (daten?.abwesenheiten || []).find((a) => a.user_id === uid && a.from_date <= key && a.to_date >= key);
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-1.5"><IconBtn variant="soft" onClick={prev}><ChevronLeft size={18} /></IconBtn><Select value={month} onChange={(e) => setYm({ year, month: Number(e.target.value) })}>{MONTHS_DE.map((m, i) => <option key={m} value={i}>{m}</option>)}</Select><Select value={year} onChange={(e) => setYm({ year: Number(e.target.value), month })}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select><IconBtn variant="soft" onClick={next}><ChevronRight size={18} /></IconBtn></div>
        <div className="flex flex-wrap gap-3 text-[12px] text-[#6E6E73]">{Object.entries(ABWESENHEIT_LABEL).map(([k, l]) => <span key={k} className="flex items-center gap-1"><span className="w-3 h-3 rounded" style={{ backgroundColor: FARBEN[k] }} /> {l}</span>)}<span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#FFE4B5]" /> Feiertag</span></div>
      </div>
      {!daten ? <Ladeanzeige /> : (
        <div className="overflow-x-auto"><table className="text-[12px] border-collapse w-full">
          <thead><tr><th className="sticky left-0 bg-white text-left px-3 py-2 text-[11px] uppercase tracking-wider text-[#86868B] min-w-[150px]">Mitarbeiter</th>{tage.map((d) => { const k = toKey(d); const we = d.getDay() === 0 || d.getDay() === 6; return <th key={k} title={daten.feiertage[k] || ''} className={`px-0 py-1 font-medium text-center min-w-[26px] ${k === heute ? 'text-[#C41E3A]' : we ? 'text-[#A1A1A6]' : 'text-[#6E6E73]'}`}>{d.getDate()}<div className="text-[9px] font-normal">{['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'][d.getDay()]}</div></th>; })}</tr></thead>
          <tbody>
            {mitarbeiter.filter((m) => m.active !== false).map((m) => (
              <tr key={m.id} className="border-t border-black/[0.05]">
                <td className="sticky left-0 bg-white px-3 py-1.5 font-medium whitespace-nowrap">{m.name}</td>
                {tage.map((d) => {
                  const k = toKey(d);
                  const a = zelle(m.id, k);
                  const we = d.getDay() === 0 || d.getDay() === 6;
                  const frei = daten.feiertage[k];
                  return <td key={k} title={a ? `${ABWESENHEIT_LABEL[a.type]}${a.status === 'beantragt' ? ' (beantragt)' : ''}${a.note ? `: ${a.note}` : ''}` : frei || ''} className={`h-7 p-0.5 ${frei ? 'bg-[#FFE4B5]/50' : we ? 'bg-[#F5F5F7]' : ''}`}>{a && <div className="h-full rounded" style={{ backgroundColor: FARBEN[a.type], opacity: a.status === 'beantragt' ? 0.45 : 1 }} />}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <div className="px-4 py-2 text-[11px] text-[#86868B]">Blasse Farbe = noch nicht genehmigt. Resturlaub je Mitarbeiter unter „Auswertung → Stundenkonten“.</div>
    </Card>
  );
}

export { addDays };
