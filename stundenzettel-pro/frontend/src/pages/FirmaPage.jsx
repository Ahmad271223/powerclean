import React, { useCallback, useEffect, useRef, useState } from 'react';
import { KeyRound, Copy, Trash2, Upload, Building2, BadgeCheck, Plug, Tag, Plus, Webhook, Send, Pencil, FileText } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import CompanyForm from '../components/CompanyForm';
import { Btn, Card, Chip, Field, IconBtn, Segmented, TextInput, Toggle } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate } from '../lib/dates';
import AngeboteEinstellungenKarte from '../components/angebot/AngeboteEinstellungenKarte';
import AbosKarte, { PreisListe } from '../components/AbosKarte';
import { useDialoge } from '../components/Dialoge';

const fmtZeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '–');

export default function FirmaPage() {
  const { firma, setFirma, isInhaber } = useAuth();
  const [tab, setTab] = useState('firma');
  const optionen = [{ value: 'firma', label: 'Firmendaten', icon: Building2 }, { value: 'leistungen', label: 'Leistungen', icon: Tag }, { value: 'angebote', label: 'Angebote', icon: FileText }, { value: 'lizenz', label: 'Lizenz', icon: BadgeCheck }];
  if (isInhaber) optionen.push({ value: 'api', label: 'Schnittstelle', icon: Plug }, { value: 'webhooks', label: 'Webhooks', icon: Webhook }, { value: 'import', label: 'Import', icon: Upload });

  const speichern = async (daten) => {
    const r = await api.put('/api/firma', daten);
    setFirma(r.firma, r.plan);
  };

  return (
    <Layout title="Firma" subtitle="Logo, Stempel, Rechnungsdaten, Arbeitszeitregeln und Leistungen gelten für alle Stundenzettel und Rechnungen.">
      <div className="flex justify-center mb-5 overflow-x-auto no-scrollbar"><Segmented value={tab} onChange={setTab} options={optionen} /></div>
      {tab === 'firma' && <div className="max-w-3xl mx-auto space-y-5"><FirmenartKarte /><BenachrichtigungenKarte /><Card className="p-5 sm:p-8">{firma ? <CompanyForm company={firma} onSave={speichern} /> : <Ladeanzeige />}</Card></div>}
      {tab === 'leistungen' && <Leistungen />}
      {tab === 'angebote' && <div className="max-w-3xl mx-auto space-y-5"><AngeboteEinstellungenKarte /></div>}
      {tab === 'lizenz' && <Lizenz />}
      {tab === 'api' && <Schnittstelle />}
      {tab === 'webhooks' && <Webhooks />}
      {tab === 'import' && <Import />}
    </Layout>
  );
}

/** Leistungen mit eigenem Stundensatz (Unterhaltsreinigung, Grundreinigung, Glasreinigung …). */
const FIRMENARTEN = [
  { value: 'betrieb', label: 'Ausführender Betrieb', text: 'Zeiten, Stundenzettel, Rechnungen; Aufträge finden und Angebote abgeben.' },
  { value: 'auftraggeber', label: 'Auftraggeber / GU', text: 'Bauprojekte führen, Gewerke ausschreiben, Angebote vergleichen und vergeben. Menü ohne Rechnungen und Kunden.' },
  { value: 'beides', label: 'Beides', text: 'Volles Menü: eigene Leistungen und Vergabe an andere Firmen.' },
];

/** Firmenart bestimmt Menü, Startseite und die Ansicht unter „Ausschreibungen“ – ändert nur der Inhaber. */
function FirmenartKarte() {
  const { firma, isInhaber, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const art = firma?.art || 'betrieb';
  const setzen = async (v) => {
    if (!isInhaber || v === art) return;
    setBusy(true);
    try { await api.put('/api/firma', { art: v }); await refresh(); toast.success('Firmenart gespeichert – Menü und Startseite sind angepasst'); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Card className="p-5 sm:p-8">
      <h2 className="text-[17px] flex items-center gap-2">Firmenart{firma?.verifiziert?.status && <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#1B7F3B] bg-[#E8F8EC] rounded-full px-2 py-0.5" title={firma.verifiziert.hinweis || 'Vom Anbieter geprüft'}><BadgeCheck size={12} /> Geprüfte Firma</span>}</h2>
      <p className="text-[14px] text-[#6E6E73] mt-1 mb-3">Auftraggeber (z. B. Generalunternehmer) und ausführende Betriebe sehen unterschiedliche Menüs und Startseiten. Eine Firma kann auch beides sein.</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {FIRMENARTEN.map((a) => (
          <button key={a.value} type="button" disabled={!isInhaber || busy} onClick={() => setzen(a.value)} className={`text-left rounded-2xl px-4 py-3 transition-all disabled:opacity-60 ${art === a.value ? 'ring-2 ring-[#C41E3A] bg-[#C41E3A]/5' : 'bg-[#F5F5F7] hover:bg-black/[0.06]'}`}>
            <span className="block text-[14px] font-semibold">{a.label}</span><span className="block text-[12px] text-[#6E6E73]">{a.text}</span>
          </button>
        ))}
      </div>
      {!isInhaber && <p className="text-[12px] text-[#86868B] mt-2">Ändern kann das nur der Inhaber.</p>}
    </Card>
  );
}

/** E-Mails zu Einladungen, Angeboten, Zuschlägen, Nachträgen und Abnahmen – nie zu jeder Statusänderung. */
function BenachrichtigungenKarte() {
  const { firma, isInhaber, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const an = firma?.email_benachrichtigungen !== false;
  const setzen = async (v) => {
    setBusy(true);
    try { await api.put('/api/firma', { email_benachrichtigungen: v }); await refresh(); toast.success(v ? 'E-Mail-Versand an' : 'E-Mail-Versand aus'); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Card className="p-5 sm:p-8">
      <h2 className="text-[17px]">E-Mails an eure Firma</h2>
      <p className="text-[14px] text-[#6E6E73] mt-1 mb-2">Büro und Inhaber bekommen E-Mails zu Projekteinladungen, Ausschreibungen, Einreichungsnachweisen, Zuschlägen, Nachträgen und Abnahmen. Jede E-Mail steht als Nachweis unter „Protokoll → E-Mail-Nachweise“.</p>
      <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={an} onChange={(v) => { if (!busy && isInhaber) setzen(v); }} label="E-Mail-Benachrichtigungen" hint={isInhaber ? 'Nur der Inhaber ändert das.' : 'Ändern kann das nur der Inhaber.'} /></div>
      <ErinnerungEinstellung firma={firma} isInhaber={isInhaber} refresh={refresh} />
    </Card>
  );
}

/** Einsatz-Erinnerung am Vorabend: Uhrzeit und ob zusätzlich zur App-Mitteilung eine E-Mail geht. */
function ErinnerungEinstellung({ firma, isInhaber, refresh }) {
  const e = firma?.erinnerung || { uhrzeit: '18:00', email: true };
  const [uhrzeit, setUhrzeit] = useState(e.uhrzeit || '18:00');
  const [email, setEmail] = useState(e.email !== false);
  const [busy, setBusy] = useState(false);
  const speichern = async () => {
    setBusy(true);
    try { await api.put('/api/firma', { erinnerung: { uhrzeit, email } }); await refresh(); toast.success('Erinnerung gespeichert'); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="mt-4 rounded-2xl bg-[#F5F5F7] px-4 py-3 space-y-2">
      <div className="text-[14px] font-medium">Einsatz-Erinnerung am Vorabend</div>
      <p className="text-[13px] text-[#6E6E73]">Jede eingeplante Person bekommt am Abend eine Mitteilung für den nächsten Tag (Projekt, Zeit, Adresse, Hinweis) – einmal je Einsatz, bei Planänderungen erneut.</p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Uhrzeit"><TextInput type="time" value={uhrzeit} onChange={(ev) => setUhrzeit(ev.target.value)} disabled={!isInhaber} /></Field>
        <div className="flex-1 min-w-[220px]"><Toggle checked={email} onChange={(v) => isInhaber && setEmail(v)} label="Zusätzlich per E-Mail" hint="In der App immer" /></div>
        {isInhaber && <Btn size="sm" onClick={speichern} loading={busy}>Speichern</Btn>}
      </div>
    </div>
  );
}

function Leistungen() {
  const [liste, setListe] = useState(null);
  const [form, setForm] = useState({ id: '', name: '', hourly_rate: '', sort: '', active: true });
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get('/api/leistungen?alle=true').then((r) => setListe(r.leistungen)).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Bitte einen Namen eingeben'); return; }
    setBusy(true);
    try {
      const body = { name: form.name.trim(), hourly_rate: parseFloat(String(form.hourly_rate).replace(',', '.')) || 0, sort: parseInt(form.sort, 10) || 0, active: form.active };
      if (form.id) await api.put(`/api/leistungen/${form.id}`, body); else await api.post('/api/leistungen', body);
      toast.success(form.id ? 'Gespeichert' : 'Leistung angelegt'); setForm({ id: '', name: '', hourly_rate: '', sort: '', active: true }); laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const loeschen = async (l) => {
    if (!window.confirm(`„${l.name}“ löschen?`)) return;
    try { const r = await api.del(`/api/leistungen/${l.id}`); toast.success(r.deaktiviert ? r.hinweis : 'Gelöscht'); laden(); } catch (err) { toast.error(err.message); }
  };
  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <Card className="p-5 sm:p-7 space-y-4">
        <div><h2 className="text-[17px]">{form.id ? 'Leistung bearbeiten' : 'Neue Leistung'}</h2><p className="text-[14px] text-[#6E6E73] mt-1">Leistungen erscheinen als Auswahl beim Eintragen und Ausstempeln. Mit eigenem Satz werden sie auf der Rechnung getrennt ausgewiesen; ohne Satz gilt der Satz des Projekts.</p></div>
        <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-[1fr_140px_90px_auto] gap-3 items-end">
          <Field label="Name"><TextInput value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="z. B. Glasreinigung" required /></Field>
          <Field label="Stundensatz € (0 = Projekt)"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} placeholder="0" /></Field>
          <Field label="Reihenfolge"><TextInput type="number" min="0" value={form.sort} onChange={(e) => setForm({ ...form, sort: e.target.value })} placeholder="0" /></Field>
          <div className="flex gap-2"><Btn type="submit" loading={busy}>{form.id ? <Pencil size={15} /> : <Plus size={15} />} {form.id ? 'Speichern' : 'Anlegen'}</Btn>{form.id && <Btn type="button" variant="soft" onClick={() => setForm({ id: '', name: '', hourly_rate: '', sort: '', active: true })}>Abbrechen</Btn>}</div>
        </form>
        {form.id && <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={form.active} onChange={(v) => setForm({ ...form, active: v })} label="Aktiv (zur Auswahl angeboten)" /></div>}
        {!liste ? <Ladeanzeige /> : liste.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch keine Leistungen. Typisch: Unterhaltsreinigung (Projektsatz), Grundreinigung, Glasreinigung, Treppenhaus, Sonderreinigung.</p> : (
          <ul className="divide-y divide-black/[0.06]">{liste.map((l) => <li key={l.id} className="py-2.5 flex items-center gap-3 text-[14px]"><Tag size={15} className="text-[#6E6E73]" /><div className="flex-1 min-w-0"><div className="font-medium">{l.name}{!l.active && <span className="ml-2 text-[11px] text-[#86868B] bg-black/[0.06] rounded-full px-2 py-0.5">inaktiv</span>}</div><div className="text-[12px] text-[#86868B]">{l.hourly_rate ? `${String(l.hourly_rate).replace('.', ',')} € je Stunde` : 'Satz des Projekts'}</div></div><IconBtn size={30} onClick={() => setForm({ id: l.id, name: l.name, hourly_rate: l.hourly_rate ? String(l.hourly_rate) : '', sort: String(l.sort || 0), active: l.active !== false })} title="Bearbeiten"><Pencil size={14} /></IconBtn><IconBtn size={30} variant="danger" onClick={() => loeschen(l)} title="Löschen"><Trash2 size={14} /></IconBtn></li>)}</ul>
        )}
      </Card>
    </div>
  );
}

function Lizenz() {
  const { firma, isInhaber, logout } = useAuth();
  const { fragen } = useDialoge();
  const [plan, setPlan] = useState(null);
  useEffect(() => { api.get('/api/firma/plan').then(setPlan).catch((err) => toast.error(err.message)); }, []);
  const firmaLoeschen = async () => {
    const name = await fragen({ titel: 'Firma löschen', text: `Firma „${firma?.name}“ mit ALLEN Daten (Mitarbeiter, Zeiten, Rechnungen, Akten) unwiderruflich löschen? Vorher unter „Exporte“ die Komplettsicherung herunterladen.`, feld: 'Zur Bestätigung den Firmennamen eingeben', pflicht: true, ok: 'Weiter', gefaehrlich: true });
    if (name === null) return;
    const pw = await fragen({ titel: 'Passwort bestätigen', text: 'Zur Sicherheit dein Passwort eingeben.', feld: 'Passwort', passwort: true, pflicht: true, ok: 'Endgültig löschen', gefaehrlich: true });
    if (!pw) return;
    try { await api.del('/api/firma', { name, password: pw }); toast.success('Firma gelöscht'); logout(); window.location.hash = '#/login'; }
    catch (err) { toast.error(err.message); }
  };
  if (!plan) return <Ladeanzeige />;
  const farbe = plan.status === 'aktiv' ? 'text-[#1B7F3B]' : plan.status === 'test' || plan.status === 'teilnahme' ? 'text-[#B25E00]' : 'text-[#C41E3A]';
  return (
    <Card className="p-5 sm:p-8 max-w-3xl mx-auto space-y-5">
      <div><div className="text-[13px] text-[#6E6E73]">Stand</div><div className={`text-[28px] font-bold tracking-tight ${farbe}`}>{{ test: 'Testphase', aktiv: plan.stufe === 'teilnahme' ? 'Kostenlose Projektteilnahme' : 'Firmenabo aktiv', abgelaufen: 'Abgelaufen', gesperrt: 'Gesperrt', teilnahme: 'Kostenlose Projektteilnahme' }[plan.status] || plan.status}</div><div className="text-[14px] text-[#6E6E73] mt-1">{plan.hinweis}</div></div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-[14px]">
        <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Aktive Nutzer</div><div className="text-[20px] font-bold">{plan.nutzer_aktiv}{plan.nutzer_max ? ` / ${plan.nutzer_max}` : ''}</div></div>
        {plan.test_bis && plan.status === 'test' && <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Test bis</div><div className="text-[20px] font-bold">{fmtDate(new Date(plan.test_bis))}</div></div>}
        {plan.gueltig_bis && <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Gültig bis</div><div className="text-[20px] font-bold">{fmtDate(new Date(plan.gueltig_bis))}</div></div>}
      </div>
      {plan.hinweis_betreiber && <p className="text-[14px]">{plan.hinweis_betreiber}</p>}
      <PreisListe />
      <AbosKarte />
      <div className="text-[13px] text-[#6E6E73]"><a href="/datenschutz" target="_blank" rel="noreferrer" className="text-[#C41E3A] font-medium">Datenschutzerklärung</a> · <a href="/impressum" target="_blank" rel="noreferrer" className="text-[#C41E3A] font-medium">Impressum</a></div>
      {isInhaber && (
        <div className="pt-4 border-t border-black/[0.06]">
          <Btn variant="danger" size="sm" onClick={firmaLoeschen}><Trash2 size={14} /> Firma und alle Daten löschen</Btn>
          <p className="text-[12px] text-[#86868B] mt-1.5">Unwiderruflich. Vorher unter „Exporte“ die Komplettsicherung herunterladen.</p>
        </div>
      )}
    </Card>
  );
}

const API_RECHTE = [['zeiten', 'Zeiten'], ['projekte', 'Projekte'], ['abwesenheiten', 'Abwesenheiten'], ['mitarbeiter', 'Mitarbeiter'], ['kunden', 'Kunden'], ['rechnungen', 'Rechnungen']];

function Schnittstelle() {
  const [tokens, setTokens] = useState(null);
  const [name, setName] = useState('');
  const [rechte, setRechte] = useState(['zeiten', 'projekte']);
  const [tage, setTage] = useState(365);
  const [neu, setNeu] = useState('');
  const laden = () => api.get('/api/firma/api-tokens').then((r) => setTokens(r.tokens)).catch((err) => toast.error(err.message));
  useEffect(() => { laden(); }, []);
  const toggleRecht = (r) => setRechte((x) => (x.includes(r) ? x.filter((y) => y !== r) : [...x, r]));
  const anlegen = async (e) => {
    e.preventDefault();
    if (!rechte.length) { toast.error('Bitte mindestens ein Recht wählen'); return; }
    try { const r = await api.post('/api/firma/api-tokens', { name: name.trim() || 'Schlüssel', rechte, tage: Math.max(1, Math.min(730, parseInt(tage, 10) || 365)) }); setNeu(r.token); setName(''); laden(); } catch (err) { toast.error(err.message); }
  };
  const loeschen = async (t) => { if (!window.confirm(`Schlüssel „${t.name}“ löschen? Verbundene Programme verlieren den Zugriff.`)) return; try { await api.del(`/api/firma/api-tokens/${t.id}`); laden(); } catch (err) { toast.error(err.message); } };
  return (
    <Card className="p-5 sm:p-8 max-w-3xl mx-auto space-y-5">
      <div><h2 className="text-[17px]">API-Schlüssel</h2><p className="text-[14px] text-[#6E6E73] mt-1">Für Lohnbüro, Steuerberater oder eigene Auswertungen: lesender Zugriff auf Zeiten, Projekte, Mitarbeiter, Abwesenheiten und Rechnungen. Dokumentation unter <a href="/api/docs" target="_blank" rel="noreferrer" className="text-[#C41E3A] font-medium">/api/docs</a> (Bereich „API v1“).</p></div>
      <form onSubmit={anlegen} className="space-y-3">
        <div className="flex gap-2"><TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, z. B. Lohnbüro Schmidt" /><TextInput type="number" min="1" max="730" inputMode="numeric" value={tage} onChange={(e) => setTage(e.target.value)} className="w-28" title="Gültig in Tagen" /><Btn type="submit"><KeyRound size={16} /> Erzeugen</Btn></div>
        <div><span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Rechte (nur so viel wie nötig)</span><div className="flex flex-wrap gap-2">{API_RECHTE.map(([r, l]) => <Chip key={r} active={rechte.includes(r)} onClick={() => toggleRecht(r)}>{l}</Chip>)}</div><span className="block text-[12px] text-[#86868B] mt-1">Gültig {tage || 365} Tage ab heute; danach einen neuen Schlüssel erzeugen. Jeder Abruf wird mit Zeitpunkt vermerkt.</span></div>
      </form>
      {neu && (
        <div className="rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[14px] text-[#7A4100]">
          <div className="font-semibold">Neuer Schlüssel – wird nur jetzt angezeigt:</div>
          <div className="mt-1 break-all select-all font-mono text-[13px]">{neu}</div>
          <Btn size="sm" variant="dark" className="mt-2" onClick={() => navigator.clipboard?.writeText(neu).then(() => toast.success('Kopiert'))}><Copy size={14} /> Kopieren</Btn>
        </div>
      )}
      {!tokens ? <Ladeanzeige /> : tokens.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch keine Schlüssel.</p> : (
        <ul className="divide-y divide-black/[0.06]">{tokens.map((t) => <li key={t.id} className="py-2.5 flex items-center gap-3 text-[14px]"><div className="flex-1"><div className="font-medium">{t.name}</div><div className="text-[12px] text-[#86868B]">{(t.rechte || ['alle (alter Schlüssel)']).join(', ')} · gültig bis {t.gueltig_bis ? fmtZeit(t.gueltig_bis) : 'unbegrenzt (alter Schlüssel – bitte erneuern)'} · erzeugt {fmtZeit(t.created_at)} · zuletzt benutzt {fmtZeit(t.last_used_at)}</div></div><Btn size="sm" variant="danger" onClick={() => loeschen(t)}><Trash2 size={14} /></Btn></li>)}</ul>
      )}
      <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[13px] font-mono break-all">curl -H "Authorization: Bearer sz_…" {window.location.origin}/api/v1/zeiten?von=2026-10-01&amp;bis=2026-10-31</div>
    </Card>
  );
}

/** Webhooks: Ereignisse an fremde Systeme (Buchhaltung, Zapier/Make, eigene Programme). */
function Webhooks() {
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState({ name: '', url: '', events: ['*'] });
  const [geheim, setGeheim] = useState('');
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get('/api/firma/webhooks').then(setDaten).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  const toggleEvent = (ev) => setForm((f) => {
    if (ev === '*') return { ...f, events: ['*'] };
    const ohne = f.events.filter((x) => x !== '*' && x !== ev);
    return { ...f, events: f.events.includes(ev) ? (ohne.length ? ohne : ['*']) : [...ohne, ev] };
  });
  const anlegen = async (e) => {
    e.preventDefault();
    setBusy('neu');
    try { const r = await api.post('/api/firma/webhooks', form); setGeheim(r.secret); setForm({ name: '', url: '', events: ['*'] }); toast.success('Webhook angelegt'); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const testen = async (h) => { setBusy(h.id); try { const r = await api.post(`/api/firma/webhooks/${h.id}/test`); if (r.ok) toast.success(`Test gesendet (HTTP ${r.status})`); else toast.error(`Ziel antwortet mit ${r.status || 'Fehler'}`); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const loeschen = async (h) => { if (!window.confirm(`Webhook „${h.name}“ löschen?`)) return; try { await api.del(`/api/firma/webhooks/${h.id}`); laden(); } catch (err) { toast.error(err.message); } };
  return (
    <Card className="p-5 sm:p-8 max-w-3xl mx-auto space-y-5">
      <div><h2 className="text-[17px]">Webhooks</h2><p className="text-[14px] text-[#6E6E73] mt-1">Bei Ereignissen schickt der Server eine JSON-Nachricht an deine Adresse (z. B. Zapier, Make, Buchhaltung, eigenes Programm). Signatur im Kopf <code>X-Signatur</code> (HMAC-SHA256 über den Inhalt mit dem Geheimnis).</p></div>
      <form onSubmit={anlegen} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_2fr] gap-3"><Field label="Name"><TextInput value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="z. B. Buchhaltung" /></Field><Field label="Adresse (https)"><TextInput value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" required /></Field></div>
        <div><span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Ereignisse</span><div className="flex flex-wrap gap-2"><Chip active={form.events.includes('*')} onClick={() => toggleEvent('*')}>Alle</Chip>{(daten?.ereignisse || []).filter((e) => e !== 'test').map((ev) => <Chip key={ev} active={form.events.includes(ev)} onClick={() => toggleEvent(ev)}>{ev}</Chip>)}</div></div>
        <Btn type="submit" loading={busy === 'neu'}><Plus size={16} /> Webhook anlegen</Btn>
      </form>
      {geheim && <div className="rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[14px] text-[#7A4100]"><div className="font-semibold">Geheimnis für die Signatur – wird nur jetzt angezeigt:</div><div className="mt-1 break-all select-all font-mono text-[13px]">{geheim}</div><Btn size="sm" variant="dark" className="mt-2" onClick={() => navigator.clipboard?.writeText(geheim).then(() => toast.success('Kopiert'))}><Copy size={14} /> Kopieren</Btn></div>}
      {!daten ? <Ladeanzeige /> : daten.webhooks.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch keine Webhooks.</p> : (
        <ul className="divide-y divide-black/[0.06]">{daten.webhooks.map((h) => <li key={h.id} className="py-2.5 flex items-center gap-3 text-[14px]"><div className="flex-1 min-w-0"><div className="font-medium truncate">{h.name} <span className="text-[12px] font-normal text-[#86868B]">{h.url}</span></div><div className="text-[12px] text-[#86868B]">{(h.events || ['*']).join(', ')} · zuletzt {h.last_status ? `HTTP ${h.last_status} (${h.last_event})` : 'nie'} {h.last_at ? fmtZeit(h.last_at) : ''}{h.ausgang?.offen ? ` · ${h.ausgang.offen} Lieferung(en) wartet auf Wiederholung` : ''}{h.ausgang?.fehlgeschlagen ? ` · ${h.ausgang.fehlgeschlagen} endgültig fehlgeschlagen` : ''}</div></div><Btn size="sm" variant="soft" onClick={() => testen(h)} loading={busy === h.id}><Send size={14} /> Test</Btn><IconBtn size={30} variant="danger" onClick={() => loeschen(h)} title="Löschen"><Trash2 size={14} /></IconBtn></li>)}</ul>
      )}
    </Card>
  );
}

function Import() {
  const ref = useRef(null);
  const [firmendaten, setFirmendaten] = useState(false);
  const [busy, setBusy] = useState(false);
  const datei = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      setBusy(true);
      try {
        const json = JSON.parse(String(reader.result));
        const r = await api.post(`/api/import/free-app?firmendaten_uebernehmen=${firmendaten}`, json);
        toast.success(`Übernommen: ${r.projekte} Projekte, ${r.eintraege} Einträge, ${r.rechnungen} Rechnungen${r.uebersprungen ? ` (${r.uebersprungen} übersprungen)` : ''}`);
      } catch (err) { toast.error(err.message || 'Datei konnte nicht gelesen werden'); } finally { setBusy(false); }
    };
    reader.readAsText(file);
  };
  return (
    <Card className="p-5 sm:p-8 max-w-3xl mx-auto space-y-4">
      <h2 className="text-[17px]">Aus der kostenlosen App übernehmen</h2>
      <p className="text-[14px] text-[#6E6E73]">In der kostenlosen Stundenzettel-App unter „Datensicherung“ die Sicherungsdatei erzeugen und hier einspielen. Projekte, Zeiten und Rechnungsnummern werden übernommen, Auftraggeber werden als Kunden angelegt. Mehrfaches Einspielen legt nichts doppelt an.</p>
      <Field label="Firmendaten (Logo, Stempel, Bankverbindung) aus der Datei übernehmen"><label className="flex items-center gap-2 text-[14px]"><input type="checkbox" checked={firmendaten} onChange={(e) => setFirmendaten(e.target.checked)} /> ja, überschreiben</label></Field>
      <input ref={ref} type="file" accept="application/json,.json" className="hidden" onChange={datei} />
      <Btn onClick={() => ref.current?.click()} loading={busy}><Upload size={16} /> Sicherungsdatei auswählen</Btn>
    </Card>
  );
}
