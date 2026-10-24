import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Briefcase, Check, Copy, FileDown, GitBranch, LayoutTemplate, Link2, Mail, Plus, Save, Send, Trash2, Undo2, X } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Field, IconBtn, Select, Sheet, TextArea, TextInput, Toggle } from '../components/ui';
import KundeDialog from '../components/KundeDialog';
import { useDialoge } from '../components/Dialoge';
import PositionenEditor from '../components/angebot/PositionenEditor';
import KalkulationPanel from '../components/angebot/KalkulationPanel';
import { api, openFile } from '../lib/api';
import { ANNAHMEARTEN, STATUS_CLS, STATUS_NAMEN, fmtGeld, fmtMenge, positionenFuerServer, summen } from '../lib/angebot';
import { fmtDate, fromKey, todayKey } from '../lib/dates';

const formAus = (a) => ({
  titel: a.titel || '', customer_id: a.customer_id || '', kunde: { name: '', contact: '', street: '', zip_code: '', city: '', email: '', phone: '', ...(a.kunde || {}) },
  project_id: a.project_id || '', datum: a.datum || '', gueltig_bis: a.gueltig_bis || '', anfrage: { text: '', kanal: '', ...(a.anfrage || {}) },
  einleitung: a.einleitung || '', zahlungsbedingungen: a.zahlungsbedingungen || '', schluss: a.schluss || '', intern: a.intern || '',
  positionen: a.positionen || [], zuschlaege: a.zuschlaege || [], rabatt_prozent: a.rabatt_prozent || 0,
});
const payload = (f) => ({
  titel: f.titel, customer_id: f.customer_id || null, ...(f.customer_id ? {} : { kunde_frei: f.kunde }), project_id: f.project_id || null, datum: f.datum || null, gueltig_bis: f.gueltig_bis || null,
  anfrage: f.anfrage?.text ? f.anfrage : null, einleitung: f.einleitung, zahlungsbedingungen: f.zahlungsbedingungen, schluss: f.schluss, intern: f.intern,
  positionen: positionenFuerServer(f.positionen), zuschlaege: (f.zuschlaege || []).map((z) => ({ text: z.text || 'Zuschlag', prozent: Number(z.prozent) || 0 })), rabatt_prozent: Number(f.rabatt_prozent) || 0,
});
const StatusChip = ({ status }) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[status] || ''}`}>{STATUS_NAMEN[status] || status}</span>;

function SendenDialog({ open, onOpenChange, kunde, onSenden }) {
  const [an, setAn] = useState('');
  const [nachricht, setNachricht] = useState('');
  const [ohne, setOhne] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setAn(kunde?.email || ''); setNachricht(''); setOhne(!kunde?.email); } }, [open, kunde]);
  const los = async () => { setBusy(true); try { if (await onSenden({ an, nachricht, ohne_email: ohne })) onOpenChange(false); } finally { setBusy(false); } };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Angebot senden" subtitle="Das Angebot wird festgeschrieben (PDF-Snapshot) und bekommt einen Antwortlink, über den der Kunde online annehmen kann."
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={los} loading={busy}>{ohne ? 'Als übergeben markieren' : 'Per E-Mail senden'}</Btn></>}>
      <div className="space-y-3">
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={ohne} onChange={setOhne} label="Ohne E-Mail (gedruckt oder persönlich übergeben)" hint="Dann wird keine E-Mail verschickt; die Annahme erfasst ihr später von Hand." /></div>
        {!ohne && (<>
          <Field label="An (E-Mail des Kunden)"><TextInput type="email" value={an} onChange={(e) => setAn(e.target.value)} placeholder="kunde@beispiel.de" /></Field>
          <Field label="Persönliche Nachricht (optional)" hint="Steht über dem Standardtext der E-Mail; das PDF hängt an."><TextArea rows={3} value={nachricht} onChange={(e) => setNachricht(e.target.value)} /></Field>
        </>)}
      </div>
    </Sheet>
  );
}

function AnnahmeDialog({ open, onOpenChange, onAnnahme }) {
  const [f, setF] = useState({ von_name: '', art: 'schriftlich', am: todayKey(), text: '' });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF({ von_name: '', art: 'schriftlich', am: todayKey(), text: '' }); }, [open]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const los = async () => { if (f.von_name.trim().length < 2) { toast.error('Wer hat angenommen?'); return; } setBusy(true); try { if (await onAnnahme(f)) onOpenChange(false); } finally { setBusy(false); } };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Annahme erfassen" subtitle="Der Kunde hat das Angebot angenommen (schriftlich, telefonisch oder unterschrieben)."
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={los} loading={busy}><Check size={16} /> Annahme speichern</Btn></>}>
      <div className="space-y-3">
        <Field label="Angenommen durch"><TextInput value={f.von_name} onChange={set('von_name')} placeholder="Name der Person beim Kunden" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Wie"><Select value={f.art} onChange={set('art')}>{Object.entries(ANNAHMEARTEN).filter(([k]) => k !== 'online').map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          <Field label="Am"><TextInput type="date" value={f.am} onChange={set('am')} /></Field>
        </div>
        <Field label="Vermerk (optional)"><TextArea rows={2} value={f.text} onChange={set('text')} placeholder="z. B. per E-Mail vom 12.11., Start ab KW 48" /></Field>
      </div>
    </Sheet>
  );
}

function AuftragDialog({ open, onOpenChange, angebot, projekte, onAuftrag }) {
  const [modus, setModus] = useState('neu');
  const [name, setName] = useState('');
  const [projectId, setProjectId] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setModus(angebot.project_id ? 'bestehend' : 'neu'); setName(angebot.titel || `Auftrag ${angebot.nummer}`); setProjectId(angebot.project_id || ''); } }, [open, angebot]);
  const los = async () => { setBusy(true); try { if (await onAuftrag(modus === 'neu' ? { name } : { project_id: projectId })) onOpenChange(false); } finally { setBusy(false); } };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Auftrag anlegen" subtitle="Aus dem angenommenen Angebot wird ein Kundenprojekt mit Auftragswert und Abrechnungsart – die Basis für Zeiten, Material und Nachkalkulation."
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={los} loading={busy} disabled={modus === 'bestehend' && !projectId}><Briefcase size={16} /> Auftrag anlegen</Btn></>}>
      <div className="space-y-3">
        <div className="flex gap-2"><Btn size="sm" variant={modus === 'neu' ? 'primary' : 'soft'} onClick={() => setModus('neu')}>Neues Projekt</Btn><Btn size="sm" variant={modus === 'bestehend' ? 'primary' : 'soft'} onClick={() => setModus('bestehend')}>Bestehendes Projekt</Btn></div>
        {modus === 'neu' ? <Field label="Projektname"><TextInput value={name} onChange={(e) => setName(e.target.value)} /></Field>
          : <Field label="Projekt" hint="Nur Projekte ohne Auftrag"><Select value={projectId} onChange={(e) => setProjectId(e.target.value)}><option value="">Wählen …</option>{projekte.filter((p) => !p.auftrag).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>}
        <p className="text-[13px] text-[#6E6E73]">Auftragswert {fmtGeld(angebot.summen?.netto)} netto · {angebot.positionen?.some((p) => p.art === 'stunden' && p.zaehlt) ? 'Abrechnung nach Stunden (Stundensatz aus der ersten Stundenposition)' : 'Pauschalauftrag'}.</p>
      </div>
    </Sheet>
  );
}

/** Ein Angebot: Kopf, Positionen, Konditionen, Texte, Verlauf – und je nach Status Senden, Annahme, Version, Auftrag. */
export default function AngebotPage() {
  const { angebotId } = useParams();
  const navigate = useNavigate();
  const { fragen, bestaetigen } = useDialoge();
  const [d, setD] = useState(null);
  const [form, setForm] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [kunden, setKunden] = useState([]);
  const [projekte, setProjekte] = useState([]);
  const [leistungen, setLeistungen] = useState([]);
  const [dialog, setDialog] = useState('');
  const [kundeDialog, setKundeDialog] = useState(false);
  const [busy, setBusy] = useState('');

  const uebernehmen = useCallback((r) => { setD(r); setForm(formAus(r.angebot)); setDirty(false); }, []);
  const laden = useCallback(() => api.get(`/api/kundenangebote/${angebotId}`).then(uebernehmen).catch((err) => { toast.error(err.message); navigate('/angebote'); }), [angebotId, navigate, uebernehmen]);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    api.get('/api/kunden').then((r) => setKunden(r.kunden)).catch(() => {});
    api.get('/api/projekte').then((r) => setProjekte((r.projekte || r).filter((p) => !p.archived && !p.verknuepft))).catch(() => {});
    api.get('/api/leistungen').then((r) => setLeistungen(r.leistungen)).catch(() => {});
  }, []);
  const a = d?.angebot;
  const bearbeitbar = !!a && (a.status === 'entwurf' || a.status === 'anfrage');
  const live = useMemo(() => (form && a ? summen(form.positionen, form.zuschlaege, form.rabatt_prozent, a.summen?.steuer) : null), [form, a]);
  const set = (patch) => { setForm((f) => ({ ...f, ...patch })); setDirty(true); };
  const setKunde = (patch) => { setForm((f) => ({ ...f, kunde: { ...f.kunde, ...patch } })); setDirty(true); };

  const speichern = async (leise = false) => {
    setBusy('speichern');
    try {
      const r = await api.put(`/api/kundenangebote/${angebotId}`, payload(form));
      setD((x) => ({ ...x, angebot: r.angebot }));
      setForm(formAus(r.angebot));
      setDirty(false);
      if (!leise) toast.success('Angebot gespeichert');
      return r.angebot;
    } catch (err) { toast.error(err.message); throw err; } finally { setBusy(''); }
  };
  /** Aktion mit vorherigem Speichern; liefert true bei Erfolg (Dialoge schließen nur dann). */
  const aktion = async (name, fn) => { setBusy(name); try { if (bearbeitbar && dirty) await speichern(true); await fn(); return true; } catch (err) { if (err?.message) toast.error(err.message); return false; } finally { setBusy(''); } };
  const pdf = () => aktion('pdf', () => openFile(`/api/kundenangebote/${angebotId}/angebot.pdf`));
  const senden = (body) => aktion('senden', async () => { const r = await api.post(`/api/kundenangebote/${angebotId}/senden`, body); toast.success(body.ohne_email ? 'Als übergeben markiert' : `Angebot an ${body.an} gesendet`); uebernehmen({ ...d, angebot: r.angebot, antwortlink: r.antwortlink }); });
  const annahme = (body) => aktion('annahme', async () => { const r = await api.post(`/api/kundenangebote/${angebotId}/annahme`, body); toast.success('Annahme erfasst – jetzt den Auftrag anlegen'); setD((x) => ({ ...x, angebot: r.angebot })); setForm(formAus(r.angebot)); });
  const ablehnen = () => aktion('ablehnen', async () => { const grund = await fragen({ titel: 'Angebot abgelehnt', text: 'Grund (für den Verlauf):', pflicht: true }); if (!grund) return; const r = await api.post(`/api/kundenangebote/${angebotId}/ablehnen`, { grund }); setD((x) => ({ ...x, angebot: r.angebot })); });
  const zurueckziehen = () => aktion('zurueckziehen', async () => { const grund = await fragen({ titel: 'Angebot zurückziehen', text: 'Grund:', pflicht: true }); if (!grund) return; const r = await api.post(`/api/kundenangebote/${angebotId}/zurueckziehen`, { grund }); setD((x) => ({ ...x, angebot: r.angebot })); });
  const neueVersion = () => aktion('version', async () => { if (!(await bestaetigen({ titel: 'Neue Version anlegen?', text: 'Diese Version bleibt als Nachweis erhalten und wird als ersetzt markiert. Die neue Version ist ein Entwurf mit denselben Positionen.' }))) return; const r = await api.post(`/api/kundenangebote/${angebotId}/version`); toast.success(`Version ${r.angebot.version} angelegt`); navigate(`/angebote/${r.angebot.id}`); });
  const kopieren = () => aktion('kopieren', async () => { const r = await api.post(`/api/kundenangebote/${angebotId}/kopieren`); toast.success(`Kopie ${r.angebot.nummer} angelegt`); navigate(`/angebote/${r.angebot.id}`); });
  const alsVorlage = () => aktion('vorlage', async () => { const name = await fragen({ titel: 'Als Vorlage speichern', text: 'Name der Vorlage:', vorgabe: form.titel, pflicht: true }); if (!name) return; await api.post(`/api/kundenangebote/${angebotId}/als-vorlage`, { name, gueltig_tage: 30 }); toast.success('Vorlage gespeichert'); });
  const loeschen = () => aktion('loeschen', async () => { if (!(await bestaetigen({ titel: 'Entwurf löschen?', text: `${a.nummer} wird gelöscht. Die Nummer wird nicht noch einmal vergeben.`, gefaehrlich: true }))) return; await api.del(`/api/kundenangebote/${angebotId}`); toast.success('Entwurf gelöscht'); navigate('/angebote'); });
  const auftrag = (body) => aktion('auftrag', async () => { const r = await api.post(`/api/kundenangebote/${angebotId}/auftrag`, body); toast.success(`Auftrag im Projekt „${r.projekt.name}“ angelegt`); laden(); });
  const ausarbeiten = () => aktion('ausarbeiten', async () => { const r = await api.put(`/api/kundenangebote/${angebotId}`, { ...payload(form), status: 'entwurf' }); uebernehmen({ ...d, angebot: r.angebot }); });
  const linkKopieren = async () => { try { await navigator.clipboard.writeText(d.antwortlink); toast.success('Antwortlink kopiert'); } catch { toast.error('Kopieren nicht möglich – Link: ' + d.antwortlink); } };

  if (!d || !form) return <Layout title="Angebot"><Ladeanzeige /></Layout>;
  const s = live || a.summen || {};
  const k = form.kunde || {};
  return (
    <Layout wide>
      <div className="flex items-start gap-3 mb-4">
        <IconBtn onClick={() => navigate('/angebote')} title="Zurück"><ArrowLeft size={20} /></IconBtn>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h1 className="text-[22px] font-semibold leading-tight">Angebot {a.nummer}</h1>{a.version > 1 && <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-black/[0.06] text-[#6E6E73]">Version {a.version}</span>}<StatusChip status={a.status} />{dirty && <span className="text-[11px] text-[#B25E00]">ungespeichert</span>}</div>
          <div className="text-[13px] text-[#6E6E73] mt-0.5">{k.name || 'Kunde fehlt'}{a.datum ? ` · ${fmtDate(fromKey(a.datum))}` : ''}{a.gueltig_bis ? ` · gültig bis ${fmtDate(fromKey(a.gueltig_bis))}` : ''}{a.projekt_name ? ` · Projekt ${a.projekt_name}` : ''}{a.created_by_name ? ` · angelegt von ${a.created_by_name}` : ''}</div>
        </div>
      </div>
      {d.versionen?.length > 1 && <div className="flex flex-wrap gap-1.5 mb-3 text-[12px]">{d.versionen.map((v) => <button key={v.id} type="button" onClick={() => v.id !== a.id && navigate(`/angebote/${v.id}`)} className={`rounded-full px-2.5 py-1 ${v.id === a.id ? 'bg-[#1D1D1F] text-white' : 'bg-black/[0.06] text-[#6E6E73]'}`}>Version {v.version} · {STATUS_NAMEN[v.status] || v.status}</button>)}</div>}
      {a.status === 'ersetzt' && a.ersetzt_durch && <div className="mb-4 rounded-2xl bg-[#FFF4E5] text-[#B25E00] px-4 py-3 text-[13px]">Diese Version wurde ersetzt. <button type="button" className="font-semibold underline" onClick={() => navigate(`/angebote/${a.ersetzt_durch}`)}>Zur aktuellen Version</button></div>}
      <div className="flex flex-wrap gap-2 mb-5">
        {bearbeitbar && <Btn onClick={() => speichern()} loading={busy === 'speichern'} disabled={!dirty}><Save size={16} /> Speichern</Btn>}
        {a.status === 'anfrage' && <Btn variant="soft" onClick={ausarbeiten} loading={busy === 'ausarbeiten'}>Angebot ausarbeiten</Btn>}
        <Btn variant="soft" onClick={pdf} loading={busy === 'pdf'}><FileDown size={16} /> PDF</Btn>
        {a.status === 'entwurf' && <Btn onClick={() => setDialog('senden')}><Send size={16} /> Senden</Btn>}
        {a.status === 'gesendet' && (<>
          <Btn variant="soft" onClick={linkKopieren}><Link2 size={16} /> Antwortlink</Btn>
          <Btn variant="soft" onClick={() => setDialog('senden')}><Mail size={16} /> Erneut senden</Btn>
          <Btn onClick={() => setDialog('annahme')}><Check size={16} /> Annahme erfassen</Btn>
          <Btn variant="soft" onClick={ablehnen} loading={busy === 'ablehnen'}><X size={16} /> Abgelehnt</Btn>
          <Btn variant="ghost" onClick={zurueckziehen} loading={busy === 'zurueckziehen'}><Undo2 size={16} /> Zurückziehen</Btn>
        </>)}
        {a.status === 'angenommen' && !a.auftrag && <Btn onClick={() => setDialog('auftrag')}><Briefcase size={16} /> Auftrag anlegen</Btn>}
        {a.auftrag?.project_id && <Btn variant="soft" onClick={() => navigate(`/projekte/${a.auftrag.project_id}`)}><Briefcase size={16} /> Projekt „{a.auftrag.projekt_name}“</Btn>}
        {['gesendet', 'abgelehnt', 'zurueckgezogen', 'abgelaufen'].includes(a.status) && <Btn variant="soft" onClick={neueVersion} loading={busy === 'version'}><GitBranch size={16} /> Neue Version</Btn>}
        {(a.status === 'entwurf' || a.status === 'anfrage') && <Btn variant="ghost" onClick={ablehnen} loading={busy === 'ablehnen'}><X size={16} /> Absage</Btn>}
        <Btn variant="ghost" onClick={kopieren} loading={busy === 'kopieren'}><Copy size={16} /> Kopieren</Btn>
        <Btn variant="ghost" onClick={alsVorlage} loading={busy === 'vorlage'}><LayoutTemplate size={16} /> Als Vorlage</Btn>
        {bearbeitbar && <Btn variant="ghost" onClick={loeschen} loading={busy === 'loeschen'} className="text-[#C41E3A]"><Trash2 size={16} /> Löschen</Btn>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5">
        <div className="space-y-5 min-w-0">
          {(a.status === 'anfrage' || form.anfrage?.text) && (
            <Card className="p-5 border border-[#1D4ED8]/20">
              <h2 className="text-[17px] mb-2">Kundenanfrage{form.anfrage?.kanal ? <span className="text-[13px] font-normal text-[#6E6E73]"> · über {form.anfrage.kanal}</span> : null}</h2>
              {bearbeitbar ? <TextArea rows={3} value={form.anfrage?.text || ''} onChange={(e) => set({ anfrage: { ...form.anfrage, text: e.target.value } })} placeholder="Was wünscht der Kunde?" /> : <p className="text-[14px] whitespace-pre-line">{form.anfrage?.text}</p>}
            </Card>
          )}
          <Card className="p-5">
            <h2 className="text-[17px] mb-3">Kunde und Rahmen</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Titel / Bauvorhaben" className="sm:col-span-2"><TextInput value={form.titel} onChange={(e) => set({ titel: e.target.value })} disabled={!bearbeitbar} /></Field>
              <Field label="Kunde">
                {bearbeitbar ? (
                  <div className="flex gap-2">
                    <Select value={form.customer_id} onChange={(e) => set({ customer_id: e.target.value })} className="flex-1"><option value="">Ohne Kundenstamm (frei eintragen)</option>{kunden.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select>
                    <Btn variant="soft" onClick={() => setKundeDialog(true)}><Plus size={15} /></Btn>
                  </div>
                ) : <div className="text-[14px]">{k.name || '–'}{k.contact ? `, ${k.contact}` : ''}<div className="text-[12px] text-[#6E6E73]">{[k.street, `${k.zip_code || ''} ${k.city || ''}`.trim(), k.email].filter(Boolean).join(' · ')}</div></div>}
              </Field>
              <Field label="Projekt (optional)"><Select value={form.project_id} onChange={(e) => set({ project_id: e.target.value })} disabled={!bearbeitbar}><option value="">Kein Projekt</option>{projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
              {bearbeitbar && !form.customer_id && (<>
                <Field label="Kundenname"><TextInput value={k.name || ''} onChange={(e) => setKunde({ name: e.target.value })} /></Field>
                <Field label="Ansprechpartner"><TextInput value={k.contact || ''} onChange={(e) => setKunde({ contact: e.target.value })} /></Field>
                <Field label="Straße"><TextInput value={k.street || ''} onChange={(e) => setKunde({ street: e.target.value })} /></Field>
                <div className="grid grid-cols-[100px_1fr] gap-2"><Field label="PLZ"><TextInput value={k.zip_code || ''} onChange={(e) => setKunde({ zip_code: e.target.value })} /></Field><Field label="Ort"><TextInput value={k.city || ''} onChange={(e) => setKunde({ city: e.target.value })} /></Field></div>
                <Field label="E-Mail" hint="für den Versand und den Antwortlink"><TextInput type="email" value={k.email || ''} onChange={(e) => setKunde({ email: e.target.value })} /></Field>
              </>)}
              {bearbeitbar && form.customer_id && <div className="text-[12px] text-[#6E6E73] sm:col-span-2">{k.contact ? `${k.contact}, ` : ''}{[k.street, `${k.zip_code || ''} ${k.city || ''}`.trim(), k.email || 'keine E-Mail hinterlegt'].filter(Boolean).join(' · ')} – Änderungen unter „Kunden“.</div>}
              <Field label="Angebotsdatum"><TextInput type="date" value={form.datum} onChange={(e) => set({ datum: e.target.value })} disabled={!bearbeitbar} /></Field>
              <Field label="Gültig bis"><TextInput type="date" value={form.gueltig_bis} onChange={(e) => set({ gueltig_bis: e.target.value })} disabled={!bearbeitbar} /></Field>
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="text-[17px] mb-3">Positionen</h2>
            <PositionenEditor positionen={form.positionen} onChange={(p) => set({ positionen: p })} leistungen={leistungen} readOnly={!bearbeitbar} />
          </Card>
          <Card className="p-5">
            <h2 className="text-[17px] mb-3">Texte</h2>
            <div className="space-y-3">
              <Field label="Einleitung"><TextArea rows={2} value={form.einleitung} onChange={(e) => set({ einleitung: e.target.value })} disabled={!bearbeitbar} /></Field>
              <Field label="Zahlungsbedingungen"><TextArea rows={2} value={form.zahlungsbedingungen} onChange={(e) => set({ zahlungsbedingungen: e.target.value })} disabled={!bearbeitbar} /></Field>
              <Field label="Schlusstext"><TextArea rows={2} value={form.schluss} onChange={(e) => set({ schluss: e.target.value })} disabled={!bearbeitbar} /></Field>
              <Field label="Interne Notiz" hint="Nie im PDF, nie für den Kunden"><TextArea rows={2} value={form.intern} onChange={(e) => set({ intern: e.target.value })} /></Field>
            </div>
            {!bearbeitbar && dirty && <div className="mt-2 flex justify-end"><Btn size="sm" onClick={async () => { try { await api.put(`/api/kundenangebote/${angebotId}`, { intern: form.intern }); setDirty(false); toast.success('Notiz gespeichert'); } catch (err) { toast.error(err.message); } }}>Notiz speichern</Btn></div>}
          </Card>
        </div>
        <div className="space-y-5">
          <Card className="p-5">
            <h2 className="text-[17px] mb-2">Summe</h2>
            <div className="text-[14px] space-y-1">
              <div className="flex justify-between"><span>Positionen netto</span><span>{fmtGeld(s.positionen_netto)}</span></div>
              {(s.zuschlaege || []).map((z, i) => <div key={i} className="flex justify-between text-[#6E6E73]"><span>zzgl. {z.text} ({fmtMenge(z.prozent)} %)</span><span>{fmtGeld(z.betrag)}</span></div>)}
              {s.rabatt_betrag > 0 && <div className="flex justify-between text-[#6E6E73]"><span>Rabatt {fmtMenge(s.rabatt_prozent)} %</span><span>– {fmtGeld(s.rabatt_betrag)}</span></div>}
              <div className="flex justify-between font-medium"><span>Netto</span><span>{fmtGeld(s.netto)}</span></div>
              <div className="flex justify-between text-[#6E6E73]"><span>{s.steuer?.kategorie === 'S' ? `USt. ${fmtMenge(s.ust_satz)} %` : 'USt. (0 %)'}</span><span>{fmtGeld(s.ust)}</span></div>
              <div className="flex justify-between font-semibold text-[17px] border-t border-black/20 pt-1.5"><span>Brutto</span><span>{fmtGeld(s.brutto)}</span></div>
              {s.alternativ_netto > 0 && <div className="text-[12px] text-[#6E6E73]">Alternativpositionen: {fmtGeld(s.alternativ_netto)} (nicht enthalten)</div>}
              {s.eventual_netto > 0 && <div className="text-[12px] text-[#6E6E73]">Eventualpositionen: {fmtGeld(s.eventual_netto)} (nur bei Bedarf)</div>}
              {s.steuer?.hinweis && <div className="text-[12px] text-[#6E6E73]">{s.steuer.hinweis}</div>}
            </div>
            {bearbeitbar && (
              <div className="mt-4 space-y-2">
                <div className="text-[12px] font-semibold text-[#6E6E73]">Zuschläge und Rabatt</div>
                {(form.zuschlaege || []).map((z, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <TextInput value={z.text || ''} onChange={(e) => set({ zuschlaege: form.zuschlaege.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)) })} placeholder="Zuschlag" className="flex-1 h-9" />
                    <TextInput type="number" inputMode="decimal" step="0.1" min="0" value={z.prozent ?? ''} onChange={(e) => set({ zuschlaege: form.zuschlaege.map((x, j) => (j === i ? { ...x, prozent: e.target.value } : x)) })} className="w-20 h-9 text-right" /><span className="text-[13px]">%</span>
                    <IconBtn size={28} onClick={() => set({ zuschlaege: form.zuschlaege.filter((_, j) => j !== i) })} className="text-[#C41E3A]"><Trash2 size={14} /></IconBtn>
                  </div>
                ))}
                <Btn size="sm" variant="ghost" onClick={() => set({ zuschlaege: [...(form.zuschlaege || []), { text: '', prozent: 0 }] })}><Plus size={14} /> Zuschlag</Btn>
                <label className="flex items-center gap-2 text-[13px]">Rabatt auf die Summe <TextInput type="number" inputMode="decimal" step="0.1" min="0" max="100" value={form.rabatt_prozent ?? ''} onChange={(e) => set({ rabatt_prozent: e.target.value })} className="w-20 h-9 text-right" /> %</label>
              </div>
            )}
          </Card>
          {a.annahme && <Card className="p-5 border border-[#1B7F3B]/30"><h2 className="text-[17px] mb-1">Annahme</h2><div className="text-[14px]">{a.annahme.von_name}{a.annahme.am ? ` am ${fmtDate(fromKey(a.annahme.am))}` : ''} · {ANNAHMEARTEN[a.annahme.art] || a.annahme.art}</div>{a.annahme.text && <div className="text-[13px] text-[#6E6E73] mt-1 whitespace-pre-line">{a.annahme.text}</div>}</Card>}
          {a.ablehnung && <Card className="p-5 border border-[#C41E3A]/30"><h2 className="text-[17px] mb-1">Ablehnung</h2><div className="text-[14px]">{a.ablehnung.grund}</div><div className="text-[12px] text-[#6E6E73]">{a.ablehnung.am ? fmtDate(fromKey(a.ablehnung.am)) : ''} · {a.ablehnung.erfasst_von}</div></Card>}
          {a.versand?.length > 0 && <Card className="p-5"><h2 className="text-[17px] mb-1">Versand</h2><ul className="text-[13px] space-y-1">{a.versand.map((v, i) => <li key={i}>{v.at ? new Date(v.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''} · {v.art === 'ohne_email' ? 'ohne E-Mail übergeben' : `an ${v.an}`} · {v.user_name}</li>)}</ul>{d.antwortlink && <div className="text-[12px] text-[#6E6E73] mt-2 break-all">Antwortlink: {d.antwortlink}</div>}</Card>}
          <Card className="p-5"><h2 className="text-[17px] mb-1">Verlauf</h2><ul className="text-[13px] space-y-1.5">{(a.verlauf || []).slice().reverse().map((v, i) => <li key={i}><span className="text-[#6E6E73]">{v.at ? new Date(v.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}</span> · <span className="font-medium">{v.aktion}</span> · {v.user_name}{v.text ? ` – ${v.text}` : ''}</li>)}</ul></Card>
        </div>
      </div>
      {d.kann_kalkulation && a.status !== 'ersetzt' && (
        <div className="mt-5"><KalkulationPanel angebotId={a.id} positionen={a.positionen} kalkulation={a.kalkulation} bearbeitbar={bearbeitbar} onAngebot={(neu) => { setD((x) => ({ ...x, angebot: neu })); if (!dirty) setForm(formAus(neu)); }} /></div>
      )}
      <SendenDialog open={dialog === 'senden'} onOpenChange={(v) => setDialog(v ? 'senden' : '')} kunde={k} onSenden={senden} />
      <AnnahmeDialog open={dialog === 'annahme'} onOpenChange={(v) => setDialog(v ? 'annahme' : '')} onAnnahme={annahme} />
      <AuftragDialog open={dialog === 'auftrag'} onOpenChange={(v) => setDialog(v ? 'auftrag' : '')} angebot={a} projekte={projekte} onAuftrag={auftrag} />
      <KundeDialog open={kundeDialog} onOpenChange={setKundeDialog} kunde={null} onSaved={(neu) => { setKunden((ks) => [...ks, neu].sort((x, y) => x.name.localeCompare(y.name))); set({ customer_id: neu.id }); }} />
    </Layout>
  );
}
