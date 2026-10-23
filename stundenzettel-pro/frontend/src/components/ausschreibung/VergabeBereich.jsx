import React, { useRef, useState } from 'react';
import { BadgeCheck, FileSignature, FileText, Paperclip, Send, Undo2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Btn, Card, Field, Select, TextArea, TextInput, Toggle } from '../ui';
import { useDialoge } from '../Dialoge';
import { api, openFile } from '../../lib/api';
import { VERGABE_CLS, VERGABE_NAMEN, fmtGeld, fmtZeit } from '../../lib/ausschreibung';

const chip = (st) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${VERGABE_CLS[st] || ''}`}>{VERGABE_NAMEN[st] || st}</span>;
const SCHRITTE = ['vorgeschlagen', 'freigegeben', 'mitgeteilt', 'angenommen'];

/** Mehrstufige Vergabe: Vorschlag → interne Freigabe (zweite Person) → Mitteilung mit Vertragsunterlagen → verbindliche Annahme durch den Inhaber der Firma. */
export default function VergabeBereich({ ausschreibung: a, rolle, onChanged, kategorien = [] }) {
  const { fragen } = useDialoge();
  const v = a.vergabe;
  const [busy, setBusy] = useState('');
  const [nachricht, setNachricht] = useState('');
  const [kat, setKat] = useState('Auftragsschreiben');
  const [annahme, setAnnahme] = useState({ name: '', text: '', gelesen: false });
  const [grund, setGrund] = useState('');
  const eingabe = useRef(null);
  if (!v) return null;
  const aktion = async (pfad, body, erfolg) => { setBusy(pfad); try { const r = await api.post(pfad, body); toast.success(erfolg); onChanged?.(r); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const upload = async (file) => { if (!file) return; setBusy('upload'); try { const fd = new FormData(); fd.append('datei', file); fd.append('kategorie', kat); await api.upload(`/api/vergaben/${v.id}/dokumente`, fd); toast.success('Dokument bereitgestellt'); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const stufe = SCHRITTE.indexOf(v.status);
  const dokumente = v.dokumente || [];
  return (
    <div className="space-y-4">
      <Card className="p-5 space-y-4">
        <div className="flex flex-wrap items-center gap-3"><span className="font-semibold text-[16px] flex items-center gap-2"><FileSignature size={17} /> Vergabe an {v.firma_name}</span>{chip(v.status)}<span className="ml-auto text-[15px] font-semibold">{fmtGeld(v.summe_netto)} netto</span></div>
        <ol className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[12px]">
          {SCHRITTE.map((s, i) => <li key={s} className={`rounded-xl px-3 py-2 ${i <= stufe && stufe >= 0 ? 'bg-[#E8F8EC] text-[#1B7F3B]' : 'bg-black/[0.04] text-[#86868B]'}`}><span className="block font-semibold">{i + 1}. {VERGABE_NAMEN[s].split(' – ')[0]}</span>{s === 'vorgeschlagen' && v.vorgeschlagen_von && <span>{v.vorgeschlagen_von.name}</span>}{s === 'freigegeben' && v.freigegeben_von && <span>{v.freigegeben_von.name}</span>}{s === 'mitgeteilt' && v.mitgeteilt_at && <span>{fmtZeit(v.mitgeteilt_at)}</span>}{s === 'angenommen' && v.bestaetigung && <span>{v.bestaetigung.name}</span>}</li>)}
        </ol>
        {v.begruendung && rolle === 'leitung' && <p className="text-[13px] text-[#6E6E73]">Begründung: {v.begruendung}</p>}
        {v.nachricht && <p className="text-[13px] whitespace-pre-wrap rounded-2xl bg-[#F5F5F7] px-4 py-3">{v.nachricht}</p>}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2"><span className="text-[13px] font-medium text-[#6E6E73] flex items-center gap-1.5"><Paperclip size={14} /> Vertrags- und Auftragsdokumente ({dokumente.length})</span>
            {rolle === 'leitung' && ['vorgeschlagen', 'freigegeben', 'mitgeteilt'].includes(v.status) && <div className="flex gap-2"><Select value={kat} onChange={(e) => setKat(e.target.value)}>{(kategorien.length ? kategorien : ['Auftragsschreiben', 'Vertrag', 'Sonstiges']).map((k) => <option key={k} value={k}>{k}</option>)}</Select><input ref={eingabe} type="file" className="hidden" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ''; }} /><Btn size="sm" variant="dark" onClick={() => eingabe.current?.click()} loading={busy === 'upload'}><Paperclip size={14} /> Hochladen</Btn></div>}</div>
          {dokumente.length > 0 ? <ul className="divide-y divide-black/[0.06] text-[13px]">{dokumente.map((d) => <li key={d.id} className="py-2 flex items-center gap-2"><FileText size={14} className="text-[#6E6E73]" /><button type="button" className="flex-1 text-left truncate" onClick={() => openFile(`/api/dokumente/${d.id}/datei`).catch((err) => toast.error(err.message))}>{d.filename}</button><span className="text-[12px] text-[#86868B]">{d.category}</span></li>)}</ul> : <p className="text-[12px] text-[#86868B]">Noch keine Dokumente.</p>}
        </div>
        {rolle === 'leitung' && v.status === 'vorgeschlagen' && (
          <div className="rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[13px] space-y-2"><p>Interne Freigabe durch Büro oder Inhaber. Sobald es eine zweite freigabeberechtigte Person gibt, muss sie die Freigabe erteilen (Vier-Augen-Prinzip).</p><Btn size="sm" onClick={() => aktion(`/api/vergaben/${v.id}/freigabe`, {}, 'Vergabe freigegeben')} loading={busy === `/api/vergaben/${v.id}/freigabe`}><BadgeCheck size={14} /> Freigeben</Btn></div>
        )}
        {rolle === 'leitung' && v.status === 'freigegeben' && (
          <div className="rounded-2xl bg-[#E8F0FE] px-4 py-3 text-[13px] space-y-2"><p>Vertrags- oder Auftragsdokumente hochladen und der Firma die Vergabe mitteilen. Die Firma bestätigt danach die Annahme ausdrücklich.</p><Field label="Nachricht an die Firma"><TextArea rows={2} value={nachricht} onChange={(e) => setNachricht(e.target.value)} /></Field><Btn size="sm" onClick={() => aktion(`/api/vergaben/${v.id}/mitteilen`, { nachricht }, 'Vergabemitteilung gesendet')} loading={busy === `/api/vergaben/${v.id}/mitteilen`}><Send size={14} /> Vergabe mitteilen</Btn></div>
        )}
        {rolle === 'leitung' && ['vorgeschlagen', 'freigegeben', 'mitgeteilt'].includes(v.status) && <div className="flex justify-end"><Btn size="sm" variant="ghost" onClick={async () => { const g = await fragen({ titel: 'Vergabe zurückziehen', text: 'Die Firma wird benachrichtigt; die Ausschreibung geht zurück in die Vergabe.', feld: 'Grund', pflicht: true, ok: 'Zurückziehen', gefaehrlich: true }); if (g !== null) aktion(`/api/vergaben/${v.id}/zurueckziehen`, { nachricht: g }, 'Vergabe zurückgezogen'); }}><Undo2 size={14} /> Zurückziehen</Btn></div>}
        {rolle === 'bieter' && v.status === 'mitgeteilt' && (
          <div className="rounded-2xl border-2 border-[#1B7F3B]/40 bg-[#E8F8EC]/50 px-4 py-4 space-y-3">
            <p className="text-[14px] font-semibold">Verbindliche Auftragsannahme</p>
            <p className="text-[13px] text-[#1D1D1F]">Mit der Annahme wird eure Firma dem Projekt als beauftragter Subunternehmer zugeordnet. Das darf nur der Inhaber erklären. Bitte zuerst die bereitgestellten Dokumente prüfen.</p>
            <div className="rounded-2xl bg-white px-4"><Toggle checked={annahme.gelesen} onChange={(x) => setAnnahme((s) => ({ ...s, gelesen: x }))} label="Ich habe die Vertrags-/Auftragsdokumente geprüft" /></div>
            <Field label="Name der annehmenden Person"><TextInput value={annahme.name} onChange={(e) => setAnnahme((s) => ({ ...s, name: e.target.value }))} /></Field>
            <Field label={`Bestätigung – bitte genau eintippen: „${v.annahme_text}“`}><TextInput value={annahme.text} onChange={(e) => setAnnahme((s) => ({ ...s, text: e.target.value }))} placeholder={v.annahme_text} /></Field>
            <div className="flex flex-wrap gap-2"><Btn onClick={() => aktion(`/api/vergaben/${v.id}/antwort`, { annehmen: true, bestaetigung: annahme.text, name: annahme.name }, 'Auftrag verbindlich angenommen – das Projekt ist jetzt in euren Projekten')} disabled={!annahme.gelesen || !annahme.name.trim() || annahme.text.trim() !== v.annahme_text} loading={busy === `/api/vergaben/${v.id}/antwort`}><BadgeCheck size={15} /> Auftrag verbindlich annehmen</Btn></div>
            <details><summary className="text-[13px] cursor-pointer text-[#6E6E73]">Vergabe ablehnen</summary><div className="mt-2 space-y-2"><TextArea rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} placeholder="Grund (optional)" /><Btn size="sm" variant="danger" onClick={() => { if (window.confirm('Vergabe wirklich ablehnen?')) aktion(`/api/vergaben/${v.id}/antwort`, { annehmen: false, grund }, 'Vergabe abgelehnt'); }}>Ablehnen</Btn></div></details>
          </div>
        )}
        {v.status === 'angenommen' && v.lokales_project_id && rolle === 'bieter' && <Link to={`/projekte/${v.lokales_project_id}`} className="inline-flex items-center gap-2 text-[14px] font-semibold text-[#1B7F3B]"><BadgeCheck size={16} /> Zum Projekt (Mitarbeiter zuordnen, Aufgaben, Zeiten)</Link>}
        {v.status === 'angenommen' && rolle === 'leitung' && <Link to={`/projekte/${a.project_id}`} className="inline-flex items-center gap-2 text-[14px] font-semibold text-[#1B7F3B]"><BadgeCheck size={16} /> Firma ist beteiligt – zum Projekt (Aufgaben planen)</Link>}
      </Card>
      {(v.verlauf || []).length > 0 && <Card className="p-4"><span className="block text-[13px] font-medium text-[#6E6E73] mb-1">Vergabehistorie</span><ul className="text-[12px] text-[#6E6E73] space-y-0.5">{v.verlauf.slice().reverse().map((s, i) => <li key={i}>{fmtZeit(s.at)} · {VERGABE_NAMEN[s.status] || s.status} · {s.user_name}{s.text ? ` · ${s.text}` : ''}</li>)}</ul></Card>}
    </div>
  );
}
