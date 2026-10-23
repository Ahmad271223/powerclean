import React, { useCallback, useEffect, useState } from 'react';
import { Building2, Copy, Link2, Mail, Plus, Search, Trash2, UserCog } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Chip, Field, IconBtn, Select, Sheet, TextArea, TextInput } from '../ui';
import { api } from '../../lib/api';

const STATUS = { eingeladen: ['Eingeladen', 'bg-[#FFF4E5] text-[#B25E00]'], aktiv: ['Beteiligt', 'bg-[#E8F8EC] text-[#1B7F3B]'], abgelehnt: ['Abgelehnt', 'bg-black/[0.06] text-[#6E6E73]'] };

/** Eigentümerseite: Projektleitung (mehrere je Projekt) und beteiligte Firmen (einladen, Status, entfernen). */
export default function FirmenTab({ projectId, isBuero }) {
  const [daten, setDaten] = useState(null);
  const [leiter, setLeiter] = useState([]);
  const [mitarbeiter, setMitarbeiter] = useState([]);
  const [einladen, setEinladen] = useState(false);
  const [neuLeiter, setNeuLeiter] = useState({ user_id: '', funktion: 'Projektleitung' });
  const laden = useCallback(() => Promise.all([api.get(`/api/projekte/${projectId}/beteiligungen`), api.get(`/api/projekte/${projectId}/leiter`)]).then(([b, l]) => { setDaten(b); setLeiter(l.leiter); }).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => { if (isBuero) api.get('/api/mitarbeiter').then((r) => setMitarbeiter(r.mitarbeiter.filter((m) => m.active !== false))).catch(() => {}); }, [isBuero]);

  const leiterZuordnen = async () => {
    if (!neuLeiter.user_id) return;
    try { await api.post(`/api/projekte/${projectId}/leiter`, neuLeiter); toast.success('Projektleitung zugeordnet'); setNeuLeiter({ user_id: '', funktion: 'Projektleitung' }); laden(); } catch (err) { toast.error(err.message); }
  };
  const leiterEntfernen = async (l) => { if (!window.confirm(`${l.user_name} aus der Projektleitung entfernen?`)) return; try { await api.del(`/api/projekte/${projectId}/leiter/${l.user_id}`); laden(); } catch (err) { toast.error(err.message); } };
  const entfernen = async (b) => { if (!window.confirm(`${b.firma.name} aus dem Projekt entfernen? Die Firma verliert den Zugang zu Aufgaben und Projektdaten.`)) return; try { await api.del(`/api/projekte/${projectId}/beteiligungen/${b.id}`); toast.success('Firma entfernt'); laden(); } catch (err) { toast.error(err.message); } };

  if (!daten) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card className="p-5 space-y-3">
        <h2 className="text-[16px] flex items-center gap-2"><UserCog size={16} /> Projektleitung</h2>
        {leiter.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch niemand eingetragen. Büro und Inhaber sehen ohnehin alles; Projektleiter mit Vorarbeiter-Rolle sehen nur zugeordnete Projekte.</p> : (
          <ul className="divide-y divide-black/[0.06]">{leiter.map((l) => <li key={l.id} className="py-2 flex items-center gap-2 text-[14px]"><div className="flex-1 min-w-0"><div className="font-semibold truncate">{l.user_name}</div><div className="text-[12px] text-[#6E6E73]">{l.funktion}</div></div>{isBuero && <IconBtn size={30} variant="danger" onClick={() => leiterEntfernen(l)} title="Entfernen"><Trash2 size={14} /></IconBtn>}</li>)}</ul>
        )}
        {isBuero && (
          <div className="flex flex-wrap gap-2 items-end">
            <Field label="Mitarbeiter" className="flex-1 min-w-[160px]"><Select value={neuLeiter.user_id} onChange={(e) => setNeuLeiter((n) => ({ ...n, user_id: e.target.value }))} className="w-full"><option value="">– wählen –</option>{mitarbeiter.filter((m) => !leiter.some((l) => l.user_id === m.id)).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Select></Field>
            <Field label="Funktion" className="flex-1 min-w-[140px]"><TextInput value={neuLeiter.funktion} onChange={(e) => setNeuLeiter((n) => ({ ...n, funktion: e.target.value }))} placeholder="z. B. Bauleiter" /></Field>
            <Btn variant="dark" onClick={leiterZuordnen} disabled={!neuLeiter.user_id}><Plus size={15} /> Zuordnen</Btn>
          </div>
        )}
      </Card>

      <Card className="p-5 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[16px] flex items-center gap-2"><Building2 size={16} /> Beteiligte Firmen</h2>
          {daten.leitung && <Btn size="sm" onClick={() => setEinladen(true)}><Plus size={15} /> Firma einladen</Btn>}
        </div>
        {daten.beteiligungen.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine Firma. Lade Subunternehmer über das Firmenverzeichnis oder per E-Mail ein; sie sehen nur Aufgaben und Projektdaten, nie eure internen Daten.</p> : (
          <ul className="divide-y divide-black/[0.06]">
            {daten.beteiligungen.map((b) => (
              <li key={b.id} className="py-2.5 flex items-center gap-2 text-[14px]">
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate">{b.firma.name}{b.firma.city ? <span className="text-[#6E6E73] font-normal"> · {b.firma.city}</span> : null}</div>
                  <div className="text-[12px] text-[#6E6E73]">{[b.gewerk, b.rolle_name, b.kontakt_name ? `Kontakt ${b.kontakt_name}` : b.email].filter(Boolean).join(' · ')}</div>
                </div>
                <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS[b.status]?.[1] || ''}`}>{STATUS[b.status]?.[0] || b.status}</span>
                {daten.leitung && b.status !== 'abgelehnt' && <IconBtn size={30} variant="danger" onClick={() => entfernen(b)} title="Aus dem Projekt entfernen"><Trash2 size={14} /></IconBtn>}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <EinladenDialog open={einladen} onOpenChange={setEinladen} projectId={projectId} gewerke={daten.gewerke} rollen={daten.rollen} onSaved={laden} />
    </div>
  );
}

function EinladenDialog({ open, onOpenChange, projectId, gewerke, rollen, onSaved }) {
  const [art, setArt] = useState('suche');
  const [q, setQ] = useState('');
  const [treffer, setTreffer] = useState(null);
  const [wahl, setWahl] = useState(null);
  const [form, setForm] = useState({ firma_name: '', email: '', gewerk: '', rolle: 'subunternehmer', nachricht: '' });
  const [link, setLink] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setArt('suche'); setQ(''); setTreffer(null); setWahl(null); setLink(''); setForm({ firma_name: '', email: '', gewerk: '', rolle: 'subunternehmer', nachricht: '' }); } }, [open]);
  const suchen = async () => { try { setTreffer((await api.get(`/api/verzeichnis/firmen?q=${encodeURIComponent(q)}`)).firmen); } catch (err) { toast.error(err.message); } };
  const senden = async () => {
    const body = art === 'suche' ? { firma_id: wahl?.id, gewerk: form.gewerk, rolle: form.rolle, nachricht: form.nachricht } : form;
    if (art === 'suche' && !wahl) { toast.error('Bitte eine Firma aus dem Verzeichnis wählen'); return; }
    setBusy(true);
    try { const r = await api.post(`/api/projekte/${projectId}/beteiligungen`, body); toast.success('Einladung gesendet'); onSaved?.(); if (art === 'email') setLink(r.beteiligung.einladung_link); else onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Firma zum Projekt einladen" subtitle="Die Firma muss annehmen. Danach sieht sie ihre Aufgaben, nie eure internen Daten.">
      <div className="space-y-4">
        <div className="flex gap-2"><Chip active={art === 'suche'} onClick={() => setArt('suche')}><Search size={13} /> Im Verzeichnis suchen</Chip><Chip active={art === 'email'} onClick={() => setArt('email')}><Mail size={13} /> Per E-Mail einladen</Chip></div>
        {art === 'suche' ? (
          <>
            <div className="flex gap-2"><TextInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Firmenname, Ort oder Gewerk" onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); suchen(); } }} /><Btn variant="dark" onClick={suchen}>Suchen</Btn></div>
            {treffer && (treffer.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Keine sichtbare Firma gefunden. Nur Firmen, die sich im Verzeichnis freigeschaltet haben, erscheinen hier. Alternative: per E-Mail einladen.</p> : (
              <ul className="rounded-2xl bg-[#F5F5F7] divide-y divide-black/[0.06]">{treffer.map((t) => <li key={t.id}><button type="button" onClick={() => setWahl(t)} className={`w-full text-left px-4 py-2.5 ${wahl?.id === t.id ? 'bg-[#C41E3A]/10' : ''}`}><div className="text-[14px] font-semibold">{t.name} <span className="text-[12px] font-normal text-[#6E6E73]">{t.ort}</span></div><div className="text-[12px] text-[#6E6E73]">{t.gewerke.join(', ')}{t.beschreibung ? ` · ${t.beschreibung}` : ''} · bereits registriert</div></button></li>)}</ul>
            ))}
          </>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Firmenname"><TextInput value={form.firma_name} onChange={set('firma_name')} required /></Field>
            <Field label="E-Mail der Firma"><TextInput type="email" value={form.email} onChange={set('email')} required /></Field>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Gewerk"><TextInput list="gewerke-einladen" value={form.gewerk} onChange={set('gewerk')} /><datalist id="gewerke-einladen">{gewerke.map((g) => <option key={g} value={g} />)}</datalist></Field>
          <Field label="Rolle im Projekt"><Select value={form.rolle} onChange={set('rolle')} className="w-full">{Object.entries(rollen).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        </div>
        <Field label="Nachricht (optional)"><TextArea rows={2} value={form.nachricht} onChange={set('nachricht')} /></Field>
        {link ? (
          <div className="rounded-2xl bg-[#E8F8EC] px-4 py-3 text-[13px]"><div className="font-semibold flex items-center gap-1.5"><Link2 size={14} /> Einladungslink (30 Tage gültig)</div><div className="break-all select-all mt-1">{link}</div><Btn size="sm" variant="soft" className="mt-2" onClick={() => navigator.clipboard?.writeText(link).then(() => toast.success('Kopiert'))}><Copy size={13} /> Kopieren und an die Firma schicken</Btn></div>
        ) : <div className="flex justify-end gap-2"><Btn variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={senden} loading={busy}>Einladen</Btn></div>}
      </div>
    </Sheet>
  );
}
