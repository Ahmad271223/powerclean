import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronLeft, ChevronRight, ChevronDown, Copy, Link2, FileText, Paperclip, Trash2, ExternalLink, Plus, Check, X, Clock, Palmtree } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige, Warnungen } from '../components/Layout';
import AbwesenheitDialog, { ABWESENHEIT_LABEL } from '../components/AbwesenheitDialog';
import { ROLLEN } from '../components/MitarbeiterDialog';
import { AppIcon, Btn, Card, Chip, Field, IconBtn, Segmented, Select, TextArea, TextInput, Toggle } from '../components/ui';
import { api, openFile } from '../lib/api';
import { useAuth } from '../lib/auth';
import { MONTHS_DE, WEEKDAYS_DE, fmtDate, fmtHours, fmtDecimalHours, fmtSigned, fromKey, clampMonth, MIN_YEAR, MAX_YEAR, todayKey } from '../lib/dates';
import { milogPdf } from '../lib/pdf';
import { deliverPdf, initials } from '../lib/utils';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);
const BUCHUNGSARTEN = [['auszahlung', 'Auszahlung (−)'], ['ausgleich', 'Freizeitausgleich (−)'], ['korrektur', 'Korrektur (±)'], ['start', 'Startsaldo (±)']];

export default function MitarbeiterDetailPage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const [m, setM] = useState(null);
  const [tab, setTab] = useState('daten');
  const laden = useCallback(() => api.get(`/api/mitarbeiter/${userId}`).then((r) => setM(r.mitarbeiter)).catch((err) => { toast.error(err.message); navigate('/mitarbeiter'); }), [userId, navigate]);
  useEffect(() => { laden(); }, [laden]);

  return (
    <Layout>
      {!m ? <Ladeanzeige /> : (
        <>
          <div className="flex items-center gap-3 mb-5">
            <IconBtn onClick={() => navigate('/mitarbeiter')} title="Zurück"><ArrowLeft size={20} /></IconBtn>
            <AppIcon color="#1D1D1F" text={initials(m.name)} size={44} className="rounded-xl" />
            <div className="min-w-0"><div className="font-semibold text-[20px] leading-tight truncate">{m.name}</div><div className="text-[12px] text-[#6E6E73]">{m.rolle_name}{m.personalnummer ? ` · Nr. ${m.personalnummer}` : ''} · {m.email}</div></div>
          </div>
          <div className="flex justify-center mb-5 overflow-x-auto no-scrollbar">
            <Segmented value={tab} onChange={setTab} options={[{ value: 'daten', label: 'Mitarbeiterdaten' }, { value: 'konto', label: 'Konten' }, { value: 'abwesenheiten', label: 'Abwesenheiten' }, { value: 'stunden', label: 'Stundenübersicht' }, { value: 'akte', label: 'Personalakte' }]} />
          </div>
          {tab === 'daten' && <Daten m={m} onSaved={laden} />}
          {tab === 'konto' && <Konten m={m} />}
          {tab === 'abwesenheiten' && <Abwesenheiten m={m} />}
          {tab === 'stunden' && <Stunden m={m} />}
          {tab === 'akte' && <Personalakte userId={m.id} />}
        </>
      )}
    </Layout>
  );
}

function Daten({ m, onSaved }) {
  const { isInhaber, user, firma } = useAuth();
  const [form, setForm] = useState({ name: m.name, role: m.role, personalnummer: m.personalnummer || '', phone: m.phone || '', weekly_hours: m.weekly_hours || '', vacation_days: m.vacation_days || '', notes: m.notes || '', active: m.active !== false,
    workdays: m.workdays || null, balance_start_minutes: m.balance_start_minutes ? String(Math.round(m.balance_start_minutes / 6) / 10).replace('.', ',') : '', balance_start_date: m.balance_start_date || '', vacation_carryover: m.vacation_carryover || '', vacation_carryover_year: m.vacation_carryover_year || new Date().getFullYear() });
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState('');
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const firmenTage = firma?.workdays || [0, 1, 2, 3, 4];
  const tage = form.workdays || firmenTage;
  const toggleDay = (i) => setForm((f) => { const w = f.workdays || firmenTage; return { ...f, workdays: w.includes(i) ? w.filter((d) => d !== i) : [...w, i].sort() }; });
  const speichern = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put(`/api/mitarbeiter/${m.id}`, { ...form, weekly_hours: parseFloat(String(form.weekly_hours).replace(',', '.')) || 0, vacation_days: parseFloat(String(form.vacation_days).replace(',', '.')) || 0,
        workdays: form.workdays || firmenTage, balance_start_minutes: Math.round((parseFloat(String(form.balance_start_minutes).replace(',', '.')) || 0) * 60), balance_start_date: form.balance_start_date || null,
        vacation_carryover: parseFloat(String(form.vacation_carryover).replace(',', '.')) || 0, vacation_carryover_year: parseInt(form.vacation_carryover_year, 10) || new Date().getFullYear() });
      toast.success('Gespeichert'); onSaved();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const neuerLink = async () => { try { const r = await api.post(`/api/mitarbeiter/${m.id}/einladung`); setLink(r.einladung_link); } catch (err) { toast.error(err.message); } };
  const selbst = user?.id === m.id;
  return (
    <Card className="p-5 sm:p-7 max-w-3xl">
      {m.eingeladen && (
        <div className="mb-5 rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[14px] text-[#7A4100]">
          <div className="font-semibold flex items-center gap-2"><Link2 size={15} /> Einladung noch nicht angenommen</div>
          <div className="mt-1">Link erneut erzeugen und per WhatsApp schicken.</div>
          <div className="flex flex-wrap gap-2 mt-2"><Btn size="sm" variant="dark" onClick={neuerLink}>Neuen Link erzeugen</Btn>{link && <Btn size="sm" variant="soft" onClick={() => navigator.clipboard?.writeText(link).then(() => toast.success('Kopiert'))}><Copy size={14} /> Kopieren</Btn>}</div>
          {link && <div className="mt-2 break-all select-all text-[12px]">{link}</div>}
        </div>
      )}
      <form onSubmit={speichern} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Name"><TextInput value={form.name} onChange={set('name')} required /></Field>
          <Field label="Personalnummer"><TextInput value={form.personalnummer} onChange={set('personalnummer')} /></Field>
          <Field label="Telefon"><TextInput type="tel" value={form.phone} onChange={set('phone')} /></Field>
          <Field label="E-Mail"><TextInput value={m.email} disabled /></Field>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Rolle</span>
          <div className="flex gap-2 flex-wrap">{ROLLEN.filter(([v]) => v !== 'inhaber' || isInhaber || m.role === 'inhaber').map(([v, l]) => <Chip key={v} active={form.role === v} onClick={() => !selbst && setForm((f) => ({ ...f, role: v }))} disabled={selbst || (m.role === 'inhaber' && !isInhaber)}>{l}</Chip>)}</div>
          <span className="block text-[12px] text-[#86868B] mt-1.5">{ROLLEN.find(([v]) => v === form.role)?.[2]}</span>
        </div>
        <section className="space-y-3 rounded-2xl bg-[#F5F5F7] p-4">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-[#86868B]">Sollstunden &amp; Stundenkonto</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Wochenstunden (Soll)" hint="0 = kein Stundenkonto"><TextInput type="number" step="0.5" min="0" value={form.weekly_hours} onChange={set('weekly_hours')} placeholder="z. B. 40" className="bg-white" /></Field>
            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Arbeitstage</span>
              <div className="flex flex-wrap gap-1.5">{WEEKDAYS_DE.map((d, i) => <Chip key={d} active={tage.includes(i)} onClick={() => toggleDay(i)} className="h-8 px-3">{d}</Chip>)}</div>
            </div>
            <Field label="Startsaldo (Stunden, ± möglich)" hint="Überstunden aus der Zeit vor der App"><TextInput type="text" inputMode="decimal" value={form.balance_start_minutes} onChange={set('balance_start_minutes')} placeholder="z. B. 12,5 oder -3" className="bg-white" /></Field>
            <Field label="Konto zählt ab" hint="Leer = ab dem ersten Eintrag"><TextInput type="date" value={form.balance_start_date} onChange={set('balance_start_date')} className="bg-white" /></Field>
          </div>
        </section>
        <section className="space-y-3 rounded-2xl bg-[#F5F5F7] p-4">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-[#86868B]">Urlaub</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Urlaubstage pro Jahr"><TextInput type="number" step="0.5" min="0" value={form.vacation_days} onChange={set('vacation_days')} placeholder="z. B. 24" className="bg-white" /></Field>
            <Field label="Übertrag aus dem Vorjahr"><TextInput type="number" step="0.5" value={form.vacation_carryover} onChange={set('vacation_carryover')} placeholder="z. B. 3" className="bg-white" /></Field>
            <Field label="Übertrag gilt für Jahr"><TextInput type="number" min="2025" max="2100" value={form.vacation_carryover_year} onChange={set('vacation_carryover_year')} className="bg-white" /></Field>
          </div>
        </section>
        <Field label="Notizen (nur Büro)"><TextArea rows={3} value={form.notes} onChange={set('notes')} placeholder="Führerschein, Sprachen, Einsatzgebiete …" /></Field>
        {!selbst && <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={form.active} onChange={(v) => setForm((f) => ({ ...f, active: v }))} label="Konto aktiv" hint="Deaktivierte Mitarbeiter können sich nicht anmelden; Zeiten und Akte bleiben erhalten." /></div>}
        <div className="flex justify-end"><Btn type="submit" loading={busy}>Speichern</Btn></div>
      </form>
    </Card>
  );
}

/** Stundenkonto (Soll/Ist/Saldo je Monat, Buchungen) und Urlaubskonto. */
function Konten({ m }) {
  const today = new Date();
  const [{ year, month }, setYm] = useState(clampMonth(today.getFullYear(), today.getMonth()));
  const [k, setK] = useState(null);
  const [form, setForm] = useState({ date: todayKey(), stunden: '', type: 'auszahlung', note: '' });
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/mitarbeiter/${m.id}/konto?jahr=${year}&monat=${month + 1}`).then(setK).catch((err) => toast.error(err.message)), [m.id, year, month]);
  useEffect(() => { setK(null); laden(); }, [laden]);
  const prev = () => setYm(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 });
  const next = () => setYm(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 });
  const buchen = async (e) => {
    e.preventDefault();
    const std = parseFloat(String(form.stunden).replace(',', '.'));
    if (!std) { toast.error('Bitte Stunden angeben'); return; }
    let minuten = Math.round(std * 60);
    if ((form.type === 'auszahlung' || form.type === 'ausgleich') && minuten > 0) minuten = -minuten;
    setBusy(true);
    try { await api.post(`/api/mitarbeiter/${m.id}/konto/buchungen`, { date: form.date, minutes: minuten, type: form.type, note: form.note }); toast.success('Gebucht'); setForm({ ...form, stunden: '', note: '' }); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (b) => { if (!window.confirm('Buchung löschen?')) return; try { await api.del(`/api/konto/buchungen/${b.id}`); laden(); } catch (err) { toast.error(err.message); } };
  if (!k) return <Ladeanzeige />;
  const mon = k.monto || k.monat;
  const u = k.urlaub;
  return (
    <div className="space-y-4 max-w-4xl">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="p-4"><div className="text-[12px] text-[#6E6E73] flex items-center gap-1"><Clock size={13} /> Saldo gesamt</div><div className={`text-[24px] font-bold tracking-tight ${k.verlauf.saldo_minuten < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{k.mitarbeiter.weekly_hours ? fmtSigned(k.verlauf.saldo_minuten) : '–'}</div><div className="text-[11px] text-[#86868B]">{k.mitarbeiter.weekly_hours ? `seit ${fmtDate(fromKey(k.verlauf.start))}` : 'Wochenstunden unter „Mitarbeiterdaten“ setzen'}</div></Card>
        <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">{MONTHS_DE[month]}: Soll / Ist</div><div className="text-[24px] font-bold tracking-tight">{fmtHours(mon.ist_minuten)}</div><div className="text-[11px] text-[#86868B]">Soll {fmtHours(mon.soll_minuten)} · {fmtSigned(mon.saldo_minuten)}</div></Card>
        <Card className="p-4"><div className="text-[12px] text-[#6E6E73] flex items-center gap-1"><Palmtree size={13} /> Resturlaub {u.jahr}</div><div className="text-[24px] font-bold tracking-tight">{String(u.rest).replace('.', ',')}</div><div className="text-[11px] text-[#86868B]">{u.anspruch} + {u.uebertrag} Übertrag − {u.genommen} genommen − {u.geplant} geplant</div></Card>
        <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Beantragt</div><div className="text-[24px] font-bold tracking-tight">{u.beantragt} Tage</div><div className="text-[11px] text-[#86868B]">noch nicht entschieden</div></Card>
      </div>
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-[16px]">Verlauf Stundenkonto</h3>
          <div className="flex items-center gap-1.5"><IconBtn variant="soft" onClick={prev}><ChevronLeft size={18} /></IconBtn><Select value={month} onChange={(e) => setYm({ year, month: Number(e.target.value) })}>{MONTHS_DE.map((mm, i) => <option key={mm} value={i}>{mm}</option>)}</Select><Select value={year} onChange={(e) => setYm({ year: Number(e.target.value), month })}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select><IconBtn variant="soft" onClick={next}><ChevronRight size={18} /></IconBtn></div>
        </div>
        {!k.mitarbeiter.weekly_hours ? <p className="text-[14px] text-[#6E6E73]">Ohne Wochenstunden gibt es kein Soll und damit kein Stundenkonto.</p> : (
          <div className="overflow-x-auto"><table className="w-full text-[13px]">
            <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B] border-b border-black/[0.06]"><th className="py-2 pr-3">Monat</th><th className="py-2 pr-3 text-right">Soll</th><th className="py-2 pr-3 text-right">Ist</th><th className="py-2 pr-3 text-right">Abwesend</th><th className="py-2 pr-3 text-right">Buchungen</th><th className="py-2 pr-3 text-right">Saldo</th><th className="py-2 text-right">Kumuliert</th></tr></thead>
            <tbody>
              <tr className="border-b border-black/[0.04] text-[#6E6E73]"><td className="py-2 pr-3">Startsaldo</td><td colSpan={5} /><td className="py-2 text-right font-semibold">{fmtSigned(k.verlauf.startsaldo_minuten)}</td></tr>
              {k.verlauf.monate.map((z) => <tr key={`${z.jahr}-${z.monat}`} className={`border-b border-black/[0.04] ${z.jahr === year && z.monat === month + 1 ? 'bg-[#C41E3A]/5' : ''}`}><td className="py-2 pr-3 whitespace-nowrap">{MONTHS_DE[z.monat - 1]} {z.jahr}</td><td className="py-2 pr-3 text-right">{fmtHours(z.soll_minuten)}</td><td className="py-2 pr-3 text-right">{fmtHours(z.ist_minuten)}</td><td className="py-2 pr-3 text-right text-[#86868B]">{Object.entries(z.abwesend).filter(([, n]) => n).map(([a, n]) => `${n} ${ABWESENHEIT_LABEL[a] || a}`).join(', ') || '–'}</td><td className="py-2 pr-3 text-right">{z.buchungen_minuten ? fmtSigned(z.buchungen_minuten) : '–'}</td><td className={`py-2 pr-3 text-right font-semibold ${z.saldo_minuten < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{fmtSigned(z.saldo_minuten)}</td><td className={`py-2 text-right font-semibold ${z.kumuliert_minuten < 0 ? 'text-[#C41E3A]' : ''}`}>{fmtSigned(z.kumuliert_minuten)}</td></tr>)}
            </tbody>
          </table></div>
        )}
      </Card>
      <Card className="p-5 space-y-4">
        <h3 className="text-[16px]">Buchungen (Auszahlung, Freizeitausgleich, Korrektur)</h3>
        <form onSubmit={buchen} className="grid grid-cols-2 sm:grid-cols-[150px_120px_1fr_1fr_auto] gap-2 items-end">
          <Field label="Datum"><TextInput type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required /></Field>
          <Field label="Stunden"><TextInput type="text" inputMode="decimal" value={form.stunden} onChange={(e) => setForm({ ...form, stunden: e.target.value })} placeholder="z. B. 8" required /></Field>
          <Field label="Art"><select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full h-11 rounded-xl bg-[#F5F5F7] px-3.5 text-[15px] outline-none">{BUCHUNGSARTEN.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="Notiz"><TextInput value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="z. B. mit Lohn Oktober" /></Field>
          <Btn type="submit" loading={busy}><Plus size={16} /> Buchen</Btn>
        </form>
        {k.buchungen.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine Buchungen.</p> : (
          <ul className="divide-y divide-black/[0.06] text-[14px]">{k.buchungen.map((b) => <li key={b.id} className="py-2 flex items-center gap-3"><span className="w-24 text-[#6E6E73]">{fmtDate(fromKey(b.date))}</span><span className={`w-20 font-semibold ${b.minutes < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{fmtSigned(b.minutes)}</span><span className="flex-1 min-w-0 truncate">{BUCHUNGSARTEN.find(([v]) => v === b.type)?.[1] || b.type}{b.note ? ` · ${b.note}` : ''} <span className="text-[12px] text-[#86868B]">· {b.created_by}</span></span><IconBtn size={28} variant="danger" onClick={() => loeschen(b)} title="Löschen"><Trash2 size={14} /></IconBtn></li>)}</ul>
        )}
      </Card>
    </div>
  );
}

function Abwesenheiten({ m }) {
  const [liste, setListe] = useState(null);
  const [dialog, setDialog] = useState(false);
  const laden = useCallback(() => api.get(`/api/abwesenheiten?user_id=${m.id}`).then((r) => setListe(r.abwesenheiten)).catch((err) => toast.error(err.message)), [m.id]);
  useEffect(() => { laden(); }, [laden]);
  const status = async (a, st) => { try { await api.put(`/api/abwesenheiten/${a.id}/status`, { status: st }); laden(); } catch (err) { toast.error(err.message); } };
  const loeschen = async (a) => { if (!window.confirm('Eintrag löschen?')) return; try { await api.del(`/api/abwesenheiten/${a.id}`); laden(); } catch (err) { toast.error(err.message); } };
  const tage = (a) => Math.round((fromKey(a.to_date) - fromKey(a.from_date)) / 86400000) + 1;
  return (
    <Card className="p-5 max-w-3xl">
      <div className="flex items-center justify-between mb-3"><h2 className="text-[16px]">Abwesenheiten</h2><Btn size="sm" onClick={() => setDialog(true)}><Plus size={15} /> Eintragen</Btn></div>
      {!liste ? <Ladeanzeige /> : liste.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Keine Einträge.</p> : (
        <ul className="divide-y divide-black/[0.06]">
          {liste.map((a) => (
            <li key={a.id} className="py-2.5 flex flex-wrap items-center gap-2 text-[14px]">
              <div className="flex-1 min-w-[200px]"><span className="font-semibold">{ABWESENHEIT_LABEL[a.type] || a.type}</span> · {fmtDate(fromKey(a.from_date))} – {fmtDate(fromKey(a.to_date))} ({tage(a)} {tage(a) === 1 ? 'Tag' : 'Tage'}){a.note && <div className="text-[12px] text-[#6E6E73]">{a.note}</div>}</div>
              <span className={`text-[11px] font-semibold rounded-full px-2.5 py-1 ${a.status === 'genehmigt' ? 'bg-[#E8F8EC] text-[#1B7F3B]' : a.status === 'abgelehnt' ? 'bg-[#C41E3A]/10 text-[#C41E3A]' : 'bg-[#FFF4E5] text-[#B25E00]'}`}>{a.status}</span>
              {a.status === 'beantragt' && <><IconBtn size={30} onClick={() => status(a, 'genehmigt')} title="Genehmigen" className="text-[#1B7F3B]"><Check size={15} /></IconBtn><IconBtn size={30} onClick={() => status(a, 'abgelehnt')} title="Ablehnen" className="text-[#C41E3A]"><X size={15} /></IconBtn></>}
              <IconBtn size={30} variant="danger" onClick={() => loeschen(a)} title="Löschen"><Trash2 size={14} /></IconBtn>
            </li>
          ))}
        </ul>
      )}
      <AbwesenheitDialog open={dialog} onOpenChange={setDialog} abwesenheit={null} mitarbeiter={[m]} userId={m.id} onSaved={laden} />
    </Card>
  );
}

function Stunden({ m }) {
  const today = new Date();
  const [{ year, month }, setYm] = useState(clampMonth(today.getFullYear(), today.getMonth()));
  const [u, setU] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setU(null); api.get(`/api/mitarbeiter/${m.id}/uebersicht?jahr=${year}&monat=${month + 1}`).then(setU).catch((err) => toast.error(err.message)); }, [m.id, year, month]);
  const prev = () => setYm(month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 });
  const next = () => setYm(month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 });
  const nachweis = async () => {
    setBusy(true);
    try {
      const d = await api.get(`/api/exporte/milog?jahr=${year}&monat=${month + 1}&user_id=${m.id}`);
      await deliverPdf(milogPdf(d.firma, d.mitarbeiter, year, month + 1, d.eintraege, d.abwesenheiten, d.feiertage || {}));
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-1.5">
          <IconBtn variant="soft" onClick={prev}><ChevronLeft size={18} /></IconBtn>
          <Select value={month} onChange={(e) => setYm({ year, month: Number(e.target.value) })}>{MONTHS_DE.map((mm, i) => <option key={mm} value={i}>{mm}</option>)}</Select>
          <Select value={year} onChange={(e) => setYm({ year: Number(e.target.value), month })}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select>
          <IconBtn variant="soft" onClick={next}><ChevronRight size={18} /></IconBtn>
        </div>
        <Btn variant="soft" size="sm" onClick={nachweis} loading={busy}><FileText size={15} /> Arbeitszeitnachweis (§ 17 MiLoG) PDF</Btn>
      </div>
      {!u ? <Ladeanzeige /> : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            {[['Stunden', fmtDecimalHours(u.summe.minuten)], ['Arbeitstage', u.summe.arbeitstage], ['Urlaub', `${u.summe.urlaubstage} Tage`], ['Krank', `${u.summe.kranktage} Tage`]].map(([l, v]) => <div key={l} className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">{l}</div><div className="text-[22px] font-bold tracking-tight">{v}</div></div>)}
          </div>
          {u.eintraege.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Keine Zeiten in diesem Monat.</p> : (
            <div className="overflow-x-auto"><table className="w-full text-[13px]">
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B] border-b border-black/[0.06]"><th className="py-2 pr-3">Datum</th><th className="py-2 pr-3">Beginn</th><th className="py-2 pr-3">Ende</th><th className="py-2 pr-3">Pause</th><th className="py-2 pr-3">Netto</th><th className="py-2 pr-3">Projekt</th><th className="py-2">Quelle</th></tr></thead>
              <tbody>{u.eintraege.map((e) => <tr key={e.id} className="border-b border-black/[0.04]"><td className="py-2 pr-3 whitespace-nowrap">{fmtDate(fromKey(e.date))}<Warnungen liste={e.warnungen} klein /></td><td className="py-2 pr-3">{e.start_time}</td><td className="py-2 pr-3">{e.end_time}</td><td className="py-2 pr-3">{e.pause_minutes} Min.{e.pause_auto ? '*' : ''}</td><td className="py-2 pr-3 font-semibold">{fmtHours(e.net_minutes)}</td><td className="py-2 pr-3">{e.project_name}{e.service_name ? <span className="text-[#6E6E73]"> · {e.service_name}</span> : null}{e.activity ? <span className="text-[#6E6E73]"> · {e.activity}</span> : null}</td><td className="py-2 text-[#86868B]">{e.source === 'stempel' ? 'Stempeluhr' : e.source === 'stempel_offline' ? 'Stempeluhr (offline)' : e.source || 'manuell'}</td></tr>)}</tbody>
            </table></div>
          )}
        </>
      )}
    </Card>
  );
}

/** Personalakte wie ein Ordner: Kategorien aufklappen, Dateien je Kategorie hochladen. */
export function Personalakte({ userId, readOnly = false }) {
  const [daten, setDaten] = useState(null);
  const [offen, setOffen] = useState({});
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/mitarbeiter/${userId}/dokumente`).then(setDaten).catch((err) => toast.error(err.message)), [userId]);
  useEffect(() => { laden(); }, [laden]);
  if (!daten) return <Ladeanzeige />;
  const upload = async (kategorie, file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('datei', file); fd.append('kategorie', kategorie);
    setBusy(kategorie);
    try { await api.upload(`/api/mitarbeiter/${userId}/dokumente`, fd); toast.success('Datei abgelegt'); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const loeschen = async (d) => { if (!window.confirm(`„${d.filename}“ löschen?`)) return; try { await api.del(`/api/dokumente/${d.id}`); laden(); } catch (err) { toast.error(err.message); } };
  return (
    <Card className="p-2 sm:p-4 max-w-3xl">
      {daten.kategorien.map((k) => {
        const docs = daten.dokumente.filter((d) => d.category === k);
        const auf = !!offen[k];
        return (
          <div key={k} className="border-b border-black/[0.06] last:border-b-0">
            <button type="button" onClick={() => setOffen((o) => ({ ...o, [k]: !auf }))} className="w-full flex items-center justify-between gap-3 px-3 py-3.5 text-left">
              <span className="text-[15px] font-medium flex items-center gap-2">{k} <span className="text-[11px] font-semibold bg-black/[0.06] rounded-full px-2 py-0.5">{docs.length}</span></span>
              <ChevronDown size={18} className={`text-[#86868B] transition-transform ${auf ? 'rotate-180' : ''}`} />
            </button>
            {auf && (
              <div className="px-3 pb-3">
                {docs.length === 0 ? <p className="text-[13px] text-[#86868B] mb-2">Keine Dokumente.</p> : (
                  <ul className="divide-y divide-black/[0.06] mb-2">
                    {docs.map((d) => (
                      <li key={d.id} className="py-2 flex items-center gap-3 text-[14px]">
                        <FileText size={16} className="text-[#6E6E73]" />
                        <div className="flex-1 min-w-0"><div className="truncate font-medium">{d.filename}</div><div className="text-[12px] text-[#86868B]">{fmtZeit(d.created_at)} · {d.uploaded_by_name} · {Math.round(d.size / 1024)} KB{d.note ? ` · ${d.note}` : ''}</div></div>
                        <IconBtn size={30} onClick={() => openFile(`/api/dokumente/${d.id}/datei`).catch((err) => toast.error(err.message))} title="Öffnen"><ExternalLink size={15} /></IconBtn>
                        {!readOnly && <IconBtn size={30} variant="danger" onClick={() => loeschen(d)} title="Löschen"><Trash2 size={14} /></IconBtn>}
                      </li>
                    ))}
                  </ul>
                )}
                {!readOnly && <label className="inline-flex"><input type="file" className="hidden" accept="application/pdf,image/*,.doc,.docx,.xls,.xlsx,.txt" onChange={(e) => { upload(k, e.target.files?.[0]); e.target.value = ''; }} /><span className="inline-flex items-center gap-2 h-9 px-3.5 rounded-full bg-black/[0.05] text-[13px] font-semibold cursor-pointer">{busy === k ? <span className="w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" /> : <Paperclip size={14} />} Datei ablegen</span></label>}
              </div>
            )}
          </div>
        );
      })}
    </Card>
  );
}
