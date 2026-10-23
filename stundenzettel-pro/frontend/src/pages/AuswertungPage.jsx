import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, FileDown, FileText, Users, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Chip, Field, Segmented, Select, TextInput } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { MONTHS_DE, fmtDecimalHours, fmtEur, fmtHours, fmtSigned, monthLastDay, toKey, MIN_YEAR, MAX_YEAR } from '../lib/dates';
import { tabellePdf } from '../lib/pdf';
import { deliverPdf, downloadBlob } from '../lib/utils';

const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);
const GRUPPEN = [['projekt', 'Projekte'], ['kunde', 'Kunden'], ['mitarbeiter', 'Mitarbeiter'], ['leistung', 'Leistungen'], ['monat', 'Monate']];

const csv = (head, rows, name) => {
  const z = [head, ...rows].map((r) => r.map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n');
  downloadBlob(new Blob(['﻿' + z], { type: 'text/csv;charset=utf-8' }), name);
};

export default function AuswertungPage() {
  const [tab, setTab] = useState('zeiten');
  return (
    <Layout title="Auswertung" subtitle="Stunden und Umsatz nach Kunde, Projekt, Mitarbeiter oder Leistung – und die Stundenkonten des Teams.">
      <div className="flex justify-center mb-5"><Segmented value={tab} onChange={setTab} options={[{ value: 'zeiten', label: 'Zeiten & Umsatz', icon: BarChart3 }, { value: 'konten', label: 'Stundenkonten', icon: Users }]} /></div>
      {tab === 'zeiten' ? <Zeiten /> : <Konten />}
    </Layout>
  );
}

function zeitraum(preset) {
  const h = new Date();
  const y = h.getFullYear();
  const m = h.getMonth();
  if (preset === 'monat') return [toKey(new Date(y, m, 1)), toKey(monthLastDay(y, m))];
  if (preset === 'vormonat') { const d = new Date(y, m - 1, 1); return [toKey(d), toKey(monthLastDay(d.getFullYear(), d.getMonth()))]; }
  if (preset === 'quartal') { const q = Math.floor(m / 3) * 3; return [toKey(new Date(y, q, 1)), toKey(monthLastDay(y, q + 2))]; }
  return [`${y}-01-01`, `${y}-12-31`];
}

function Zeiten() {
  const { firma } = useAuth();
  const [preset, setPreset] = useState('monat');
  const [[von, bis], setBereich] = useState(zeitraum('monat'));
  const [gruppe, setGruppe] = useState('projekt');
  const [daten, setDaten] = useState(null);
  const laden = useCallback(() => { setDaten(null); api.get(`/api/auswertung?von=${von}&bis=${bis}&gruppe=${gruppe}`).then(setDaten).catch((err) => toast.error(err.message)); }, [von, bis, gruppe]);
  useEffect(() => { laden(); }, [laden]);
  const wahl = (p) => { setPreset(p); setBereich(zeitraum(p)); };
  const head = ['Name', 'Stunden', 'Tage', 'Einträge', 'Anteil %', 'Umsatz netto €'];
  const rows = (daten?.zeilen || []).map((z) => [gruppe === 'monat' ? `${MONTHS_DE[Number(z.name.slice(5, 7)) - 1]} ${z.name.slice(0, 4)}` : z.name, fmtDecimalHours(z.minuten), z.tage, z.eintraege, String(z.anteil).replace('.', ','), fmtEur(z.umsatz).replace(' €', '')]);
  const gesamt = daten ? ['Gesamt', fmtDecimalHours(daten.gesamt.minuten), daten.gesamt.tage, daten.gesamt.eintraege, '100', fmtEur(daten.gesamt.umsatz).replace(' €', '')] : null;
  const titel = `Auswertung ${GRUPPEN.find(([k]) => k === gruppe)?.[1]} ${von} – ${bis}`;
  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap gap-2 items-center">
          {[['monat', 'Dieser Monat'], ['vormonat', 'Vormonat'], ['quartal', 'Quartal'], ['jahr', 'Jahr'], ['frei', 'Zeitraum']].map(([p, l]) => <Chip key={p} active={preset === p} onClick={() => (p === 'frei' ? setPreset('frei') : wahl(p))}>{l}</Chip>)}
          {preset === 'frei' && <><TextInput type="date" value={von} onChange={(e) => setBereich([e.target.value, bis])} className="w-auto h-9" /><TextInput type="date" value={bis} onChange={(e) => setBereich([von, e.target.value])} className="w-auto h-9" /></>}
        </div>
        <div className="flex flex-wrap gap-2 items-center justify-between">
          <div className="flex flex-wrap gap-2">{GRUPPEN.map(([k, l]) => <Chip key={k} active={gruppe === k} onClick={() => setGruppe(k)}>{l}</Chip>)}</div>
          {daten && <div className="flex gap-2"><Btn size="sm" variant="soft" onClick={() => csv(head, [...rows, gesamt], `${titel}.csv`)}><FileDown size={14} /> CSV</Btn><Btn size="sm" variant="soft" onClick={() => deliverPdf(tabellePdf(firma, 'Auswertung', `${GRUPPEN.find(([k]) => k === gruppe)?.[1]} · ${von} – ${bis}`, head, [...rows, gesamt], `${titel}.pdf`, 'Umsatz netto aus Mitarbeiterstunden × Stundensatz (Leistung, Projekt oder Firmenstandard); ohne Zusatzpositionen.')).catch((e) => toast.error(e.message))}><FileText size={14} /> PDF</Btn></div>}
        </div>
      </Card>
      {!daten ? <Ladeanzeige /> : (
        <Card className="overflow-hidden">
          <div className="grid grid-cols-3 divide-x divide-black/[0.06] border-b border-black/[0.06]">
            {[['Stunden', fmtDecimalHours(daten.gesamt.minuten)], ['Umsatz netto', fmtEur(daten.gesamt.umsatz)], ['Einträge', `${daten.gesamt.eintraege} an ${daten.gesamt.tage} Tagen`]].map(([l, v]) => <div key={l} className="p-4"><div className="text-[12px] text-[#6E6E73]">{l}</div><div className="text-[20px] font-bold tracking-tight">{v}</div></div>)}
          </div>
          {daten.zeilen.length === 0 ? <p className="p-6 text-[14px] text-[#6E6E73]">Keine Zeiten im Zeitraum.</p> : (
            <div className="overflow-x-auto"><table className="w-full text-[14px]">
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B]"><th className="px-4 py-2">Name</th><th className="px-4 py-2 text-right">Stunden</th><th className="px-4 py-2 text-right">Tage</th><th className="px-4 py-2 text-right">Anteil</th><th className="px-4 py-2 text-right">Umsatz</th></tr></thead>
              <tbody>{daten.zeilen.map((z) => (
                <tr key={z.schluessel} className="border-t border-black/[0.04]">
                  <td className="px-4 py-2.5"><div className="font-medium">{gruppe === 'monat' ? `${MONTHS_DE[Number(z.name.slice(5, 7)) - 1]} ${z.name.slice(0, 4)}` : z.name}</div><div className="h-1.5 rounded-full bg-black/[0.05] mt-1 max-w-[240px]"><div className="h-full rounded-full bg-[#C41E3A]" style={{ width: `${z.anteil}%` }} /></div></td>
                  <td className="px-4 py-2.5 text-right font-semibold">{fmtHours(z.minuten)}</td><td className="px-4 py-2.5 text-right">{z.tage}</td><td className="px-4 py-2.5 text-right text-[#6E6E73]">{String(z.anteil).replace('.', ',')} %</td><td className="px-4 py-2.5 text-right font-semibold">{fmtEur(z.umsatz)}</td>
                </tr>))}</tbody>
            </table></div>
          )}
        </Card>
      )}
    </div>
  );
}

function Konten() {
  const navigate = useNavigate();
  const { firma } = useAuth();
  const h = new Date();
  const [jahr, setJahr] = useState(h.getFullYear());
  const [monat, setMonat] = useState(h.getMonth());
  const [daten, setDaten] = useState(null);
  useEffect(() => { setDaten(null); api.get(`/api/konto/uebersicht?jahr=${jahr}&monat=${monat + 1}`).then(setDaten).catch((err) => toast.error(err.message)); }, [jahr, monat]);
  const head = ['Mitarbeiter', 'Nr.', 'Soll Monat', 'Ist Monat', 'Saldo Monat', 'Saldo gesamt', 'Resturlaub'];
  const rows = (daten?.zeilen || []).map((z) => [z.name, z.personalnummer, fmtDecimalHours(z.soll_minuten), fmtDecimalHours(z.ist_minuten), fmtSigned(z.saldo_monat), fmtSigned(z.saldo_gesamt), String(z.resturlaub).replace('.', ',')]);
  return (
    <div className="space-y-4">
      <Card className="p-4 flex flex-wrap items-center gap-2 justify-between">
        <div className="flex gap-2"><Select value={monat} onChange={(e) => setMonat(Number(e.target.value))}>{MONTHS_DE.map((m, i) => <option key={m} value={i}>{m}</option>)}</Select><Select value={jahr} onChange={(e) => setJahr(Number(e.target.value))}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select></div>
        {daten && <div className="flex gap-2"><Btn size="sm" variant="soft" onClick={() => csv(head, rows, `Stundenkonten_${jahr}-${String(monat + 1).padStart(2, '0')}.csv`)}><FileDown size={14} /> CSV</Btn><Btn size="sm" variant="soft" onClick={() => deliverPdf(tabellePdf(firma, 'Stundenkonten', `${MONTHS_DE[monat]} ${jahr}`, head, rows, `Stundenkonten_${jahr}-${monat + 1}.pdf`, 'Soll aus Wochenstunden und Arbeitstagen abzüglich Feiertage und Abwesenheiten; Saldo gesamt seit Kontostart inkl. Buchungen.')).catch((e) => toast.error(e.message))}><FileText size={14} /> PDF</Btn></div>}
      </Card>
      {!daten ? <Ladeanzeige /> : daten.zeilen.length === 0 ? <Card className="p-6 text-[14px] text-[#6E6E73]">Keine aktiven Mitarbeiter.</Card> : (
        <Card className="overflow-x-auto"><table className="w-full text-[14px]">
          <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B]"><th className="px-4 py-2">Mitarbeiter</th><th className="px-4 py-2 text-right">Soll</th><th className="px-4 py-2 text-right">Ist</th><th className="px-4 py-2 text-right">Saldo Monat</th><th className="px-4 py-2 text-right">Saldo gesamt</th><th className="px-4 py-2 text-right">Resturlaub</th><th /></tr></thead>
          <tbody>{daten.zeilen.map((z) => (
            <tr key={z.user_id} className="border-t border-black/[0.04] cursor-pointer hover:bg-black/[0.02]" onClick={() => navigate(`/mitarbeiter/${z.user_id}`)}>
              <td className="px-4 py-2.5"><div className="font-medium">{z.name}</div><div className="text-[12px] text-[#86868B]">{z.weekly_hours ? `${z.weekly_hours} Std./Woche` : 'ohne Sollstunden'}</div></td>
              <td className="px-4 py-2.5 text-right">{fmtHours(z.soll_minuten)}</td><td className="px-4 py-2.5 text-right">{fmtHours(z.ist_minuten)}</td>
              <td className={`px-4 py-2.5 text-right font-semibold ${z.saldo_monat < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{fmtSigned(z.saldo_monat)}</td>
              <td className={`px-4 py-2.5 text-right font-semibold ${z.saldo_gesamt < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{fmtSigned(z.saldo_gesamt)}</td>
              <td className="px-4 py-2.5 text-right">{String(z.resturlaub).replace('.', ',')} Tage</td><td className="px-2"><ChevronRight size={16} className="text-[#C7C7CC]" /></td>
            </tr>))}</tbody>
        </table></Card>
      )}
    </div>
  );
}
