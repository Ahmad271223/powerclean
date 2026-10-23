import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, FileText, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, Field, Select, Sheet, TextArea, TextInput } from '../ui';
import { api, openFile } from '../../lib/api';
import { fmtDate, fromKey } from '../../lib/dates';

const CLS = { angefordert: 'bg-[#E8F0FE] text-[#1D4ED8]', entwurf: 'bg-black/[0.06] text-[#6E6E73]', erstellt: 'bg-[#FFF4E5] text-[#B25E00]', bestaetigt: 'bg-[#1B7F3B] text-white', widersprochen: 'bg-[#FDE8E8] text-[#C41E3A]' };
const chip = (st, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${CLS[st] || ''}`}>{name || st}</span>;
const fmtZeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '–');
const heute = () => new Date().toISOString().slice(0, 10);

/** Abnahmen: die Firma fordert an, die Projektleitung des Auftraggebers protokolliert (Ergebnis, Vorbehalte, offene Mängel mit Frist),
 *  die Firma bestätigt oder widerspricht. Ein erstelltes Protokoll ist unveränderlich und als PDF für beide Seiten verfügbar. */
export default function AbnahmenTab({ projectId, className = '' }) {
  const [daten, setDaten] = useState(null);
  const [form, setForm] = useState(null);
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/abnahmen`).then(setDaten).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const anlegen = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { const r = await api.post(`/api/projekte/${projectId}/abnahmen`, { ...form, firma_id: form.firma_id || null, datum: form.datum || null }); toast.success(daten.rolle === 'leitung' ? 'Entwurf angelegt – jetzt Ergebnis und Mängel eintragen' : 'Abnahme angefordert'); setForm(null); laden(); setOffen(r.abnahme.id); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  if (!daten) return <Card className={`p-8 text-center text-[#A1A1A6] ${className}`}>Wird geladen …</Card>;
  const leitung = daten.rolle === 'leitung';
  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[17px] flex items-center gap-2"><ClipboardCheck size={17} /> Abnahmen</h2>
          <p className="text-[13px] text-[#6E6E73]">{leitung ? 'Teil-, End- oder Gesamtabnahme protokollieren: Ergebnis, Vorbehalte, offene Mängel mit Frist. Die Firma bestätigt oder widerspricht.' : 'Abnahme anfordern, wenn eine Leistung fertig ist; das Protokoll des Auftraggebers bestätigen oder widersprechen.'}</p>
        </div>
        <Btn onClick={() => setForm({ firma_id: daten.firmen[0]?.id || '', art: 'abnahme', gewerk: daten.firmen[0]?.gewerk || '', bereich: '', datum: heute(), bemerkung: '' })}><Plus size={17} /> {leitung ? 'Abnahme protokollieren' : 'Abnahme anfordern'}</Btn>
      </div>
      {daten.abnahmen.length === 0 ? <Card><Empty icon={ClipboardCheck} title="Keine Abnahmen" text="Eine dokumentierte Abnahme schließt eine Leistung ab und hält offene Mängel mit Nachbesserungsfrist fest." /></Card> : (
        <Card className="p-4">
          <ul className="divide-y divide-black/[0.06]">
            {daten.abnahmen.map((a) => (
              <li key={a.id} className="py-2.5 flex items-center gap-3">
                <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(a.id)}>
                  <div className="text-[15px] font-semibold truncate">{a.nummer} · {a.art_name}{a.gewerk ? ` · ${a.gewerk}` : ''}</div>
                  <div className="text-[12px] text-[#6E6E73] truncate">{[a.firma_name, a.datum && fmtDate(fromKey(a.datum)), a.ergebnis_name, a.maengel?.length ? `${a.maengel.length} Mängel` : ''].filter(Boolean).join(' · ')}</div>
                </button>
                {chip(a.status, a.status_name)}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Sheet open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }} title={leitung ? 'Abnahme protokollieren' : 'Abnahme anfordern'} subtitle={leitung ? 'Zuerst als Entwurf; Ergebnis und Mängel folgen im nächsten Schritt.' : 'Die Projektleitung des Auftraggebers führt das Protokoll.'}>
        {form && (
          <form onSubmit={anlegen} className="space-y-4">
            {leitung && <Field label="Firma"><Select value={form.firma_id} onChange={(e) => { const id = e.target.value; const f = daten.firmen.find((x) => x.id === id); setForm((x) => ({ ...x, firma_id: id, gewerk: f?.gewerk || x.gewerk })); }} className="w-full" required>{daten.firmen.map((f) => <option key={f.id} value={f.id}>{f.name}{f.gewerk ? ` · ${f.gewerk}` : ''}{f.maengel_offen ? ` (${f.maengel_offen} offene Mängel)` : ''}</option>)}</Select></Field>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Art"><Select value={form.art} onChange={set('art')} className="w-full">{Object.entries(daten.arten).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
              <Field label="Datum"><TextInput type="date" value={form.datum} onChange={set('datum')} /></Field>
              <Field label="Gewerk"><TextInput value={form.gewerk} onChange={set('gewerk')} /></Field>
              <Field label="Bereich / Bauabschnitt"><TextInput value={form.bereich} onChange={set('bereich')} /></Field>
            </div>
            <Field label={leitung ? 'Bemerkung' : 'Nachricht an den Auftraggeber'}><TextArea rows={2} value={form.bemerkung} onChange={set('bemerkung')} /></Field>
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{leitung ? 'Entwurf anlegen' : 'Anfordern'}</Btn></div>
          </form>
        )}
      </Sheet>
      <AbnahmeDialog abnahmeId={offen} arten={daten.arten} ergebnisse={daten.ergebnisse} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} />
    </div>
  );
}

function AbnahmeDialog({ abnahmeId, arten, ergebnisse, onOpenChange, onChanged }) {
  const [d, setD] = useState(null);
  const [form, setForm] = useState(null);
  const [kommentar, setKommentar] = useState('');
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => { if (!abnahmeId) { setD(null); setForm(null); return; } api.get(`/api/abnahmen/${abnahmeId}`).then((r) => { setD(r); const a = r.abnahme; if (r.rolle === 'leitung' && ['angefordert', 'entwurf'].includes(a.status)) setForm({ art: a.art, gewerk: a.gewerk || '', bereich: a.bereich || '', datum: a.datum || '', teilnehmer: a.teilnehmer || '', ergebnis: a.ergebnis || 'abgenommen', vorbehalte: a.vorbehalte || '', nachbesserung_bis: a.nachbesserung_bis || '', bemerkung: a.bemerkung || '', maengel_ids: (a.maengel || []).map((m) => m.id) }); else setForm(null); }).catch((err) => toast.error(err.message)); }, [abnahmeId]);
  useEffect(() => { laden(); }, [laden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const toggleMangel = (id) => setForm((f) => ({ ...f, maengel_ids: f.maengel_ids.includes(id) ? f.maengel_ids.filter((x) => x !== id) : [...f.maengel_ids, id] }));
  const speichern = async (abschliessen) => {
    setBusy(abschliessen ? 'abschliessen' : 'speichern');
    try {
      await api.put(`/api/abnahmen/${abnahmeId}`, { ...form, datum: form.datum || null, nachbesserung_bis: form.nachbesserung_bis || null });
      if (abschliessen) { if (!window.confirm('Abnahmeprotokoll erstellen? Danach ist es unveränderlich und die Firma wird um Bestätigung gebeten.')) { setBusy(''); laden(); return; } await api.post(`/api/abnahmen/${abnahmeId}/abschliessen`, {}); toast.success('Abnahmeprotokoll erstellt'); } else toast.success('Entwurf gespeichert');
      laden(); onChanged?.();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const antwort = async (bestaetigen) => {
    setBusy('antwort');
    try { await api.post(`/api/abnahmen/${abnahmeId}/antwort`, { bestaetigen, kommentar }); toast.success(bestaetigen ? 'Abnahme bestätigt' : 'Widerspruch gesendet'); setKommentar(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const a = d?.abnahme;
  return (
    <Sheet open={!!abnahmeId} onOpenChange={onOpenChange} title={a ? `${a.nummer} · ${a.art_name}` : 'Abnahme'} subtitle={a ? `${a.firma_name} · ${d.projekt?.name || ''}` : ''} width="sm:max-w-2xl">
      {!a ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">{chip(a.status, a.status_name)}<span className="text-[12px] text-[#6E6E73]">angelegt von {a.erstellt_von?.name} ({a.erstellt_von?.firma_name}) am {fmtZeit(a.created_at)}</span></div>
          {a.bemerkung && a.status === 'angefordert' && <p className="text-[13px] rounded-2xl bg-[#E8F0FE] text-[#1D4ED8] px-4 py-2">Anfrage der Firma: {a.bemerkung}</p>}
          {form ? (
            <div className="space-y-3 rounded-2xl bg-[#F5F5F7] p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Art"><Select value={form.art} onChange={set('art')} className="w-full">{Object.entries(arten).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
                <Field label="Datum der Abnahme"><TextInput type="date" value={form.datum} onChange={set('datum')} /></Field>
                <Field label="Gewerk"><TextInput value={form.gewerk} onChange={set('gewerk')} /></Field>
                <Field label="Bereich / Bauabschnitt"><TextInput value={form.bereich} onChange={set('bereich')} /></Field>
                <Field label="Teilnehmer" className="sm:col-span-2"><TextInput value={form.teilnehmer} onChange={set('teilnehmer')} placeholder="Namen beider Seiten" /></Field>
                <Field label="Ergebnis"><Select value={form.ergebnis} onChange={set('ergebnis')} className="w-full">{Object.entries(ergebnisse).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
                <Field label="Nachbesserung bis"><TextInput type="date" value={form.nachbesserung_bis} onChange={set('nachbesserung_bis')} /></Field>
              </div>
              <Field label="Vorbehalte / Bemerkungen"><TextArea rows={3} value={form.vorbehalte} onChange={set('vorbehalte')} /></Field>
              <div>
                <span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Offene Mängel dieser Firma ins Protokoll aufnehmen</span>
                {d.maengel_offen.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Keine offenen Mängel.</p> : (
                  <ul className="space-y-1">{d.maengel_offen.map((m) => <li key={m.id}><label className="flex items-start gap-2 text-[13px]"><input type="checkbox" className="mt-0.5" checked={form.maengel_ids.includes(m.id)} onChange={() => toggleMangel(m.id)} /><span>{m.beschreibung}{m.bereich ? ` (${m.bereich})` : ''} · {m.status_name}{m.frist ? ` · Frist ${fmtDate(fromKey(m.frist))}` : ''}</span></label></li>)}</ul>
                )}
              </div>
              <div className="flex flex-wrap justify-end gap-2"><Btn variant="soft" onClick={() => speichern(false)} loading={busy === 'speichern'}>Entwurf speichern</Btn><Btn onClick={() => speichern(true)} loading={busy === 'abschliessen'}>Protokoll erstellen</Btn></div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 text-[13px]">
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Datum</div><div className="font-semibold">{a.datum ? fmtDate(fromKey(a.datum)) : '–'}</div></div>
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Ergebnis</div><div className="font-semibold">{a.ergebnis_name || 'offen'}</div></div>
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Gewerk / Bereich</div><div className="font-semibold">{[a.gewerk, a.bereich].filter(Boolean).join(' · ') || '–'}</div></div>
                <div className="rounded-2xl bg-[#F5F5F7] px-3 py-2"><div className="text-[11px] text-[#6E6E73]">Nachbesserung bis</div><div className="font-semibold">{a.nachbesserung_bis ? fmtDate(fromKey(a.nachbesserung_bis)) : '–'}</div></div>
              </div>
              {a.teilnehmer && <p className="text-[13px] text-[#6E6E73]">Teilnehmer: {a.teilnehmer}</p>}
              {a.vorbehalte && <p className="text-[14px] whitespace-pre-wrap rounded-2xl bg-[#F5F5F7] px-4 py-3">{a.vorbehalte}</p>}
              <div>
                <span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Festgestellte Mängel ({(a.maengel || []).length})</span>
                {(a.maengel || []).length > 0 && <ul className="text-[13px] space-y-1">{a.maengel.map((m, i) => <li key={m.id}>{i + 1}. {m.beschreibung}{m.bereich ? ` (${m.bereich})` : ''} · {m.status_name}{m.frist ? ` · Frist ${fmtDate(fromKey(m.frist))}` : ''}</li>)}</ul>}
              </div>
            </>
          )}
          {a.status === 'erstellt' && d.rolle === 'firma' && (
            <div className="rounded-2xl bg-[#FFF4E5] p-4 space-y-2">
              <div className="text-[13px] font-medium text-[#7A4100]">Stellungnahme eurer Firma – wird mit Name und Zeit protokolliert.</div>
              <TextInput value={kommentar} onChange={(e) => setKommentar(e.target.value)} placeholder="Kommentar (beim Widerspruch Pflicht)" className="h-9 text-[13px]" />
              <div className="flex gap-2"><Btn size="sm" onClick={() => antwort(true)} loading={busy === 'antwort'}>Bestätigen</Btn><Btn size="sm" variant="danger" onClick={() => antwort(false)}>Widersprechen</Btn></div>
            </div>
          )}
          {a.antwort && <p className={`text-[13px] ${a.status === 'bestaetigt' ? 'text-[#1B7F3B]' : 'text-[#C41E3A]'}`}>{a.status === 'bestaetigt' ? 'Bestätigt' : 'Widersprochen'} von {a.antwort.user_name} am {fmtZeit(a.antwort.at)}{a.antwort.kommentar ? ` – „${a.antwort.kommentar}“` : ''}.</p>}
          <div className="flex flex-wrap gap-2"><Btn size="sm" variant="soft" onClick={() => openFile(`/api/abnahmen/${abnahmeId}/pdf`).catch((err) => toast.error(err.message))}><FileText size={14} /> Abnahmeprotokoll (PDF)</Btn></div>
          {(a.verlauf || []).length > 0 && <ul className="text-[12px] text-[#6E6E73] space-y-0.5">{a.verlauf.slice().reverse().map((v, i) => <li key={i}>{fmtZeit(v.at)} · {v.status} · {v.user_name} ({v.firma_name}){v.kommentar ? ` · „${v.kommentar}“` : ''}</li>)}</ul>}
        </div>
      )}
    </Sheet>
  );
}
