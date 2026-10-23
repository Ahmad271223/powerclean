import React, { useEffect, useRef, useState } from 'react';
import { FileText, Paperclip, Send, Undo2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Field, Segmented, Select, TextArea, TextInput, Toggle } from '../ui';
import { useDialoge } from '../Dialoge';
import { api, download, openFile } from '../../lib/api';
import { ANGEBOT_CLS, ANGEBOT_NAMEN, fmtGeld, fmtTag, fmtZeit } from '../../lib/ausschreibung';

const LEER = { nummer: '', ansprechpartner: '', preisart: 'pauschal', preis_netto: '', stundensatz: '', stunden_geschaetzt: '', ust_satz: 19, reverse_charge: false, positionen: [], leistungsbeschreibung: '', ausfuehrung_von: '', ausfuehrung_bis: '', verfuegbarkeit: '', kapazitaet: '', material: '', zusatzleistungen: '', bemerkungen: '', gueltig_bis: '' };
const chip = (st) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${ANGEBOT_CLS[st] || ''}`}>{ANGEBOT_NAMEN[st] || st}</span>;
const num = (v) => (v === '' || v === null || v === undefined ? null : parseFloat(String(v).replace(',', '.')) || 0);

/** Bieterseite: eigenes Angebot erfassen (Pauschal, Einheitspreise je Position oder Stunden), Anhänge, einreichen, zurückziehen. */
export default function AngebotBereich({ ausschreibung: a, onChanged }) {
  const g = a.angebot;
  const [f, setF] = useState(LEER);
  const [busy, setBusy] = useState('');
  const [kat, setKat] = useState('Angebot (PDF)');
  const eingabe = useRef(null);
  const { fragen } = useDialoge();
  useEffect(() => {
    const preise = Object.fromEntries((g?.positionen || []).map((p) => [p.nr, p]));
    setF({ ...LEER, ...(g ? Object.fromEntries(Object.keys(LEER).map((k) => [k, g[k] ?? LEER[k]])) : {}), preisart: g?.preisart || (a.kaufmaennisch?.abrechnungsart === 'einheitspreise' && a.positionen?.length ? 'einheitspreise' : a.kaufmaennisch?.abrechnungsart === 'stunden' ? 'stunden' : 'pauschal'),
      preis_netto: g?.preis_netto ?? '', stundensatz: g?.stundensatz ?? '', stunden_geschaetzt: g?.stunden_geschaetzt ?? '', ausfuehrung_von: g?.ausfuehrung_von || '', ausfuehrung_bis: g?.ausfuehrung_bis || '', gueltig_bis: g?.gueltig_bis || '',
      positionen: (a.positionen || []).map((p) => ({ nr: p.nr, einzelpreis: preise[p.nr]?.einzelpreis ?? '', bemerkung: preise[p.nr]?.bemerkung || '' })) });
  }, [g, a]);
  const bearbeitbar = a.kann_bieten && (!g || ['entwurf', 'rueckfrage', 'zurueckgezogen'].includes(g.status));
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const setPreis = (nr, k, v) => setF((x) => ({ ...x, positionen: x.positionen.map((p) => (p.nr === nr ? { ...p, [k]: v } : p)) }));
  const body = () => ({ ...f, preis_netto: num(f.preis_netto), stundensatz: num(f.stundensatz), stunden_geschaetzt: num(f.stunden_geschaetzt), ust_satz: num(f.ust_satz) ?? 19,
    ausfuehrung_von: f.ausfuehrung_von || null, ausfuehrung_bis: f.ausfuehrung_bis || null, gueltig_bis: f.gueltig_bis || null,
    positionen: f.positionen.map((p) => ({ nr: p.nr, einzelpreis: num(p.einzelpreis), bemerkung: p.bemerkung || '' })).filter((p) => p.einzelpreis !== null || p.bemerkung) });
  const speichern = async () => { setBusy('speichern'); try { if (g) await api.put(`/api/angebote/${g.id}`, body()); else await api.post(`/api/ausschreibungen/${a.id}/angebot`, body()); toast.success('Angebot gespeichert (Entwurf)'); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const einreichen = async () => {
    if (!window.confirm('Angebot verbindlich einreichen? Änderungen sind danach nur nach einer Rückfrage des Auftraggebers möglich.')) return;
    setBusy('einreichen');
    try { let id = g?.id; if (!g) id = (await api.post(`/api/ausschreibungen/${a.id}/angebot`, body())).angebot.id; else await api.put(`/api/angebote/${g.id}`, body()); await api.post(`/api/angebote/${id}/einreichen`); toast.success('Angebot eingereicht'); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const zurueck = async () => {
    const grund = await fragen({ titel: 'Angebot zurückziehen', text: 'Das Angebot wird aus der Wertung genommen; danach lässt es sich überarbeiten und erneut einreichen, solange die Frist läuft.', feld: 'Grund (optional, der Auftraggeber sieht ihn)', platzhalter: 'z. B. Kapazität nicht mehr frei', ok: 'Zurückziehen', gefaehrlich: true });
    if (grund === null) return;
    setBusy('zurueck');
    try { await api.post(`/api/angebote/${g.id}/zurueckziehen`, { nachricht: grund }); toast.success('Angebot zurückgezogen'); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const upload = async (file) => { if (!file) return; setBusy('upload'); try { let id = g?.id; if (!g) id = (await api.post(`/api/ausschreibungen/${a.id}/angebot`, body())).angebot.id; const fd = new FormData(); fd.append('datei', file); fd.append('kategorie', kat); await api.upload(`/api/angebote/${id}/dokumente`, fd); toast.success('Anhang gespeichert'); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const summe = (() => {
    if (f.preisart === 'einheitspreise') { const m = Object.fromEntries((a.positionen || []).map((p) => [p.nr, p.menge])); return f.positionen.reduce((s, p) => s + (num(p.einzelpreis) || 0) * (m[p.nr] || 0), 0); }
    if (f.preisart === 'stunden') return (num(f.stundensatz) || 0) * (num(f.stunden_geschaetzt) || 0);
    return num(f.preis_netto) || 0;
  })();
  return (
    <div className="space-y-4">
      {g && (
        <Card className="p-4 flex flex-wrap items-center gap-3">
          {chip(g.status)}
          <span className="text-[13px] text-[#6E6E73]">{g.nummer} · Version {g.version}{g.eingereicht_at ? ` · eingereicht ${fmtZeit(g.eingereicht_at)}` : ''}{g.nachreichen_bis ? ` · Nachreichung bis ${fmtTag(g.nachreichen_bis)}` : ''}</span>
          <span className="ml-auto text-[15px] font-semibold">{fmtGeld(g.summe_netto)} netto</span>
          {['eingereicht', 'in_pruefung', 'rueckfrage', 'ueberarbeitet'].includes(g.status) && <Btn size="sm" variant="soft" onClick={zurueck} loading={busy === 'zurueck'}><Undo2 size={14} /> Zurückziehen</Btn>}
        </Card>
      )}
      {g && !bearbeitbar && ['eingereicht', 'in_pruefung', 'ueberarbeitet'].includes(g.status) && <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[13px] text-[#6E6E73]">Das Angebot ist eingereicht und für den Auftraggeber sichtbar – die Felder sind deshalb gesperrt. Zum Ändern zuerst „Zurückziehen“, dann überarbeiten und erneut einreichen{a.kann_bieten ? '' : ' (nur solange die Angebotsfrist läuft)'}.</div>}
      {g?.status === 'rueckfrage' && <div className="rounded-2xl bg-[#FDE8E8] text-[#C41E3A] px-4 py-3 text-[13px]">Der Auftraggeber hat eine Rückfrage oder Nachforderung gestellt – siehe Benachrichtigungen. Bitte das Angebot ergänzen und erneut einreichen{g.nachreichen_bis ? ` (bis ${fmtTag(g.nachreichen_bis)})` : ''}.</div>}
      {!a.kann_bieten && !g && <div className="rounded-2xl bg-black/[0.05] px-4 py-3 text-[13px] text-[#6E6E73]">Diese Ausschreibung nimmt derzeit keine Angebote an (Frist abgelaufen oder Vergabe läuft).</div>}
      <Card className="p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Angebotsnummer"><TextInput value={f.nummer} onChange={set('nummer')} placeholder="wird sonst vergeben" disabled={!bearbeitbar} /></Field>
          <Field label="Ansprechpartner"><TextInput value={f.ansprechpartner} onChange={set('ansprechpartner')} disabled={!bearbeitbar} /></Field>
          <Field label="Angebot gültig bis"><TextInput type="date" value={f.gueltig_bis} onChange={set('gueltig_bis')} disabled={!bearbeitbar} /></Field>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Preisart</span>
          <Segmented value={f.preisart} disabled={!bearbeitbar} onChange={(v) => bearbeitbar && setF((x) => ({ ...x, preisart: v }))} options={[{ value: 'pauschal', label: 'Pauschal' }, { value: 'einheitspreise', label: 'Einheitspreise' }, { value: 'stunden', label: 'Stunden' }]} />
        </div>
        {f.preisart === 'pauschal' && <Field label="Angebotspreis (€ netto)"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={f.preis_netto} onChange={set('preis_netto')} disabled={!bearbeitbar} /></Field>}
        {f.preisart === 'stunden' && <div className="grid grid-cols-2 gap-3"><Field label="Stundensatz (€ netto)"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={f.stundensatz} onChange={set('stundensatz')} disabled={!bearbeitbar} /></Field><Field label="Geschätzte Stunden"><TextInput type="number" step="0.5" min="0" inputMode="decimal" value={f.stunden_geschaetzt} onChange={set('stunden_geschaetzt')} disabled={!bearbeitbar} /></Field></div>}
        {f.preisart === 'einheitspreise' && (
          (a.positionen || []).length === 0 ? <p className="text-[13px] text-[#C41E3A]">Diese Ausschreibung hat kein Leistungsverzeichnis – bitte Pauschal oder Stunden wählen.</p> : (
            <div className="overflow-x-auto"><table className="w-full text-[13px]">
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B]"><th className="py-1 pr-2">Nr</th><th className="py-1 pr-2">Leistung</th><th className="py-1 pr-2 text-right">Menge</th><th className="py-1 pr-2">Einzelpreis €</th><th className="py-1 text-right">Gesamt</th></tr></thead>
              <tbody>{(a.positionen || []).map((p) => { const z = f.positionen.find((x) => x.nr === p.nr) || {}; const ep = num(z.einzelpreis); return (
                <tr key={p.nr} className="border-t border-black/[0.06]"><td className="py-1.5 pr-2 font-mono">{p.nr}</td><td className="py-1.5 pr-2">{p.leistung}{p.beschreibung ? <span className="block text-[12px] text-[#6E6E73]">{p.beschreibung}</span> : null}</td><td className="py-1.5 pr-2 text-right whitespace-nowrap">{p.menge} {p.einheit}</td>
                  <td className="py-1.5 pr-2"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={z.einzelpreis ?? ''} onChange={(e) => setPreis(p.nr, 'einzelpreis', e.target.value)} className="h-9 text-[13px] w-28" disabled={!bearbeitbar} /></td>
                  <td className="py-1.5 text-right whitespace-nowrap">{ep === null ? '–' : fmtGeld(ep * (p.menge || 0))}</td></tr>); })}</tbody>
            </table></div>
          )
        )}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
          <Field label="Umsatzsteuer (%)"><TextInput type="number" step="1" min="0" max="30" inputMode="numeric" value={f.ust_satz} onChange={set('ust_satz')} disabled={!bearbeitbar || f.reverse_charge} /></Field>
          <div className="sm:col-span-2 rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={!!f.reverse_charge} onChange={(v) => bearbeitbar && setF((x) => ({ ...x, reverse_charge: v }))} label="Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)" /></div>
        </div>
        <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 flex flex-wrap items-center gap-3 text-[14px]"><span className="text-[#6E6E73]">Angebotssumme</span><span className="font-semibold text-[17px]">{fmtGeld(summe)} netto</span>{!f.reverse_charge && <span className="text-[#6E6E73]">{fmtGeld(summe * (1 + (num(f.ust_satz) ?? 19) / 100))} brutto</span>}</div>
        <Field label="Leistungsbeschreibung"><TextArea rows={4} value={f.leistungsbeschreibung} onChange={set('leistungsbeschreibung')} disabled={!bearbeitbar} /></Field>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Ausführung ab"><TextInput type="date" value={f.ausfuehrung_von} onChange={set('ausfuehrung_von')} disabled={!bearbeitbar} /></Field>
          <Field label="Ausführung bis"><TextInput type="date" value={f.ausfuehrung_bis} onChange={set('ausfuehrung_bis')} disabled={!bearbeitbar} /></Field>
          <Field label="Verfügbarkeit"><TextInput value={f.verfuegbarkeit} onChange={set('verfuegbarkeit')} placeholder="z. B. ab KW 2 verfügbar" disabled={!bearbeitbar} /></Field>
          <Field label="Mitarbeiterkapazität"><TextInput value={f.kapazitaet} onChange={set('kapazitaet')} placeholder="z. B. 6 Monteure, 1 Meister" disabled={!bearbeitbar} /></Field>
          <Field label="Materialangaben"><TextArea rows={2} value={f.material} onChange={set('material')} disabled={!bearbeitbar} /></Field>
          <Field label="Zusatzleistungen"><TextArea rows={2} value={f.zusatzleistungen} onChange={set('zusatzleistungen')} disabled={!bearbeitbar} /></Field>
        </div>
        <Field label="Bemerkungen"><TextArea rows={2} value={f.bemerkungen} onChange={set('bemerkungen')} disabled={!bearbeitbar} /></Field>
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Paperclip size={14} /> Dokumente zum Angebot ({(g?.dokumente || []).length})</span>
            {(bearbeitbar || a.frist_offen) && <div className="flex gap-2"><Select value={kat} onChange={(e) => setKat(e.target.value)}>{(a.kategorien?.angebot || ['Sonstiges']).map((k) => <option key={k} value={k}>{k}</option>)}</Select><input ref={eingabe} type="file" className="hidden" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'upload'}><Paperclip size={14} /> Hochladen</Btn></div>}</div>
          {(g?.dokumente || []).length > 0 && <ul className="divide-y divide-black/[0.06] text-[13px]">{g.dokumente.map((d) => <li key={d.id} className="py-2 flex items-center gap-2"><FileText size={14} className="text-[#6E6E73]" /><button type="button" className="flex-1 text-left truncate" onClick={() => openFile(`/api/dokumente/${d.id}/datei`).catch((err) => toast.error(err.message))}>{d.filename}</button><span className="text-[12px] text-[#86868B]">{d.category}</span></li>)}</ul>}
        </div>
        {bearbeitbar && <div className="flex flex-wrap justify-end gap-2"><Btn variant="soft" onClick={speichern} loading={busy === 'speichern'}>Als Entwurf speichern</Btn><Btn onClick={einreichen} loading={busy === 'einreichen'}><Send size={15} /> {g?.version ? 'Überarbeitet einreichen' : 'Angebot einreichen'}</Btn></div>}
        {g && <div className="flex justify-end"><Btn size="sm" variant="ghost" onClick={() => download(`/api/angebote/${g.id}/positionen.csv`).catch((err) => toast.error(err.message))}>Positionen als CSV</Btn></div>}
      </Card>
      {(g?.verlauf || []).length > 0 && <Card className="p-4"><span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Verlauf</span><ul className="text-[12px] text-[#6E6E73] space-y-0.5">{g.verlauf.slice().reverse().map((v, i) => <li key={i}>{fmtZeit(v.at)} · {ANGEBOT_NAMEN[v.aktion] || v.aktion} · {v.user_name}{v.text ? ` · ${v.text}` : ''}</li>)}</ul></Card>}
    </div>
  );
}
