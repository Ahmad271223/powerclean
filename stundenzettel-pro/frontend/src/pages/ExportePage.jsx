import React, { useCallback, useEffect, useState } from 'react';
import { FileDown, FileText, Table2, ShieldCheck, Smartphone, Lock, Unlock } from 'lucide-react';
import { toast } from 'sonner';
import Layout from '../components/Layout';
import { Btn, Card, Field, Select, TextInput } from '../components/ui';
import { api, download } from '../lib/api';
import { useAuth } from '../lib/auth';
import { MONTHS_DE, toKey, monthLastDay, MIN_YEAR, MAX_YEAR } from '../lib/dates';
import { milogPdf } from '../lib/pdf';
import { deliverPdf } from '../lib/utils';

const YEARS = Array.from({ length: MAX_YEAR - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i);
const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

export default function ExportePage() {
  const { isInhaber } = useAuth();
  const heute = new Date();
  const [jahr, setJahr] = useState(heute.getFullYear());
  const [monat, setMonat] = useState(heute.getMonth());
  const [von, setVon] = useState(toKey(new Date(heute.getFullYear(), heute.getMonth(), 1)));
  const [bis, setBis] = useState(toKey(monthLastDay(heute.getFullYear(), heute.getMonth())));
  const [mitarbeiter, setMitarbeiter] = useState([]);
  const [ma, setMa] = useState('');
  const [busy, setBusy] = useState('');
  const [abschluesse, setAbschluesse] = useState([]);
  useEffect(() => { api.get('/api/mitarbeiter').then((r) => { setMitarbeiter(r.mitarbeiter); if (r.mitarbeiter[0]) setMa(r.mitarbeiter[0].id); }).catch(() => {}); }, []);
  const abschluesseLaden = useCallback(() => api.get('/api/abschluss').then((r) => setAbschluesse(r.abschluesse)).catch(() => {}), []);
  useEffect(() => { abschluesseLaden(); }, [abschluesseLaden]);

  const holen = async (key, pfad) => { setBusy(key); try { await download(pfad); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const nachweis = async () => {
    if (!ma) return;
    setBusy('milog');
    try { const d = await api.get(`/api/exporte/milog?jahr=${jahr}&monat=${monat + 1}&user_id=${ma}`); await deliverPdf(milogPdf(d.firma, d.mitarbeiter, jahr, monat + 1, d.eintraege, d.abwesenheiten, d.feiertage || {})); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const abgeschlossen = abschluesse.find((a) => a.year === jahr && a.month === monat + 1);
  const abschliessen = async () => {
    if (!window.confirm(`${MONTHS_DE[monat]} ${jahr} abschließen? Danach kann niemand mehr Zeiten in diesem Monat ändern, bis du ihn wieder öffnest.`)) return;
    setBusy('abschluss');
    try { const r = await api.post('/api/abschluss', { year: jahr, month: monat + 1 }); toast.success(`${MONTHS_DE[monat]} ${jahr} abgeschlossen (${r.eintraege} Einträge)`); abschluesseLaden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const oeffnen = async () => {
    setBusy('abschluss');
    try { await api.del(`/api/abschluss/${jahr}/${monat + 1}`); toast.success('Monat wieder geöffnet'); abschluesseLaden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };

  return (
    <Layout title="Exporte & Abschluss" subtitle="Für Lohnbüro, Steuerberater und Prüfungen. Alle Dateien öffnen sich in Excel (Semikolon-getrennt).">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5 space-y-4">
          <h2 className="text-[17px] flex items-center gap-2"><Table2 size={18} /> Lohn &amp; Monat</h2>
          <div className="flex gap-2 flex-wrap">
            <Select value={monat} onChange={(e) => setMonat(Number(e.target.value))}>{MONTHS_DE.map((m, i) => <option key={m} value={i}>{m}</option>)}</Select>
            <Select value={jahr} onChange={(e) => setJahr(Number(e.target.value))}>{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}</Select>
          </div>
          <div className="flex flex-col gap-2">
            <Btn onClick={() => holen('lohn', `/api/exporte/lohn.csv?jahr=${jahr}&monat=${monat + 1}`)} loading={busy === 'lohn'}><FileDown size={16} /> Lohnexport je Eintrag (CSV)</Btn>
            <Btn variant="soft" onClick={() => holen('summen', `/api/exporte/lohn-summen.csv?jahr=${jahr}&monat=${monat + 1}`)} loading={busy === 'summen'}><FileDown size={16} /> Summen je Mitarbeiter mit Soll, Saldo, Resturlaub (CSV)</Btn>
            <Btn variant="soft" onClick={() => holen('abw', `/api/exporte/abwesenheiten.csv?jahr=${jahr}`)} loading={busy === 'abw'}><FileDown size={16} /> Abwesenheiten {jahr} (CSV)</Btn>
          </div>
          <p className="text-[12px] text-[#86868B]">Personalnummer, Datum, Beginn, Ende, Pause, Netto-Stunden je Zeile. Die Summen-Datei enthält Arbeitstage, Stunden, Urlaubs- und Kranktage, Sollstunden und Stundenkonto je Person (DATEV-Import über die Vorlage des Steuerberaters).</p>
        </Card>

        <Card className="p-5 space-y-4">
          <h2 className="text-[17px] flex items-center gap-2">{abgeschlossen ? <Lock size={18} /> : <Unlock size={18} />} Monatsabschluss</h2>
          <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[14px]">
            <div className="font-semibold">{MONTHS_DE[monat]} {jahr}: {abgeschlossen ? 'abgeschlossen' : 'offen'}</div>
            <div className="text-[#6E6E73] mt-0.5">{abgeschlossen ? `Abgeschlossen von ${abgeschlossen.closed_by} am ${fmtZeit(abgeschlossen.closed_at)}. Zeiten in diesem Monat sind für alle gesperrt.` : 'Nach dem Lohnlauf abschließen: dann kann niemand mehr Zeiten in diesem Monat ändern.'}</div>
          </div>
          {abgeschlossen ? <Btn variant="soft" onClick={oeffnen} loading={busy === 'abschluss'}><Unlock size={16} /> Monat wieder öffnen</Btn> : <Btn onClick={abschliessen} loading={busy === 'abschluss'}><Lock size={16} /> {MONTHS_DE[monat]} {jahr} abschließen</Btn>}
          {abschluesse.length > 0 && <p className="text-[12px] text-[#86868B]">Abgeschlossen: {abschluesse.map((a) => `${String(a.month).padStart(2, '0')}/${a.year}`).join(', ')}</p>}
        </Card>

        <Card className="p-5 space-y-4">
          <h2 className="text-[17px] flex items-center gap-2"><ShieldCheck size={18} /> Arbeitszeitnachweis (§ 17 MiLoG)</h2>
          <Field label="Mitarbeiter"><Select value={ma} onChange={(e) => setMa(e.target.value)} className="w-full">{mitarbeiter.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Select></Field>
          <Btn onClick={nachweis} loading={busy === 'milog'} disabled={!ma}><FileText size={16} /> Nachweis {MONTHS_DE[monat]} {jahr} als PDF</Btn>
          <p className="text-[12px] text-[#86868B]">Beginn, Ende und Dauer je Arbeitstag mit Feiertagen, Abwesenheiten und Unterschriftsfeldern. Für die Gebäudereinigung Pflicht (Aufzeichnung bis zum 7. Folgetag, zwei Jahre aufbewahren). Änderungen stehen im Protokoll.</p>
        </Card>

        <Card className="p-5 space-y-4">
          <h2 className="text-[17px] flex items-center gap-2"><Table2 size={18} /> Zeiten nach Zeitraum</h2>
          <div className="grid grid-cols-2 gap-3"><Field label="Von"><TextInput type="date" value={von} onChange={(e) => setVon(e.target.value)} /></Field><Field label="Bis"><TextInput type="date" value={bis} onChange={(e) => setBis(e.target.value)} /></Field></div>
          <Btn variant="soft" onClick={() => holen('zeiten', `/api/exporte/zeiten.csv?von=${von}&bis=${bis}`)} loading={busy === 'zeiten'}><FileDown size={16} /> Alle Zeiten (CSV)</Btn>
          <Btn variant="ghost" size="sm" onClick={() => holen('prot', '/api/exporte/protokoll.csv')} loading={busy === 'prot'}><FileDown size={15} /> Sicherheitsprotokoll (CSV)</Btn>
        </Card>

        {isInhaber && (
          <Card className="p-5 space-y-4">
            <h2 className="text-[17px] flex items-center gap-2"><Smartphone size={18} /> Sicherung &amp; Rückweg</h2>
            <Btn variant="soft" onClick={() => holen('sich', '/api/exporte/sicherung.json')} loading={busy === 'sich'}><FileDown size={16} /> Komplettsicherung (JSON)</Btn>
            <Btn variant="soft" onClick={() => holen('free', '/api/exporte/free-app.json')} loading={busy === 'free'}><FileDown size={16} /> Daten für die kostenlose App</Btn>
            <p className="text-[12px] text-[#86868B]">Deine Daten gehören dir: Die Sicherung enthält alles außer Passwörtern und Dateien. Die zweite Datei lässt sich in der kostenlosen Stundenzettel-App unter „Datensicherung → Wiederherstellen“ einspielen.</p>
          </Card>
        )}
      </div>
    </Layout>
  );
}
