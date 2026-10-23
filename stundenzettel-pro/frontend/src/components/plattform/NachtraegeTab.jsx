import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FileSignature, FileText, Paperclip, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, Field, Select, Sheet, TextArea, TextInput } from '../ui';
import { api, openFile } from '../../lib/api';
import { fmtEur } from '../../lib/dates';

const CLS = { angefragt: 'bg-[#E8F0FE] text-[#1D4ED8]', entwurf: 'bg-black/[0.06] text-[#6E6E73]', eingereicht: 'bg-[#FFF4E5] text-[#B25E00]', freigegeben: 'bg-[#1B7F3B] text-white', abgelehnt: 'bg-[#FDE8E8] text-[#C41E3A]', zurueckgezogen: 'bg-black/[0.06] text-[#6E6E73]' };
const chip = (st, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${CLS[st] || ''}`}>{name || st}</span>;
const fmtZeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '–');
const LEER = { firma_id: '', titel: '', beschreibung: '', grund: '', betrag_netto: '' };

/** Nachträge: zusätzliche Leistungen mit Preis, Einreichung durch die Firma und dokumentierter Freigabe durch den Auftraggeber.
 *  Ursprünglicher Auftrag, Nachtrag, Zustimmung und spätere Rechnung bleiben getrennt; der Auftragswert ändert sich erst mit der Freigabe. */
export default function NachtraegeTab({ projectId, className = '' }) {
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState(null);
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/nachtraege`).then(setDaten).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const speichern = async (e) => {
    e.preventDefault();
    const body = { ...form, firma_id: form.firma_id || null, betrag_netto: form.betrag_netto === '' ? null : parseFloat(String(form.betrag_netto).replace(',', '.')) };
    setBusy(true);
    try { const r = await api.post(`/api/projekte/${projectId}/nachtraege`, body); toast.success(daten.rolle === 'leitung' ? 'Nachtrag bei der Firma angefragt' : 'Nachtrag als Entwurf gespeichert'); setForm(null); laden(); setOffen(r.nachtrag.id); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  if (!daten) return <Card className={`p-8 text-center text-[#A1A1A6] ${className}`}>Wird geladen …</Card>;
  const leitung = daten.rolle === 'leitung';
  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[17px] flex items-center gap-2"><FileSignature size={17} /> Nachträge</h2>
          <p className="text-[13px] text-[#6E6E73]">{leitung ? 'Zusätzliche Leistungen anfragen, eingereichte Nachträge prüfen und freigeben – der Auftragswert ändert sich erst mit der Freigabe.' : 'Zusätzliche Arbeiten mit Preis einreichen; erst die Freigabe des Auftraggebers ändert den Auftragswert.'}</p>
        </div>
        <Btn onClick={() => setForm({ ...LEER, firma_id: daten.firmen[0]?.id || '' })}><Plus size={17} /> {leitung ? 'Nachtrag anfragen' : 'Nachtrag anlegen'}</Btn>
      </div>
      {daten.firmen.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {daten.firmen.map((f) => (
            <div key={f.id} className="rounded-2xl bg-white shadow-card px-4 py-3 text-[13px]">
              <div className="font-semibold truncate">{f.name}{f.gewerk ? <span className="text-[#6E6E73] font-normal"> · {f.gewerk}</span> : ''}</div>
              <div className="text-[#6E6E73]">Auftrag: <strong className="text-[#1D1D1F]">{f.auftragswert != null ? fmtEur(f.auftragswert) : 'ohne Vergabe'}</strong> · Nachträge: <strong className="text-[#1D1D1F]">{fmtEur(f.nachtraege_summe)}</strong>{f.auftragswert != null ? <> · aktuell <strong className="text-[#1D1D1F]">{fmtEur(f.auftragswert + f.nachtraege_summe)}</strong></> : null}</div>
            </div>
          ))}
        </div>
      )}
      {daten.nachtraege.length === 0 ? <Card><Empty icon={FileSignature} title="Keine Nachträge" text="Ein Nachtrag hält die zusätzliche Leistung, den Preis und die schriftliche Zustimmung fest – so kann später niemand behaupten, eine Preisänderung sei nie vereinbart worden." /></Card> : (
        <Card className="p-4">
          <ul className="divide-y divide-black/[0.06]">
            {daten.nachtraege.map((n) => (
              <li key={n.id} className="py-2.5 flex items-center gap-3">
                <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(n.id)}>
                  <div className="text-[15px] font-semibold truncate">{n.nummer} · {n.titel}</div>
                  <div className="text-[12px] text-[#6E6E73] truncate">{[n.firma_name, n.gewerk, n.betrag_netto != null ? `${fmtEur(n.betrag_netto)} netto` : 'Preis offen', n.eingereicht_at ? `eingereicht ${fmtZeit(n.eingereicht_at)}` : `angelegt ${fmtZeit(n.created_at)}`].filter(Boolean).join(' · ')}</div>
                </button>
                {chip(n.status, n.status_name)}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Sheet open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }} title={leitung ? 'Nachtrag anfragen' : 'Nachtrag anlegen'} subtitle={leitung ? 'Die Firma trägt den Preis ein und reicht den Nachtrag ein.' : 'Als Entwurf speichern, dann prüfen und einreichen.'}>
        {form && (
          <form onSubmit={speichern} className="space-y-4">
            {leitung && <Field label="Beauftragte Firma"><Select value={form.firma_id} onChange={set('firma_id')} className="w-full" required>{daten.firmen.map((f) => <option key={f.id} value={f.id}>{f.name}{f.gewerk ? ` · ${f.gewerk}` : ''}</option>)}</Select></Field>}
            <Field label="Titel"><TextInput value={form.titel} onChange={set('titel')} required placeholder="z. B. Zusätzliche Leitungen Halle B" /></Field>
            <Field label="Zusätzliche Leistung"><TextArea rows={3} value={form.beschreibung} onChange={set('beschreibung')} placeholder="Was wird zusätzlich gemacht, welche Mengen?" /></Field>
            <Field label="Anlass / Begründung"><TextInput value={form.grund} onChange={set('grund')} placeholder="z. B. Planänderung des Auftraggebers" /></Field>
            {!leitung && <Field label="Nachtrag netto (€)"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={form.betrag_netto} onChange={set('betrag_netto')} placeholder="0,00" /></Field>}
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{leitung ? 'Anfragen' : 'Speichern'}</Btn></div>
          </form>
        )}
      </Sheet>
      <NachtragDialog nachtragId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} />
    </div>
  );
}

function NachtragDialog({ nachtragId, onOpenChange, onChanged }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState('');
  const [begruendung, setBegruendung] = useState('');
  const [bearbeiten, setBearbeiten] = useState(null);
  const eingabe = useRef(null);
  const laden = useCallback(() => { if (!nachtragId) { setD(null); setBearbeiten(null); return; } api.get(`/api/nachtraege/${nachtragId}`).then(setD).catch((err) => toast.error(err.message)); }, [nachtragId]);
  useEffect(() => { laden(); }, [laden]);
  const aktion = async (pfad, body, meldung) => { setBusy(pfad); try { await api.post(pfad, body || {}); toast.success(meldung); setBegruendung(''); laden(); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const speichern = async (e) => {
    e.preventDefault();
    setBusy('speichern');
    try { await api.put(`/api/nachtraege/${nachtragId}`, { ...bearbeiten, betrag_netto: bearbeiten.betrag_netto === '' ? null : parseFloat(String(bearbeiten.betrag_netto).replace(',', '.')) }); toast.success('Gespeichert'); setBearbeiten(null); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const hochladen = async (dateien) => {
    const liste = Array.from(dateien || []);
    if (!liste.length) return;
    setBusy('datei');
    try { for (const f of liste) { const fd = new FormData(); fd.append('datei', f); await api.upload(`/api/nachtraege/${nachtragId}/dokumente`, fd); } toast.success('Datei gespeichert'); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const n = d?.nachtrag;
  const leitung = d?.rolle === 'leitung';
  const firma = d?.rolle === 'firma';
  const offenZumBearbeiten = n && ['angefragt', 'entwurf'].includes(n.status);
  return (
    <Sheet open={!!nachtragId} onOpenChange={onOpenChange} title={n ? `Nachtrag ${n.nummer}` : 'Nachtrag'} subtitle={n ? `${n.firma_name}${n.gewerk ? ` · ${n.gewerk}` : ''} · ${d.projekt?.name || ''}` : ''} width="sm:max-w-2xl">
      {!n ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">{chip(n.status, n.status_name)}<span className="text-[12px] text-[#6E6E73]">angelegt von {n.erstellt_von?.name} ({n.erstellt_von?.firma_name}) am {fmtZeit(n.created_at)}</span></div>
          {bearbeiten ? (
            <form onSubmit={speichern} className="space-y-3 rounded-2xl bg-[#F5F5F7] p-4">
              <Field label="Titel"><TextInput value={bearbeiten.titel} onChange={(e) => setBearbeiten({ ...bearbeiten, titel: e.target.value })} required /></Field>
              <Field label="Zusätzliche Leistung"><TextArea rows={3} value={bearbeiten.beschreibung} onChange={(e) => setBearbeiten({ ...bearbeiten, beschreibung: e.target.value })} /></Field>
              <Field label="Anlass / Begründung"><TextInput value={bearbeiten.grund} onChange={(e) => setBearbeiten({ ...bearbeiten, grund: e.target.value })} /></Field>
              {firma && <Field label="Nachtrag netto (€)"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={bearbeiten.betrag_netto} onChange={(e) => setBearbeiten({ ...bearbeiten, betrag_netto: e.target.value })} /></Field>}
              <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setBearbeiten(null)}>Abbrechen</Btn><Btn type="submit" loading={busy === 'speichern'}>Speichern</Btn></div>
            </form>
          ) : (
            <>
              <div className="text-[15px] font-semibold">{n.titel}</div>
              {n.beschreibung && <p className="text-[14px] whitespace-pre-wrap rounded-2xl bg-[#F5F5F7] px-4 py-3">{n.beschreibung}</p>}
              {n.grund && <p className="text-[13px] text-[#6E6E73]">Anlass: {n.grund}</p>}
              <div className="grid grid-cols-3 gap-2 text-[13px]">
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Ursprünglicher Auftrag</div><div className="font-semibold">{n.auftragswert_vorher != null ? fmtEur(n.auftragswert_vorher) : '–'}</div></div>
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Nachtrag netto</div><div className="font-semibold">{n.betrag_netto != null ? fmtEur(n.betrag_netto) : 'offen'}</div></div>
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Nach Zustimmung</div><div className="font-semibold">{n.status === 'freigegeben' && n.auftragswert_nachher != null ? fmtEur(n.auftragswert_nachher) : 'erst nach Freigabe'}</div></div>
              </div>
            </>
          )}
          <div className="flex flex-wrap gap-2">
            {firma && offenZumBearbeiten && !bearbeiten && <Btn size="sm" variant="soft" onClick={() => setBearbeiten({ titel: n.titel, beschreibung: n.beschreibung || '', grund: n.grund || '', betrag_netto: n.betrag_netto ?? '' })}>Bearbeiten</Btn>}
            {leitung && n.status === 'angefragt' && !bearbeiten && <Btn size="sm" variant="soft" onClick={() => setBearbeiten({ titel: n.titel, beschreibung: n.beschreibung || '', grund: n.grund || '' })}>Bearbeiten</Btn>}
            {firma && offenZumBearbeiten && <Btn size="sm" onClick={() => { if (window.confirm('Nachtrag einreichen? Danach entscheidet der Auftraggeber.')) aktion(`/api/nachtraege/${nachtragId}/einreichen`, {}, 'Nachtrag eingereicht'); }} loading={busy.endsWith('einreichen')}>Einreichen</Btn>}
            {firma && ['entwurf', 'eingereicht'].includes(n.status) && <Btn size="sm" variant="ghost" onClick={() => { if (window.confirm('Nachtrag zurückziehen?')) aktion(`/api/nachtraege/${nachtragId}/zurueckziehen`, {}, 'Zurückgezogen'); }}>Zurückziehen</Btn>}
            <Btn size="sm" variant="soft" onClick={() => openFile(`/api/nachtraege/${nachtragId}/pdf`).catch((err) => toast.error(err.message))}><FileText size={14} /> PDF</Btn>
          </div>
          {leitung && n.status === 'eingereicht' && (
            <div className="rounded-2xl bg-[#FFF4E5] p-4 space-y-2">
              <div className="text-[13px] font-medium text-[#7A4100]">Entscheidung des Auftraggebers – wird mit Name und Zeit protokolliert.</div>
              <TextInput value={begruendung} onChange={(e) => setBegruendung(e.target.value)} placeholder="Begründung (bei Ablehnung Pflicht)" className="h-9 text-[13px]" />
              <div className="flex gap-2"><Btn size="sm" onClick={() => { if (window.confirm(`Nachtrag ${n.nummer} über ${fmtEur(n.betrag_netto)} netto freigeben?`)) aktion(`/api/nachtraege/${nachtragId}/entscheiden`, { freigeben: true, begruendung }, 'Nachtrag freigegeben'); }} loading={busy.endsWith('entscheiden')}>Freigeben</Btn><Btn size="sm" variant="danger" onClick={() => aktion(`/api/nachtraege/${nachtragId}/entscheiden`, { freigeben: false, begruendung }, 'Nachtrag abgelehnt')}>Ablehnen</Btn></div>
            </div>
          )}
          {n.status === 'freigegeben' && <p className="text-[13px] text-[#1B7F3B]">Freigegeben von {n.entschieden_von?.name} am {fmtZeit(n.entschieden_at)}{n.entscheidung_begruendung ? ` – „${n.entscheidung_begruendung}“` : ''}.</p>}
          {n.status === 'abgelehnt' && <p className="text-[13px] text-[#C41E3A]">Abgelehnt von {n.entschieden_von?.name} am {fmtZeit(n.entschieden_at)}{n.entscheidung_begruendung ? ` – „${n.entscheidung_begruendung}“` : ''}.</p>}
          <div>
            <div className="flex items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Paperclip size={14} /> Unterlagen ({n.dokumente?.length || 0})</span><input ref={eingabe} type="file" multiple className="hidden" onChange={(e) => { hochladen(e.target.files); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'datei'}><Paperclip size={14} /> Datei</Btn></div>
            {(n.dokumente || []).length > 0 && <ul className="text-[13px] space-y-1">{n.dokumente.map((f) => <li key={f.id}><button type="button" className="text-[#C41E3A] font-medium" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))}>{f.filename}</button> <span className="text-[#6E6E73]">· {f.uploaded_by_name}{f.note ? ` · ${f.note}` : ''}</span></li>)}</ul>}
          </div>
          {(n.verlauf || []).length > 0 && <ul className="text-[12px] text-[#6E6E73] space-y-0.5">{n.verlauf.slice().reverse().map((v, i) => <li key={i}>{fmtZeit(v.at)} · {v.status} · {v.user_name} ({v.firma_name}){v.kommentar ? ` · „${v.kommentar}“` : ''}</li>)}</ul>}
        </div>
      )}
    </Sheet>
  );
}
