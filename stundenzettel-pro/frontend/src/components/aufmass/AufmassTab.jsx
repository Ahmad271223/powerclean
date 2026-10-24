import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Check, FileDown, Plus, Ruler, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, Field, IconBtn, Select, TextArea, TextInput } from '../ui';
import { useDialoge } from '../Dialoge';
import { api, openFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { fmtMenge } from '../../lib/angebot';
import { fmtDate, fromKey, todayKey } from '../../lib/dates';

const LEER = { bezeichnung: '', raum: '', typ: 'flaeche', formel: '', einheit: '', position_nr: '', messdatum: todayKey(), note: '' };

/** Projekt → Aufmaß: Längen, Flächen, Volumen, Stückzahlen mit Formel (kein eval), Positionsbezug, Fotos, Prüfung durch das Büro,
 *  Übernahme geprüfter Mengen in Angebot oder Auftrag, Aufmaßblatt als PDF. */
export default function AufmassTab({ projekt }) {
  const { user, isBuero, kann } = useAuth();
  const { bestaetigen } = useDialoge();
  const datei = useRef(null);
  const [d, setD] = useState(null);
  const [f, setF] = useState(LEER);
  const [vorschau, setVorschau] = useState({ menge: null, fehler: '' });
  const [busy, setBusy] = useState('');
  const [fotoFuer, setFotoFuer] = useState(null);
  const laden = useCallback(() => api.get(`/api/projekte/${projekt.id}/aufmasse`).then(setD).catch((err) => toast.error(err.message)), [projekt.id]);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    if (!f.formel.trim()) { setVorschau({ menge: null, fehler: '' }); return; }
    const t = setTimeout(() => api.post('/api/aufmass/formel', { formel: f.formel }).then((r) => setVorschau({ menge: r.menge, fehler: '' })).catch((err) => setVorschau({ menge: null, fehler: err.message })), 250);
    return () => clearTimeout(t);
  }, [f.formel]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const typGewaehlt = (e) => { const typ = e.target.value; setF((x) => ({ ...x, typ, einheit: d?.typen?.[typ]?.einheit || x.einheit })); };
  const positionGewaehlt = (e) => { const nr = e.target.value; const p = (d?.positionen || []).find((x) => x.nr === nr); setF((x) => ({ ...x, position_nr: nr, bezeichnung: x.bezeichnung || (p ? p.text : '') })); };
  const anlegen = async () => {
    if (!f.bezeichnung.trim() || !f.formel.trim()) { toast.error('Bezeichnung und Formel angeben'); return; }
    setBusy('anlegen');
    try { await api.post(`/api/projekte/${projekt.id}/aufmasse`, { ...f, position_nr: f.position_nr || '' }); toast.success('Aufmaß erfasst'); setF((x) => ({ ...LEER, typ: x.typ, position_nr: x.position_nr, einheit: x.einheit, messdatum: x.messdatum })); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const pruefen = async (a) => { setBusy(a.id); try { await api.post(`/api/aufmasse/${a.id}/pruefen`); toast.success('Aufmaß geprüft'); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const loeschen = async (a) => { if (!(await bestaetigen({ titel: 'Aufmaß löschen?', text: `${a.bezeichnung}: ${fmtMenge(a.menge)} ${a.einheit}`, gefaehrlich: true }))) return; try { await api.del(`/api/aufmasse/${a.id}`); laden(); } catch (err) { toast.error(err.message); } };
  const foto = async () => {
    const file = datei.current?.files?.[0];
    if (!file || !fotoFuer) return;
    setBusy('foto');
    try { const fd = new FormData(); fd.append('datei', file); await api.upload(`/api/aufmasse/${fotoFuer}/fotos`, fd); toast.success('Foto gespeichert'); setFotoFuer(null); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const uebernehmen = async (ziel) => {
    const text = ziel === 'angebot' ? 'Geprüfte Mengen je Position in den Angebotsentwurf dieses Projekts übernehmen?' : `Geprüfte Mengen in die Auftragspositionen übernehmen? ${d.abrechnungsart === 'pauschal' ? 'Achtung: Pauschalauftrag – der Auftragswert wird aus Mengen × Einheitspreisen neu gerechnet.' : 'Der Auftragswert folgt den Mengen.'}`;
    if (!(await bestaetigen({ titel: 'Mengen übernehmen', text }))) return;
    setBusy(ziel);
    try { const r = await api.post(`/api/projekte/${projekt.id}/aufmasse/uebernehmen`, { ziel, erzwingen: ziel === 'auftrag' && d.abrechnungsart === 'pauschal' }); toast.success(`${r.uebernommen} Position${r.uebernommen === 1 ? '' : 'en'} aktualisiert`); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const liste = d?.aufmasse || [];
  const typen = d?.typen || {};
  return (
    <div className="space-y-5">
      <Card className="p-5">
        <h2 className="text-[17px] mb-1 flex items-center gap-2"><Ruler size={17} /> Aufmaß erfassen</h2>
        <p className="text-[13px] text-[#6E6E73] mb-3">Formel eingeben wie auf dem Aufmaßblatt: „3,20 x 2,60; 1,10 x 2,60“ (Teilmengen mit ; getrennt werden addiert), Klammern und + − × / sind erlaubt.</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Field label="Typ"><Select value={f.typ} onChange={typGewaehlt}>{Object.entries(typen).map(([k, v]) => <option key={k} value={k}>{v.name}{v.einheit ? ` (${v.einheit})` : ''}</option>)}</Select></Field>
          <Field label="Position (optional)"><Select value={f.position_nr} onChange={positionGewaehlt}><option value="">Ohne Positionsbezug</option>{(d?.positionen || []).map((p) => <option key={p.nr} value={p.nr}>{p.nr} · {p.text}{p.einheit ? ` (${p.einheit})` : ''}</option>)}</Select></Field>
          <Field label="Bezeichnung" className="col-span-2"><TextInput value={f.bezeichnung} onChange={set('bezeichnung')} placeholder="z. B. Glasfläche Schalterhalle" /></Field>
          <Field label="Raum / Bauteil"><TextInput value={f.raum} onChange={set('raum')} placeholder="z. B. EG Flur" /></Field>
          <Field label="Formel" className="col-span-2"><TextInput value={f.formel} onChange={set('formel')} placeholder={typen[f.typ]?.vorlage || 'Länge x Höhe'} className={vorschau.fehler ? 'ring-2 ring-[#C41E3A]/40' : ''} /></Field>
          <Field label="Ergebnis"><div className={`h-11 flex items-center px-3 rounded-2xl bg-[#F5F5F7] font-semibold ${vorschau.fehler ? 'text-[#C41E3A] text-[12px] font-normal' : ''}`}>{vorschau.fehler || (vorschau.menge !== null ? `${fmtMenge(vorschau.menge)} ${f.einheit || typen[f.typ]?.einheit || ''}` : '–')}</div></Field>
          <Field label="Einheit"><TextInput value={f.einheit} onChange={set('einheit')} placeholder={typen[f.typ]?.einheit || 'Stk.'} /></Field>
          <Field label="Messdatum"><TextInput type="date" value={f.messdatum} onChange={set('messdatum')} /></Field>
          <Field label="Notiz" className="col-span-2"><TextArea rows={1} value={f.note} onChange={set('note')} placeholder="z. B. ohne Türen" /></Field>
        </div>
        <div className="flex justify-end mt-3"><Btn onClick={anlegen} loading={busy === 'anlegen'} disabled={!!vorschau.fehler}><Plus size={16} /> Aufmaß speichern</Btn></div>
      </Card>
      {d?.summen?.length > 0 && (
        <Card className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h2 className="text-[17px]">Summen je Position</h2>
            <div className="flex flex-wrap gap-2">
              <Btn size="sm" variant="soft" onClick={() => openFile(`/api/projekte/${projekt.id}/aufmass.pdf`).catch((e) => toast.error(e.message))}><FileDown size={14} /> Aufmaßblatt</Btn>
              {isBuero && kann('angebote') && (d.positionen?.[0]?.quelle === 'angebot' ? <Btn size="sm" onClick={() => uebernehmen('angebot')} loading={busy === 'angebot'}><Check size={14} /> In Angebot übernehmen</Btn> : d.positionen?.length > 0 && <Btn size="sm" onClick={() => uebernehmen('auftrag')} loading={busy === 'auftrag'}><Check size={14} /> In Auftrag übernehmen</Btn>)}
            </div>
          </div>
          <table className="w-full text-[13px]"><thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="py-1 pr-2">Pos.</th><th className="py-1 pr-2">Position</th><th className="py-1 pr-2 text-right">Aufmaße</th><th className="py-1 pr-2 text-right">Gesamt</th><th className="py-1 text-right">Geprüft</th></tr></thead>
            <tbody>{d.summen.map((s) => <tr key={s.nr} className="border-t border-black/[0.06]"><td className="py-1 pr-2">{s.nr}</td><td className="py-1 pr-2">{s.text}</td><td className="py-1 pr-2 text-right">{s.anzahl}</td><td className="py-1 pr-2 text-right">{fmtMenge(s.gesamt)} {s.einheit}</td><td className={`py-1 text-right font-semibold ${s.geprueft < s.gesamt ? 'text-[#B25E00]' : 'text-[#1B7F3B]'}`}>{fmtMenge(s.geprueft)} {s.einheit}</td></tr>)}</tbody></table>
          <p className="text-[11px] text-[#86868B] mt-2">Nur geprüfte Mengen werden übernommen. Pauschalaufträge ändern ihren Preis nur ausdrücklich.</p>
        </Card>
      )}
      <Card className="p-5">
        <h2 className="text-[17px] mb-2">Aufmaße</h2>
        {!d ? <p className="text-[14px] text-[#6E6E73]">Lädt …</p> : liste.length === 0 ? <Empty icon={Ruler} title="Noch kein Aufmaß" text="Erfasse Längen, Flächen oder Stückzahlen mit Formel – das Büro prüft und übernimmt die Mengen." /> : (
          <ul className="divide-y divide-black/[0.06]">
            {liste.map((a) => (
              <li key={a.id} className="py-2.5 flex flex-wrap items-center gap-3 text-[14px]">
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{a.position?.nr ? <span className="text-[#6E6E73]">{a.position.nr} · </span> : null}{a.bezeichnung}{a.raum ? <span className="text-[#6E6E73] font-normal"> · {a.raum}</span> : null}</div>
                  <div className="text-[12px] text-[#6E6E73] truncate">{a.messdatum ? fmtDate(fromKey(a.messdatum)) : ''} · {a.formel}{a.user_name ? ` · ${a.user_name}` : ''}{a.note ? ` · ${a.note}` : ''}{a.fotos?.length ? ` · ${a.fotos.length} Foto${a.fotos.length === 1 ? '' : 's'}` : ''}{a.status === 'geprueft' ? ` · geprüft von ${a.geprueft_von}` : ''}</div>
                </div>
                <div className="font-semibold">{fmtMenge(a.menge)} {a.einheit}</div>
                <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${a.status === 'geprueft' ? 'bg-[#E8F8EC] text-[#1B7F3B]' : 'bg-[#FFF4E5] text-[#B25E00]'}`}>{a.status_name}</span>
                {a.fotos?.map((fo) => <IconBtn key={fo.id} size={30} variant="soft" onClick={() => openFile(`/api/dokumente/${fo.id}/datei`).catch((e) => toast.error(e.message))} title={fo.filename}><Camera size={14} /></IconBtn>)}
                {(isBuero || (a.user_id === user?.id && a.status !== 'geprueft')) && <IconBtn size={30} variant="soft" onClick={() => setFotoFuer(fotoFuer === a.id ? null : a.id)} title="Foto hinzufügen"><Upload size={14} /></IconBtn>}
                {isBuero && a.status !== 'geprueft' && <Btn size="sm" variant="soft" onClick={() => pruefen(a)} loading={busy === a.id}><Check size={14} /> Prüfen</Btn>}
                {(isBuero || (a.user_id === user?.id && a.status !== 'geprueft')) && <IconBtn size={30} onClick={() => loeschen(a)} className="text-[#C41E3A]" title="Löschen"><Trash2 size={14} /></IconBtn>}
                {fotoFuer === a.id && <div className="w-full flex items-center gap-2 pl-2"><input ref={datei} type="file" accept="image/*,application/pdf" capture="environment" className="text-[13px]" /><Btn size="sm" onClick={foto} loading={busy === 'foto'}>Hochladen</Btn></div>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
