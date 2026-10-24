import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Package, Plus, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Chip, Empty, Field, Select, Sheet, TextArea, TextInput, Toggle } from '../components/ui';
import { useDialoge } from '../components/Dialoge';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtGeld } from '../lib/angebot';

const LEER = { nummer: '', name: '', beschreibung: '', einheit: 'Stk.', einkaufspreis: '', verkaufspreis: '', hersteller: '', lieferant: '', kategorie: '', steuer_satz: '', aktiv: true };

function ArtikelDialog({ open, onOpenChange, artikel, ekSichtbar, onSaved }) {
  const { bestaetigen } = useDialoge();
  const [f, setF] = useState(LEER);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF({ ...LEER, ...(artikel || {}), einkaufspreis: artikel?.einkaufspreis ?? '', verkaufspreis: artikel?.verkaufspreis ?? '', steuer_satz: artikel?.steuer_satz ?? '' }); }, [open, artikel]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const speichern = async () => {
    if (!f.nummer.trim() || !f.name.trim()) { toast.error('Artikelnummer und Bezeichnung angeben'); return; }
    setBusy(true);
    try {
      const daten = { ...f, einkaufspreis: ekSichtbar && f.einkaufspreis !== '' ? Number(f.einkaufspreis) : null, verkaufspreis: f.verkaufspreis !== '' ? Number(f.verkaufspreis) : null, steuer_satz: f.steuer_satz !== '' ? Number(f.steuer_satz) : null };
      if (!ekSichtbar) delete daten.einkaufspreis;
      const r = artikel ? await api.put(`/api/artikel/${artikel.id}`, daten) : await api.post('/api/artikel', daten);
      toast.success(artikel ? 'Artikel gespeichert' : 'Artikel angelegt');
      onSaved(r.artikel);
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async () => {
    if (!(await bestaetigen({ titel: 'Artikel löschen?', text: 'Ein Artikel, der in Buchungen oder Angeboten vorkommt, wird nur deaktiviert.', gefaehrlich: true }))) return;
    try { const r = await api.del(`/api/artikel/${artikel.id}`); toast.success(r.deaktiviert ? r.hinweis : 'Artikel gelöscht'); onSaved(null); onOpenChange(false); } catch (err) { toast.error(err.message); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={artikel ? `Artikel ${artikel.nummer}` : 'Neuer Artikel'} subtitle="Material, das in Angeboten, Buchungen und der Nachkalkulation wiederverwendet wird."
      footer={<>{artikel && <Btn variant="ghost" onClick={loeschen} className="text-[#C41E3A] mr-auto"><Trash2 size={16} /> Löschen</Btn>}<Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={speichern} loading={busy}>Speichern</Btn></>}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Artikelnummer"><TextInput value={f.nummer} onChange={set('nummer')} placeholder="z. B. RM-100" /></Field>
        <Field label="Einheit"><TextInput value={f.einheit} onChange={set('einheit')} /></Field>
        <Field label="Bezeichnung" className="sm:col-span-2"><TextInput value={f.name} onChange={set('name')} /></Field>
        <Field label="Beschreibung" className="sm:col-span-2"><TextArea rows={2} value={f.beschreibung || ''} onChange={set('beschreibung')} /></Field>
        {ekSichtbar ? <Field label="Einkaufspreis (netto)" hint="vertraulich – nur mit Recht „Kostensätze“"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.einkaufspreis} onChange={set('einkaufspreis')} /></Field> : <Field label="Einkaufspreis" hint="nur mit Recht „Kostensätze“ sichtbar"><TextInput value="•••" disabled /></Field>}
        <Field label="Verkaufspreis (netto)"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.verkaufspreis} onChange={set('verkaufspreis')} /></Field>
        <Field label="Hersteller"><TextInput value={f.hersteller || ''} onChange={set('hersteller')} /></Field>
        <Field label="Lieferant"><TextInput value={f.lieferant || ''} onChange={set('lieferant')} /></Field>
        <Field label="Kategorie / Warengruppe"><TextInput value={f.kategorie || ''} onChange={set('kategorie')} /></Field>
        <Field label="Steuersatz %" hint="leer = Satz der Firma"><TextInput type="number" inputMode="decimal" step="1" min="0" max="100" value={f.steuer_satz} onChange={set('steuer_satz')} /></Field>
        <div className="sm:col-span-2 rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={!!f.aktiv} onChange={(v) => setF((x) => ({ ...x, aktiv: v }))} label="Aktiv" hint="Inaktive Artikel stehen nicht mehr zur Auswahl, bleiben aber in alten Buchungen." /></div>
      </div>
    </Sheet>
  );
}

function ImportDialog({ open, onOpenChange, onDone }) {
  const datei = useRef(null);
  const [vorschau, setVorschau] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setVorschau(null); }, [open]);
  const lesen = async (endgueltig) => {
    const f = datei.current?.files?.[0];
    if (!f) { toast.error('Bitte eine CSV-Datei wählen'); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('datei', f); fd.append('vorschau', endgueltig ? '0' : '1');
      const r = await api.upload('/api/artikel/import', fd);
      setVorschau(r);
      if (endgueltig) { toast.success(`${r.angelegt} angelegt, ${r.aktualisiert} aktualisiert${r.fehler.length ? `, ${r.fehler.length} Fehlerzeilen` : ''}`); onDone(); }
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Artikel aus CSV importieren" subtitle="Semikolon, Komma oder Tab; Anführungszeichen; Dezimalkomma; UTF-8 oder Windows. Spalten: Artikelnummer, Bezeichnung, Einheit, EK, VK, Kategorie, Hersteller, Lieferant, Beschreibung." width="sm:max-w-2xl"
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Schließen</Btn><Btn variant="soft" onClick={() => lesen(false)} loading={busy}>Vorschau</Btn><Btn onClick={() => lesen(true)} loading={busy} disabled={!vorschau || !vorschau.anzahl}>Importieren ({vorschau?.anzahl || 0})</Btn></>}>
      <input ref={datei} type="file" accept=".csv,text/csv,text/plain" className="block w-full text-[14px]" />
      {vorschau && (
        <div className="mt-3 text-[13px] space-y-2">
          <div>Erkannte Spalten: {Object.keys(vorschau.spalten || {}).join(', ') || 'keine'} · Trennzeichen „{vorschau.trenner === '\t' ? 'Tab' : vorschau.trenner}“ · {vorschau.anzahl} gültige Artikel{vorschau.vorschau === false ? ` · ${vorschau.angelegt} angelegt, ${vorschau.aktualisiert} aktualisiert` : ''}</div>
          {vorschau.fehler?.length > 0 && <div className="rounded-2xl bg-[#FFF4E5] px-3 py-2"><div className="font-semibold text-[#B25E00] mb-1">{vorschau.fehler.length} Zeilen nicht übernommen</div><ul className="space-y-0.5">{vorschau.fehler.slice(0, 50).map((f, i) => <li key={i}>{f.zeile ? `Zeile ${f.zeile}: ` : ''}{f.grund}</li>)}</ul></div>}
          {vorschau.artikel?.length > 0 && (
            <div className="overflow-x-auto"><table className="w-full text-[12px] min-w-[520px]"><thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-2">Nr.</th><th className="py-1 pr-2">Bezeichnung</th><th className="py-1 pr-2">Einheit</th><th className="py-1 pr-2 text-right">EK</th><th className="py-1 pr-2 text-right">VK</th><th className="py-1">Kategorie</th></tr></thead>
              <tbody>{vorschau.artikel.slice(0, 100).map((a) => <tr key={a.nummer} className="border-t border-black/[0.06]"><td className="py-1 pr-2">{a.nummer}</td><td className="py-1 pr-2">{a.name}</td><td className="py-1 pr-2">{a.einheit}</td><td className="py-1 pr-2 text-right">{a.einkaufspreis === null || a.einkaufspreis === undefined ? '–' : fmtGeld(a.einkaufspreis)}</td><td className="py-1 pr-2 text-right">{a.verkaufspreis === null || a.verkaufspreis === undefined ? '–' : fmtGeld(a.verkaufspreis)}</td><td className="py-1">{a.kategorie}</td></tr>)}</tbody></table></div>
          )}
        </div>
      )}
    </Sheet>
  );
}

/** Artikelstamm: Katalog für Angebote, Materialbuchungen und Nachkalkulation – mit CSV-Import (DATANORM folgt in Stufe F). */
export default function ArtikelPage() {
  const { kann } = useAuth();
  const [d, setD] = useState(null);
  const [q, setQ] = useState('');
  const [kategorie, setKategorie] = useState('');
  const [nurAktiv, setNurAktiv] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [edit, setEdit] = useState(null);
  const [importDialog, setImportDialog] = useState(false);
  const laden = useCallback(() => api.get(`/api/artikel?${nurAktiv ? 'aktiv=true&' : ''}${kategorie ? `kategorie=${encodeURIComponent(kategorie)}&` : ''}${q ? `q=${encodeURIComponent(q)}` : ''}`).then(setD).catch((err) => toast.error(err.message)), [q, kategorie, nurAktiv]);
  useEffect(() => { const t = setTimeout(laden, 200); return () => clearTimeout(t); }, [laden]);
  return (
    <Layout title="Artikel & Material" subtitle="Euer Materialkatalog: Einkaufs- und Verkaufspreise, Einheiten, Lieferanten. Einkaufspreise sieht nur, wer das Recht „Kostensätze“ hat."
      action={<div className="flex gap-2"><Btn variant="soft" onClick={() => setImportDialog(true)}><Upload size={16} /> <span className="hidden sm:inline">CSV-Import</span></Btn><Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={16} /> Artikel</Btn></div>}>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <TextInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Suche Nummer, Name, Hersteller, Lieferant" className="w-full sm:w-80" />
        <Select value={kategorie} onChange={(e) => setKategorie(e.target.value)}><option value="">Alle Kategorien</option>{(d?.kategorien || []).map((k) => <option key={k} value={k}>{k}</option>)}</Select>
        <Chip active={nurAktiv} onClick={() => setNurAktiv((v) => !v)}>Nur aktive</Chip>
      </div>
      {!d ? <Ladeanzeige /> : d.artikel.length === 0 ? <Card><Empty icon={Package} title="Noch keine Artikel" text="Lege Artikel an oder importiere eure Preisliste als CSV." action={<Btn onClick={() => setImportDialog(true)}><Upload size={16} /> CSV-Import</Btn>} /></Card> : (
        <Card className="overflow-x-auto">
          <table className="w-full text-[13px] min-w-[720px]">
            <thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="px-4 py-2">Nr.</th><th className="py-2 pr-2">Bezeichnung</th><th className="py-2 pr-2">Einheit</th>{d.ek_sichtbar && <th className="py-2 pr-2 text-right">EK</th>}<th className="py-2 pr-2 text-right">VK</th><th className="py-2 pr-2">Kategorie</th><th className="py-2 pr-4">Lieferant</th></tr></thead>
            <tbody>
              {d.artikel.map((a) => (
                <tr key={a.id} role="button" tabIndex={0} onClick={() => { setEdit(a); setDialog(true); }} onKeyDown={(e) => e.key === 'Enter' && (setEdit(a), setDialog(true))} className={`border-t border-black/[0.06] cursor-pointer hover:bg-black/[0.02] ${a.aktiv ? '' : 'text-[#86868B]'}`}>
                  <td className="px-4 py-2 whitespace-nowrap">{a.nummer}</td><td className="py-2 pr-2"><div className="font-medium">{a.name}{!a.aktiv && <span className="ml-2 text-[11px] bg-black/[0.06] rounded-full px-2 py-0.5">inaktiv</span>}</div>{a.hersteller && <div className="text-[12px] text-[#6E6E73]">{a.hersteller}</div>}</td>
                  <td className="py-2 pr-2">{a.einheit}</td>{d.ek_sichtbar && <td className="py-2 pr-2 text-right">{a.einkaufspreis === null || a.einkaufspreis === undefined ? '–' : fmtGeld(a.einkaufspreis)}</td>}<td className="py-2 pr-2 text-right">{a.verkaufspreis === null || a.verkaufspreis === undefined ? '–' : fmtGeld(a.verkaufspreis)}</td><td className="py-2 pr-2">{a.kategorie}</td><td className="py-2 pr-4">{a.lieferant}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <ArtikelDialog open={dialog} onOpenChange={setDialog} artikel={edit} ekSichtbar={!!d?.ek_sichtbar || kann('kostensaetze')} onSaved={laden} />
      <ImportDialog open={importDialog} onOpenChange={setImportDialog} onDone={laden} />
    </Layout>
  );
}
