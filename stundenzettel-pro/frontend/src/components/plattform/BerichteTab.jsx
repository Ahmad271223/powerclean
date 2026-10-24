import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, FileText, PenLine, Plus, Save, Trash2, Wand2, X } from 'lucide-react';
import { toast } from 'sonner';
import Bild from '../Bild';
import SignaturePad from '../SignaturePad';
import { useDialoge } from '../Dialoge';
import { Btn, Card, Empty, Field, IconBtn, Select, Sheet, TextArea, TextInput } from '../ui';
import { api, download, openFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { fmtDate, fromKey, todayKey } from '../../lib/dates';

const CLS = { entwurf: 'bg-black/[0.06] text-[#6E6E73]', eingereicht: 'bg-[#EEE8FD] text-[#6D28D9]', freigegeben: 'bg-[#1B7F3B] text-white' };
const chip = (st, name) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${CLS[st] || ''}`}>{name || st}</span>;
const LEER = { datum: todayKey(), art: 'tagesbericht', vorlage_id: '', bereich: '', wetter: '', firmen: [], mitarbeiter_anzahl: 0, taetigkeiten: '', fortschritt: '', lieferungen: '', behinderungen: '', maengel: '', besondere_vorkommnisse: '', notizen: '',
  auftraggeber_name: '', regie_stunden: [], regie_material: [], regie_geraete: [] };
const FELDER = [['taetigkeiten', 'Tätigkeiten', 4], ['fortschritt', 'Fortschritt', 2], ['lieferungen', 'Lieferungen', 2], ['behinderungen', 'Behinderungen', 2], ['maengel', 'Mängel', 2], ['besondere_vorkommnisse', 'Besondere Vorkommnisse', 2], ['notizen', 'Notizen', 2]];
const VORLAGE_FELDER = ['bereich', 'wetter', 'firmen', 'mitarbeiter_anzahl', 'taetigkeiten', 'fortschritt', 'lieferungen', 'behinderungen', 'maengel', 'besondere_vorkommnisse', 'notizen', 'auftraggeber_name', 'regie_stunden', 'regie_material', 'regie_geraete'];
const AKTION = { entwurf: 'Zurück zum Entwurf', eingereicht: 'Zur Freigabe einreichen', freigegeben: 'Freigeben' };
const REGIE = [
  ['regie_stunden', 'Regiestunden', [['name', 'Mitarbeiter', 'text'], ['taetigkeit', 'Tätigkeit', 'text'], ['stunden', 'Std.', 'number']], { name: '', taetigkeit: '', stunden: '' }],
  ['regie_material', 'Material', [['bezeichnung', 'Material', 'text'], ['menge', 'Menge', 'number'], ['einheit', 'Einheit', 'text']], { bezeichnung: '', menge: '', einheit: 'Stück' }],
  ['regie_geraete', 'Geräte', [['bezeichnung', 'Gerät', 'text'], ['stunden', 'Std.', 'number']], { bezeichnung: '', stunden: '' }],
];
const zahl = (v) => (v === '' || v === null || v === undefined ? 0 : parseFloat(String(v).replace(',', '.')) || 0);
const regieBereinigen = (liste) => (liste || []).filter((z) => Object.values(z).some((v) => v !== '' && v !== null)).map((z) => Object.fromEntries(Object.entries(z).map(([k, v]) => [k, ['stunden', 'menge'].includes(k) ? zahl(v) : v])));

/** Bautages- und Regieberichte: Entwurf (mit Vorbelegung aus Aufgaben, Lieferungen, Auftrag und Material des Tages, optional aus Vorlage) → einreichen → Freigabe,
 *  Regieberichte zusätzlich mit Stunden/Material/Geräten und Kundenunterschrift auf dem Gerät, PDF. */
export default function BerichteTab({ projectId }) {
  const { isBuero, feature } = useAuth();
  const { fragen } = useDialoge();
  const [daten, setDaten] = useState(null);
  const [vorlagen, setVorlagen] = useState([]);
  const [form, setForm] = useState(null);
  const [vorschlag, setVorschlag] = useState(null);
  const [offen, setOffen] = useState(null);
  const [busy, setBusy] = useState('');
  const vorlagenAktiv = feature('berichtsvorlagen');
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/tagesberichte`).then(setDaten).catch((err) => toast.error(err.message)), [projectId]);
  const vorlagenLaden = useCallback(() => { if (vorlagenAktiv) api.get('/api/berichtsvorlagen').then((r) => setVorlagen(r.vorlagen)).catch(() => setVorlagen([])); }, [vorlagenAktiv]);
  useEffect(() => { laden(); vorlagenLaden(); }, [laden, vorlagenLaden]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const vorlageAnwenden = (id) => {
    const v = vorlagen.find((x) => x.id === id);
    setForm((f) => ({ ...f, vorlage_id: id, ...(v ? { art: v.art, ...v.felder } : {}) }));
    if (v) toast.success(`Vorlage „${v.name}“ übernommen`);
  };
  const vorbelegen = async () => {
    setBusy('vorschlag');
    try {
      const v = await api.get(`/api/projekte/${projectId}/tagesbericht-vorschlag?datum=${form.datum}`);
      setVorschlag(v);
      setForm((f) => ({ ...f, firmen: v.firmen, taetigkeiten: f.taetigkeiten || v.taetigkeiten, lieferungen: f.lieferungen || v.lieferungen, mitarbeiter_anzahl: f.mitarbeiter_anzahl || v.mitarbeiter_anzahl, maengel: f.maengel || (v.maengel_offen ? `${v.maengel_offen} offene Mängel` : '') }));
      toast.success('Aus Aufgaben, Lieferungen und Anwesenheit des Tages vorbelegt');
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const alsVorlage = async () => {
    const name = await fragen({ titel: 'Als Vorlage speichern', text: 'Felder, Regiezeilen und Art des Berichts werden als Vorlage für die ganze Firma gespeichert (ohne Datum).', feld: 'Name der Vorlage', pflicht: true, ok: 'Speichern' });
    if (!name) return;
    const felder = Object.fromEntries(VORLAGE_FELDER.map((k) => [k, ['regie_stunden', 'regie_material', 'regie_geraete'].includes(k) ? regieBereinigen(form[k]) : k === 'mitarbeiter_anzahl' ? parseInt(form[k], 10) || 0 : k === 'firmen' ? (Array.isArray(form.firmen) ? form.firmen : String(form.firmen).split(',').map((x) => x.trim()).filter(Boolean)) : form[k]]));
    try { await api.post('/api/berichtsvorlagen', { name, art: form.art, felder }); toast.success('Vorlage gespeichert'); vorlagenLaden(); } catch (err) { toast.error(err.message); }
  };
  const vorlageLoeschen = async (v) => { if (!window.confirm(`Vorlage „${v.name}“ löschen?`)) return; try { await api.del(`/api/berichtsvorlagen/${v.id}`); vorlagenLaden(); } catch (err) { toast.error(err.message); } };
  const speichern = async (e) => {
    e.preventDefault();
    const body = { ...form, vorlage_id: form.vorlage_id || null, mitarbeiter_anzahl: parseInt(form.mitarbeiter_anzahl, 10) || 0, firmen: Array.isArray(form.firmen) ? form.firmen : String(form.firmen).split(',').map((x) => x.trim()).filter(Boolean),
      regie_stunden: regieBereinigen(form.regie_stunden), regie_material: regieBereinigen(form.regie_material), regie_geraete: regieBereinigen(form.regie_geraete) };
    setBusy('speichern');
    try { if (form.id) { const { id, ...rest } = body; await api.put(`/api/tagesberichte/${id}`, rest); } else await api.post(`/api/projekte/${projectId}/tagesberichte`, body); toast.success('Bericht gespeichert'); setForm(null); setVorschlag(null); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const regie = form?.art === 'regiebericht';
  const zeile = (k, i, feld, wert) => setForm((f) => ({ ...f, [k]: f[k].map((z, j) => (j === i ? { ...z, [feld]: wert } : z)) }));
  if (!daten) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] text-[#6E6E73]">Bautages- und Regieberichte nach Datum. Entwurf → Einreichen → Freigabe durch die Projektleitung. Regieberichte kann der Auftraggeber direkt auf dem Gerät unterschreiben.</p>
        {daten.schreiben && <div className="flex gap-2"><Btn variant="soft" onClick={() => setForm({ ...LEER, art: 'regiebericht' })}><Plus size={17} /> Regiebericht</Btn><Btn onClick={() => setForm({ ...LEER })}><Plus size={17} /> Tagesbericht</Btn></div>}
      </div>
      {daten.berichte.length === 0 ? <Card><Empty icon={FileText} title="Noch kein Bericht" text="Ein Bericht je Tag und Firma: Tätigkeiten, Firmen, Mitarbeiterzahl, Fortschritt, Lieferungen, Behinderungen, Mängel, Fotos – Regieberichte zusätzlich mit Stunden, Material, Geräten und Unterschrift." /></Card> : (
        <Card className="p-4"><ul className="divide-y divide-black/[0.06]">
          {daten.berichte.map((b) => (
            <li key={b.id} className="py-2.5 flex items-center gap-3">
              <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOffen(b.id)}>
                <div className="text-[15px] font-semibold">{fmtDate(fromKey(b.datum))}{b.art === 'regiebericht' && <span className="ml-2 text-[11px] font-semibold rounded-full bg-[#FFF4E5] text-[#B25E00] px-2 py-0.5">Regie</span>}{b.bereich ? <span className="font-normal text-[#6E6E73]"> · {b.bereich}</span> : null}</div>
                <div className="text-[12px] text-[#6E6E73] truncate">{[b.firma_name, b.verfasser, b.mitarbeiter_anzahl ? `${b.mitarbeiter_anzahl} Mitarbeiter` : '', b.fotos_anzahl ? `${b.fotos_anzahl} Fotos` : '', b.unterschrieben ? `unterschrieben (${b.unterschrift?.signer_name})` : ''].filter(Boolean).join(' · ')}</div>
              </button>
              {chip(b.status, b.status_name)}
              <IconBtn size={30} variant="soft" onClick={() => download(`/api/tagesberichte/${b.id}/pdf`).catch((err) => toast.error(err.message))} title="PDF"><FileText size={14} /></IconBtn>
            </li>
          ))}
        </ul></Card>
      )}
      <Sheet open={!!form} onOpenChange={(o) => { if (!o) { setForm(null); setVorschlag(null); } }} title={form?.id ? `${regie ? 'Regiebericht' : 'Tagesbericht'} bearbeiten` : regie ? 'Neuer Regiebericht' : 'Neuer Tagesbericht'} subtitle="„Vorbelegen“ holt Aufgaben, Lieferungen, Anwesenheit, Arbeitsanweisungen aus dem Auftrag und Material des Tages." width="sm:max-w-2xl">
        {form && (
          <form onSubmit={speichern} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
              <Field label="Art"><Select value={form.art} onChange={set('art')}><option value="tagesbericht">Bautagesbericht</option><option value="regiebericht">Regiebericht</option></Select></Field>
              {vorlagenAktiv && (
                <Field label="Vorlage" className="sm:col-span-2">
                  <div className="flex gap-2">
                    <Select value={form.vorlage_id || ''} onChange={(e) => vorlageAnwenden(e.target.value)} data-testid="vorlage-auswahl"><option value="">– keine Vorlage –</option>{vorlagen.map((v) => <option key={v.id} value={v.id}>{v.name} ({v.art_name})</option>)}</Select>
                    {isBuero && <Btn type="button" variant="soft" onClick={alsVorlage} title="Aktuelle Felder als Vorlage speichern"><Save size={15} /> Als Vorlage</Btn>}
                    {isBuero && form.vorlage_id && <IconBtn type="button" variant="danger" size={40} title="Vorlage löschen" onClick={() => vorlageLoeschen(vorlagen.find((v) => v.id === form.vorlage_id))}><Trash2 size={14} /></IconBtn>}
                  </div>
                </Field>
              )}
              <Field label="Datum"><TextInput type="date" value={form.datum} onChange={set('datum')} required /></Field>
              <Field label="Bauabschnitt"><TextInput value={form.bereich} onChange={set('bereich')} /></Field>
              <Btn type="button" variant="soft" onClick={vorbelegen} loading={busy === 'vorschlag'}><Wand2 size={15} /> Vorbelegen</Btn>
              <Field label="Wetter"><TextInput value={form.wetter} onChange={set('wetter')} placeholder="z. B. trocken, 12 °C" /></Field>
              <Field label="Beteiligte Firmen" className="sm:col-span-2"><TextInput value={Array.isArray(form.firmen) ? form.firmen.join(', ') : form.firmen} onChange={(e) => { const v = e.target.value; setForm((f) => ({ ...f, firmen: v })); }} placeholder="durch Komma getrennt" /></Field>
              <Field label="Mitarbeiter vor Ort"><TextInput type="number" min="0" inputMode="numeric" value={form.mitarbeiter_anzahl} onChange={set('mitarbeiter_anzahl')} /></Field>
              {regie && <Field label="Auftraggeber / Ansprechpartner" className="sm:col-span-2"><TextInput value={form.auftraggeber_name} onChange={set('auftraggeber_name')} placeholder="wer die Regieleistung bestätigt" /></Field>}
            </div>
            {vorschlag?.arbeitsanweisungen?.length > 0 && (
              <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[13px]">
                <div className="flex items-center justify-between gap-2 mb-1"><span className="font-semibold">Arbeitsanweisungen (Auftrag und Aufgaben des Tages)</span><Btn type="button" size="sm" variant="soft" onClick={() => setForm((f) => ({ ...f, taetigkeiten: [f.taetigkeiten, ...vorschlag.arbeitsanweisungen.map((a) => `- ${a}`)].filter(Boolean).join('\n') }))}>In Tätigkeiten übernehmen</Btn></div>
                <ul className="list-disc pl-5 text-[#3A3A3C]">{vorschlag.arbeitsanweisungen.map((a, i) => <li key={i}>{a}</li>)}</ul>
              </div>
            )}
            {vorschlag?.materialliste?.length > 0 && (
              <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[13px]">
                <div className="flex items-center justify-between gap-2 mb-1"><span className="font-semibold">Material des Tages (Buchungen und Lieferungen)</span>{regie && <Btn type="button" size="sm" variant="soft" onClick={() => setForm((f) => ({ ...f, regie_material: [...regieBereinigen(f.regie_material), ...vorschlag.materialliste.map((m) => ({ bezeichnung: m.bezeichnung || '', menge: m.menge ?? '', einheit: m.einheit || '' }))] }))}>In Material übernehmen</Btn>}</div>
                <ul className="list-disc pl-5 text-[#3A3A3C]">{vorschlag.materialliste.map((m, i) => <li key={i}>{m.bezeichnung}{m.menge != null ? ` – ${m.menge} ${m.einheit || ''}` : m.einheit ? ` – ${m.einheit}` : ''}</li>)}</ul>
              </div>
            )}
            {FELDER.map(([k, l, rows]) => <Field key={k} label={l}><TextArea rows={rows} value={form[k]} onChange={set(k)} /></Field>)}
            {regie && REGIE.map(([k, titel, spalten, leer]) => (
              <div key={k}>
                <div className="flex items-center justify-between gap-2 mb-1"><span className="text-[13px] font-medium text-[#6E6E73]">{titel}</span><Btn type="button" size="sm" variant="soft" onClick={() => setForm((f) => ({ ...f, [k]: [...(f[k] || []), { ...leer }] }))}><Plus size={14} /> Zeile</Btn></div>
                {(form[k] || []).length === 0 ? <p className="text-[12px] text-[#A1A1A6]">Keine Zeilen.</p> : (form[k] || []).map((z, i) => (
                  <div key={i} className="grid gap-2 mb-1.5" style={{ gridTemplateColumns: `${spalten.map(([, , t]) => (t === 'number' ? '80px' : '1fr')).join(' ')} 36px` }}>
                    {spalten.map(([feld, label, typ]) => <TextInput key={feld} type={typ === 'number' ? 'text' : 'text'} inputMode={typ === 'number' ? 'decimal' : undefined} value={z[feld] ?? ''} onChange={(e) => zeile(k, i, feld, e.target.value)} placeholder={label} className="h-9 text-[13px]" />)}
                    <IconBtn type="button" size={36} variant="ghost" onClick={() => setForm((f) => ({ ...f, [k]: f[k].filter((_, j) => j !== i) }))} title="Zeile entfernen"><X size={14} /></IconBtn>
                  </div>
                ))}
              </div>
            ))}
            <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => setForm(null)}>Abbrechen</Btn><Btn type="submit" loading={busy === 'speichern'}>Speichern</Btn></div>
          </form>
        )}
      </Sheet>
      <BerichtDialog berichtId={offen} onOpenChange={(o) => { if (!o) setOffen(null); }} onChanged={laden} onEdit={(b) => { setOffen(null); setForm({ id: b.id, ...Object.fromEntries(Object.keys(LEER).map((k) => [k, b[k] ?? LEER[k]])) }); }} />
    </div>
  );
}

function BerichtDialog({ berichtId, onOpenChange, onChanged, onEdit }) {
  const { isBuero, firma } = useAuth();
  const { fragen } = useDialoge();
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const [unterschrift, setUnterschrift] = useState(false);
  const eingabe = useRef(null);
  const laden = useCallback(() => { if (!berichtId) { setD(null); return; } api.get(`/api/tagesberichte/${berichtId}`).then(setD).catch((err) => toast.error(err.message)); }, [berichtId]);
  useEffect(() => { laden(); }, [laden]);
  const status = async (st) => { setBusy(st); try { await api.post(`/api/tagesberichte/${berichtId}/status`, { status: st }); toast.success(AKTION[st] || st); laden(); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const fotos = async (dateien) => {
    const liste = Array.from(dateien || []).filter((f) => f.type.startsWith('image/'));
    if (!liste.length) return;
    setBusy('foto');
    try { for (const f of liste) { const fd = new FormData(); fd.append('datei', f); fd.append('note', note); await api.upload(`/api/tagesberichte/${berichtId}/fotos`, fd); } toast.success('Foto gespeichert'); setNote(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const loeschen = async () => { if (!window.confirm('Bericht löschen?')) return; try { await api.del(`/api/tagesberichte/${berichtId}`); onOpenChange(false); onChanged?.(); } catch (err) { toast.error(err.message); } };
  const unterschriftEntfernen = async () => {
    const grund = await fragen({ titel: 'Unterschrift entfernen', text: 'Der Grund wird im Verlauf und im Protokoll gespeichert.', feld: 'Grund', pflicht: true, ok: 'Entfernen', gefaehrlich: true });
    if (!grund) return;
    try { await api.del(`/api/tagesberichte/${berichtId}/unterschrift?grund=${encodeURIComponent(grund)}`); toast.success('Unterschrift entfernt'); laden(); onChanged?.(); } catch (err) { toast.error(err.message); }
  };
  const b = d?.bericht;
  const regie = b?.art === 'regiebericht';
  return (
    <Sheet open={!!berichtId} onOpenChange={onOpenChange} title={b ? `${b.art_name} ${fmtDate(fromKey(b.datum))}` : 'Bericht'} subtitle={b ? [b.firma_name, b.verfasser, b.bereich, b.wetter].filter(Boolean).join(' · ') : ''} width="sm:max-w-2xl"
      footer={b && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex gap-2">{d.bearbeiten && <Btn size="sm" variant="soft" onClick={() => onEdit?.(b)}>Bearbeiten</Btn>}{d.bearbeiten && <IconBtn size={34} variant="danger" onClick={loeschen} title="Löschen"><Trash2 size={14} /></IconBtn>}</div>
          <div className="flex flex-wrap gap-2">
            {d.unterschreiben && !b.unterschrieben && <Btn size="sm" variant="soft" onClick={() => setUnterschrift(true)}><PenLine size={14} /> Unterschrift</Btn>}
            {b.unterschrieben && isBuero && b.firma_id === firma?.id && b.status !== 'freigegeben' && <Btn size="sm" variant="ghost" onClick={unterschriftEntfernen}>Unterschrift entfernen</Btn>}
            {d.status_erlaubt.map((s) => <Btn key={s} size="sm" variant={s === 'entwurf' ? 'soft' : 'primary'} onClick={() => status(s)} loading={busy === s}>{AKTION[s]}</Btn>)}
            <Btn size="sm" variant="dark" onClick={() => download(`/api/tagesberichte/${berichtId}/pdf`).catch((err) => toast.error(err.message))}><FileText size={14} /> PDF</Btn>
          </div>
        </div>
      )}>
      {!b ? <div className="text-[14px] text-[#6E6E73]">Wird geladen …</div> : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">{chip(b.status, b.status_name)}{regie && <span className="text-[11px] font-semibold rounded-full bg-[#FFF4E5] text-[#B25E00] px-2 py-0.5">Regiebericht</span>}{b.unterschrieben && <span className="text-[11px] font-semibold rounded-full bg-[#E8F8EC] text-[#1B7F3B] px-2 py-0.5">Unterschrieben: {b.unterschrift?.signer_name}</span>}<span className="text-[12px] text-[#6E6E73]">{(b.firmen || []).join(', ')}{b.mitarbeiter_anzahl ? ` · ${b.mitarbeiter_anzahl} Mitarbeiter` : ''}</span></div>
          {b.auftraggeber_name && <div><span className="block text-[12px] font-semibold text-[#6E6E73]">Auftraggeber / Ansprechpartner</span><p className="text-[14px]">{b.auftraggeber_name}</p></div>}
          {FELDER.filter(([k]) => b[k]).map(([k, l]) => <div key={k}><span className="block text-[12px] font-semibold text-[#6E6E73]">{l}</span><p className="text-[14px] whitespace-pre-wrap">{b[k]}</p></div>)}
          {REGIE.filter(([k]) => (b[k] || []).length > 0).map(([k, titel, spalten]) => (
            <div key={k}><span className="block text-[12px] font-semibold text-[#6E6E73] mb-1">{titel}</span>
              <table className="w-full text-[13px]"><thead><tr className="text-left text-[#6E6E73]">{spalten.map(([f, l]) => <th key={f} className="py-0.5 pr-2 font-medium">{l}</th>)}</tr></thead>
                <tbody>{b[k].map((z, i) => <tr key={i} className="border-t border-black/[0.06]">{spalten.map(([f, , t]) => <td key={f} className="py-0.5 pr-2">{t === 'number' ? String(z[f] ?? '').replace('.', ',') : z[f]}</td>)}</tr>)}</tbody></table>
              {k !== 'regie_material' && <p className="text-[12px] text-[#6E6E73] mt-0.5">Summe {b[k].reduce((s, z) => s + (parseFloat(z.stunden) || 0), 0).toFixed(2).replace('.', ',')} Std.</p>}
            </div>
          ))}
          <div>
            <div className="flex items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Camera size={14} /> Fotos ({d.fotos.length})</span>{d.bearbeiten && <><input ref={eingabe} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { fotos(e.target.files); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'foto'}><Camera size={14} /> Foto</Btn></>}</div>
            {d.bearbeiten && <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz zum nächsten Foto" className="h-9 text-[13px] mb-2" />}
            {d.fotos.length > 0 && <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">{d.fotos.map((f) => <button key={f.id} type="button" className="relative rounded-xl overflow-hidden aspect-square" onClick={() => openFile(`/api/dokumente/${f.id}/datei`).catch((err) => toast.error(err.message))}><Bild id={f.id} max={300} className="w-full h-full" alt={f.note || ''} />{f.note && <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[10px] px-1.5 py-0.5 truncate text-left">{f.note}</span>}</button>)}</div>}
          </div>
          {(b.verlauf || []).some((v) => v.status?.startsWith('unterschr')) && <p className="text-[12px] text-[#86868B]">{b.verlauf.filter((v) => v.status?.startsWith('unterschr')).map((v) => `${v.status === 'unterschrieben' ? 'Unterschrieben' : 'Unterschrift entfernt'} · ${v.user_name || ''}${v.kommentar ? ` · ${v.kommentar}` : ''}`).join(' | ')}</p>}
        </div>
      )}
      <BerichtUnterschriftDialog open={unterschrift} onOpenChange={setUnterschrift} berichtId={berichtId} vorgabe={b?.auftraggeber_name || ''} onSaved={() => { laden(); onChanged?.(); }} />
    </Sheet>
  );
}

/** Auftraggeber unterschreibt den Bericht (z. B. Regiebericht) direkt auf dem Gerät – danach ist der Inhalt fest. */
function BerichtUnterschriftDialog({ open, onOpenChange, berichtId, vorgabe, onSaved }) {
  const [name, setName] = useState('');
  const [bild, setBild] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setName(vorgabe || ''); setBild(null); } }, [open, vorgabe]);
  const speichern = async () => {
    if (!name.trim()) { toast.error('Bitte den Namen des Unterzeichners eingeben'); return; }
    if (!bild) { toast.error('Bitte unterschreiben'); return; }
    setBusy(true);
    try { await api.post(`/api/tagesberichte/${berichtId}/unterschrift`, { signer_name: name.trim(), image: bild }); toast.success('Unterschrift gespeichert'); onSaved?.(); onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Unterschrift des Auftraggebers" subtitle="Bestätigt die erfassten Leistungen, Stunden und Materialien dieses Berichts. Danach lässt sich der Inhalt nicht mehr ändern.">
      <div className="space-y-4">
        <Field label="Name des Unterzeichners"><TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Herr Berger, Bauleitung" /></Field>
        {open && <SignaturePad label="Unterschrift" onChange={setBild} height={180} />}
        <div className="flex justify-end gap-2"><Btn variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={speichern} loading={busy}><PenLine size={16} /> Unterschrift speichern</Btn></div>
      </div>
    </Sheet>
  );
}
