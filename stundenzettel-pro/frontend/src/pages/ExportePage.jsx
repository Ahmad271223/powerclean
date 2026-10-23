import React, { useCallback, useEffect, useState } from 'react';
import { FileDown, FileText, Table2, ShieldCheck, Smartphone, Lock, Unlock, Landmark } from 'lucide-react';
import { toast } from 'sonner';
import Layout from '../components/Layout';
import { Btn, Card, Field, Select, Sheet, TextInput } from '../components/ui';
import { api, download } from '../lib/api';
import { useAuth } from '../lib/auth';
import { MONTHS_DE, toKey, monthLastDay, MIN_YEAR, MAX_YEAR, fmtDecimalHours } from '../lib/dates';
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
  const [vorschau, setVorschau] = useState(null);
  const [datev, setDatev] = useState(false);
  useEffect(() => { api.get('/api/mitarbeiter').then((r) => { setMitarbeiter(r.mitarbeiter); if (r.mitarbeiter[0]) setMa(r.mitarbeiter[0].id); }).catch(() => {}); }, []);
  const abschluesseLaden = useCallback(() => api.get('/api/abschluss').then((r) => setAbschluesse(r.abschluesse)).catch(() => {}), []);
  useEffect(() => { abschluesseLaden(); }, [abschluesseLaden]);

  const holen = async (key, pfad) => { setBusy(key); try { await download(pfad); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const vorschauLaden = async () => { setBusy('vorschau'); try { setVorschau(await api.get(`/api/lohn/vorbereitung?jahr=${jahr}&monat=${monat + 1}`)); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
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

        <Card className="p-5 space-y-4 lg:col-span-2">
          <h2 className="text-[17px] flex items-center gap-2"><Landmark size={18} /> Lohnvorbereitung für Steuerberater / DATEV</h2>
          <p className="text-[13px] text-[#6E6E73]">Keine Lohnabrechnung in der App: Für {MONTHS_DE[monat]} {jahr} werden je Mitarbeiter Stunden gesamt, Nacht (20–6 Uhr), Sonntag, Feiertag, Überstunden, Urlaubs- und Kranktage sowie Stammdaten zusammengestellt. Zuschläge und Abzüge rechnet das Lohnbüro.</p>
          <div className="flex flex-wrap gap-2">
            <Btn onClick={() => holen('lv', `/api/lohn/vorbereitung.csv?jahr=${jahr}&monat=${monat + 1}`)} loading={busy === 'lv'}><FileDown size={16} /> Tabelle (CSV)</Btn>
            <Btn variant="soft" onClick={() => holen('lodas', `/api/lohn/lodas.txt?jahr=${jahr}&monat=${monat + 1}`)} loading={busy === 'lodas'}><FileDown size={16} /> DATEV LODAS-Importdatei</Btn>
            <Btn variant="soft" onClick={() => holen('lvpdf', `/api/lohn/vorbereitung.pdf?jahr=${jahr}&monat=${monat + 1}`)} loading={busy === 'lvpdf'}><FileText size={16} /> PDF zum Abzeichnen</Btn>
            <Btn variant="soft" onClick={() => holen('stamm', '/api/lohn/stammdaten.csv')} loading={busy === 'stamm'}><FileDown size={16} /> Stammdaten (einmalig)</Btn>
            <Btn variant="ghost" onClick={vorschauLaden} loading={busy === 'vorschau'}>Vorschau</Btn>
            <Btn variant="ghost" onClick={() => setDatev(true)}>DATEV-Einstellungen</Btn>
          </div>
          {vorschau && (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-3 font-medium">Pers.-Nr.</th><th className="py-1 pr-3 font-medium">Mitarbeiter</th><th className="py-1 pr-3 text-right font-medium">Std.</th><th className="py-1 pr-3 text-right font-medium">Nacht</th><th className="py-1 pr-3 text-right font-medium">So.</th><th className="py-1 pr-3 text-right font-medium">Feiertag</th><th className="py-1 pr-3 text-right font-medium">Überstd.</th><th className="py-1 pr-3 text-right font-medium">Urlaub</th><th className="py-1 pr-3 text-right font-medium">Krank</th></tr></thead>
                <tbody>{vorschau.mitarbeiter.map((m) => (
                  <tr key={m.user_id} className="border-t border-black/[0.06]"><td className="py-1 pr-3">{m.personalnummer || '–'}</td><td className="py-1 pr-3">{m.name}</td><td className="py-1 pr-3 text-right">{fmtDecimalHours(m.minuten)}</td><td className="py-1 pr-3 text-right">{fmtDecimalHours(m.nacht_minuten)}</td><td className="py-1 pr-3 text-right">{fmtDecimalHours(m.sonntag_minuten)}</td><td className="py-1 pr-3 text-right">{fmtDecimalHours(m.feiertag_minuten)}</td><td className="py-1 pr-3 text-right">{m.wochenstunden ? fmtDecimalHours(m.ueberstunden_minuten) : '–'}</td><td className="py-1 pr-3 text-right">{m.urlaubstage}</td><td className="py-1 pr-3 text-right">{m.kranktage}</td></tr>
                ))}</tbody>
              </table>
              {vorschau.mitarbeiter.some((m) => !m.personalnummer) && <p className="text-[12px] text-[#B25E00] mt-2">Ohne Personalnummer fehlt die Zeile in der LODAS-Datei (Mitarbeiter → Mitarbeiterdaten).</p>}
              {!Object.values(vorschau.lohn_export?.lohnarten || {}).some(Boolean) && <p className="text-[12px] text-[#B25E00] mt-2">Noch keine Lohnarten-Nummern hinterlegt: Die LODAS-Datei bleibt leer, bis unter „DATEV-Einstellungen“ mindestens „Stunden gesamt“ eingetragen ist.</p>}
            </div>
          )}
          <p className="text-[12px] text-[#86868B]">Steuer-ID, SV-Nummer und IBAN der Mitarbeiter (Mitarbeiter → Lohndaten) liegen verschlüsselt und erscheinen nur in der Stammdaten-Datei. Jeder Export steht im Sicherheitsprotokoll.</p>
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
            <Btn variant="soft" onClick={() => holen('sich', '/api/exporte/sicherung.json')} loading={busy === 'sich'}><FileDown size={16} /> Datensicherung (JSON)</Btn>
            <Btn variant="soft" onClick={() => holen('dateien', '/api/exporte/dateien.zip')} loading={busy === 'dateien'}><FileDown size={16} /> Dateien (Fotos, Dokumente) als ZIP</Btn>
            <Btn variant="soft" onClick={() => holen('free', '/api/exporte/free-app.json')} loading={busy === 'free'}><FileDown size={16} /> Daten für die kostenlose App</Btn>
            <p className="text-[12px] text-[#86868B]">Deine Daten gehören dir: Die Datensicherung enthält alle Daten der Firma außer Passwörtern und Schlüsseln; die Dateien kommen als eigenes ZIP dazu. Beides enthält Personaldaten – nur verschlüsselt und mit beschränktem Zugriff aufbewahren. Die zweite Datei lässt sich in der kostenlosen Stundenzettel-App unter „Datensicherung → Wiederherstellen“ einspielen.</p>
          </Card>
        )}
      </div>
      <DatevDialog open={datev} onOpenChange={setDatev} />
    </Layout>
  );
}

const LOHNARTEN = [['normal', 'Stunden gesamt'], ['ueberstunden', 'Überstunden (Saldo Monat)'], ['nacht', 'Nachtstunden 20–6 Uhr'], ['sonntag', 'Sonntagsstunden'], ['feiertag', 'Feiertagsstunden'], ['urlaub', 'Urlaubstage'], ['krank', 'Kranktage']];

/** Berater-/Mandantennummer und Lohnarten-Nummern für die LODAS-Importdatei – die Nummern gibt der Steuerberater vor. */
function DatevDialog({ open, onOpenChange }) {
  const [form, setForm] = useState({ berater_nr: '', mandanten_nr: '', bs_nr: 1, lohnarten: {} });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    api.get('/api/firma').then((r) => { const e = r.firma?.lohn_export || {}; setForm({ berater_nr: e.berater_nr || '', mandanten_nr: e.mandanten_nr || '', bs_nr: e.bs_nr || 1, lohnarten: e.lohnarten || {} }); }).catch((err) => toast.error(err.message));
  }, [open]);
  const speichern = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await api.put('/api/firma', { lohn_export: { ...form, bs_nr: parseInt(form.bs_nr, 10) || 1 } }); toast.success('DATEV-Einstellungen gespeichert'); onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="DATEV-Einstellungen" subtitle="Für die LODAS-Importdatei. Lohnarten-Nummern bitte vom Steuerberater geben lassen – jede Kanzlei nummeriert anders.">
      <form onSubmit={speichern} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Berater-Nr."><TextInput value={form.berater_nr} onChange={(e) => setForm((f) => ({ ...f, berater_nr: e.target.value }))} inputMode="numeric" /></Field>
          <Field label="Mandanten-Nr."><TextInput value={form.mandanten_nr} onChange={(e) => setForm((f) => ({ ...f, mandanten_nr: e.target.value }))} inputMode="numeric" /></Field>
          <Field label="Bearbeitungsschlüssel (BS)" hint="Standard 1"><TextInput value={form.bs_nr} onChange={(e) => setForm((f) => ({ ...f, bs_nr: e.target.value }))} inputMode="numeric" /></Field>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Lohnarten-Nummern (leer = Kategorie nicht exportieren)</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {LOHNARTEN.map(([k, l]) => <Field key={k} label={l}><TextInput value={form.lohnarten[k] || ''} onChange={(e) => { const v = e.target.value; setForm((f) => ({ ...f, lohnarten: { ...f.lohnarten, [k]: v } })); }} placeholder="z. B. 100" /></Field>)}
          </div>
        </div>
        <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn type="submit" loading={busy}>Speichern</Btn></div>
      </form>
    </Sheet>
  );
}
