import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Ban, Check, CreditCard, FileText, Paperclip, Plus, ReceiptText, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Chip, Empty, Field, IconBtn, Select, Sheet, TextArea, TextInput } from '../components/ui';
import { useDialoge } from '../components/Dialoge';
import { api, openFile } from '../lib/api';
import { fmtGeld } from '../lib/angebot';
import { fmtDate, fromKey, todayKey } from '../lib/dates';
import KiEntwurfDialog from '../components/ki/KiEntwurfDialog';

const STATUS_CLS = { erfasst: 'bg-[#FFF4E5] text-[#B25E00]', geprueft: 'bg-[#E8F0FE] text-[#1D4ED8]', bezahlt: 'bg-[#E8F8EC] text-[#1B7F3B]', storniert: 'bg-black/[0.06] text-[#6E6E73]' };
const FILTER = [['', 'Alle'], ['erfasst', 'Zu prüfen'], ['geprueft', 'Geprüft (offen)'], ['bezahlt', 'Bezahlt'], ['storniert', 'Storniert']];
const LEER = { lieferant: '', lieferant_ustid: '', rechnungsnummer: '', rechnungsdatum: todayKey(), faellig_am: '', netto: '', ust: '', brutto: '', zuordnungen: [], kostenart: 'material', notiz: '', dokument_id: null };
const rund = (x) => Math.round((Number(x) || 0) * 100) / 100;

function RechnungDialog({ open, onOpenChange, rechnung, projekte, kostenarten, onChanged }) {
  const { fragen, bestaetigen } = useDialoge();
  const datei = useRef(null);
  const [f, setF] = useState(LEER);
  const [beleg, setBeleg] = useState(null);
  const [vorschlag, setVorschlag] = useState(null);
  const [busy, setBusy] = useState('');
  useEffect(() => {
    if (!open) return;
    setVorschlag(null); setBeleg(null);
    if (rechnung) {
      setF({ ...LEER, ...rechnung, netto: rechnung.netto, ust: rechnung.ust, brutto: rechnung.brutto, faellig_am: rechnung.faellig_am || '', zuordnungen: (rechnung.zuordnungen || []).map((z) => ({ ...z })) });
      api.get(`/api/eingangsrechnungen/${rechnung.id}`).then((r) => setBeleg(r.dokument)).catch(() => {});
    } else setF({ ...LEER, rechnungsdatum: todayKey() });
  }, [open, rechnung]);
  const bearbeitbar = !rechnung || ['erfasst', 'geprueft'].includes(rechnung.status);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const setBetrag = (k) => (e) => {
    const v = e.target.value;
    setF((x) => {
      const n = { ...x, [k]: v };
      const netto = Number(n.netto) || 0; const ust = Number(n.ust) || 0;
      if (k !== 'brutto') n.brutto = rund(netto + ust);
      else if (k === 'brutto' && n.netto !== '' && n.ust === '') n.ust = rund((Number(v) || 0) - netto);
      return n;
    });
  };
  const hochladen = async () => {
    const file = datei.current?.files?.[0];
    if (!file) { toast.error('Bitte eine Datei wählen (PDF, Bild oder XML)'); return; }
    setBusy('upload');
    try {
      const fd = new FormData(); fd.append('datei', file);
      const r = await api.upload('/api/eingangsrechnungen/datei', fd);
      setBeleg(r.dokument);
      setF((x) => ({ ...x, dokument_id: r.dokument.id }));
      if (r.vorschlag) {
        const v = r.vorschlag;
        setVorschlag(v);
        setF((x) => ({ ...x, lieferant: x.lieferant || v.lieferant || '', lieferant_ustid: x.lieferant_ustid || v.lieferant_ustid || '', rechnungsnummer: x.rechnungsnummer || v.rechnungsnummer || '', rechnungsdatum: v.rechnungsdatum || x.rechnungsdatum, faellig_am: v.faellig_am || x.faellig_am,
          netto: x.netto === '' && v.netto !== null ? v.netto : x.netto, ust: x.ust === '' && v.ust !== null ? v.ust : x.ust, brutto: x.brutto === '' && v.brutto !== null ? v.brutto : x.brutto }));
        toast.success(`${v.quelle === 'zugferd' ? 'ZUGFeRD' : 'XRechnung'} gelesen – bitte die Werte prüfen`);
      } else toast.success('Beleg hochgeladen');
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const zuordnung = (i, patch) => setF((x) => ({ ...x, zuordnungen: x.zuordnungen.map((z, j) => (j === i ? { ...z, ...patch } : z)) }));
  const zugeordnet = rund(f.zuordnungen.reduce((s, z) => s + (Number(z.betrag_netto) || 0), 0));
  const rest = rund((Number(f.netto) || 0) - zugeordnet);
  const speichern = async () => {
    if (!f.lieferant.trim() || !f.rechnungsnummer.trim() || !f.rechnungsdatum) { toast.error('Lieferant, Rechnungsnummer und Datum angeben'); return; }
    setBusy('speichern');
    try {
      const daten = { ...f, netto: Number(f.netto) || 0, ust: Number(f.ust) || 0, brutto: f.brutto === '' ? null : Number(f.brutto), faellig_am: f.faellig_am || null,
        zuordnungen: f.zuordnungen.filter((z) => z.project_id).map((z) => ({ project_id: z.project_id, betrag_netto: Number(z.betrag_netto) || 0, kostenart: z.kostenart || 'material' })) };
      let r;
      try { r = rechnung ? await api.put(`/api/eingangsrechnungen/${rechnung.id}`, daten) : await api.post('/api/eingangsrechnungen', daten); } catch (err) {
        if (err.status === 409 && (await bestaetigen({ titel: 'Mögliche Dublette', text: err.message + ' Trotzdem speichern?' }))) r = rechnung ? await api.put(`/api/eingangsrechnungen/${rechnung.id}`, { ...daten, erzwingen: true }) : await api.post('/api/eingangsrechnungen', { ...daten, erzwingen: true });
        else throw err;
      }
      toast.success(rechnung ? 'Eingangsrechnung gespeichert' : 'Eingangsrechnung erfasst');
      onChanged(r.eingangsrechnung);
      onOpenChange(false);
    } catch (err) { if (err?.message) toast.error(err.message); } finally { setBusy(''); }
  };
  const aktion = async (name, fn) => { setBusy(name); try { const r = await fn(); if (r) { onChanged(r.eingangsrechnung); onOpenChange(false); } } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const pruefen = () => aktion('pruefen', () => api.post(`/api/eingangsrechnungen/${rechnung.id}/pruefen`));
  const bezahlt = () => aktion('bezahlt', async () => { const am = await fragen({ titel: 'Bezahlt am', text: 'Datum der Zahlung (JJJJ-MM-TT):', vorgabe: todayKey(), pflicht: true }); return am ? api.post(`/api/eingangsrechnungen/${rechnung.id}/bezahlt`, { am }) : null; });
  const storno = () => aktion('storno', async () => { const grund = await fragen({ titel: 'Stornieren', text: 'Grund:', pflicht: true }); return grund ? api.post(`/api/eingangsrechnungen/${rechnung.id}/storno`, { grund }) : null; });
  const loeschen = () => aktion('loeschen', async () => { if (!(await bestaetigen({ titel: 'Eingangsrechnung löschen?', text: 'Nur erfasste Rechnungen lassen sich löschen.', gefaehrlich: true }))) return null; await api.del(`/api/eingangsrechnungen/${rechnung.id}`); toast.success('Gelöscht'); return { eingangsrechnung: null }; });
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={rechnung ? `Eingangsrechnung ${rechnung.rechnungsnummer}` : 'Eingangsrechnung erfassen'} subtitle={rechnung ? `${rechnung.lieferant} · ${rechnung.status_name}` : 'Beleg hochladen, Werte prüfen, auf Projekte und Kostenarten aufteilen. Erst „geprüft“ zählt in der Nachkalkulation.'} width="sm:max-w-2xl"
      footer={<>
        {rechnung?.status === 'erfasst' && <Btn variant="ghost" onClick={loeschen} loading={busy === 'loeschen'} className="text-[#C41E3A] mr-auto"><Trash2 size={16} /> Löschen</Btn>}
        {rechnung && rechnung.status !== 'storniert' && <Btn variant="ghost" onClick={storno} loading={busy === 'storno'}><Ban size={16} /> Storno</Btn>}
        {rechnung?.status === 'erfasst' && <Btn variant="soft" onClick={pruefen} loading={busy === 'pruefen'}><Check size={16} /> Geprüft</Btn>}
        {rechnung && ['erfasst', 'geprueft'].includes(rechnung.status) && <Btn variant="soft" onClick={bezahlt} loading={busy === 'bezahlt'}><CreditCard size={16} /> Bezahlt</Btn>}
        {bearbeitbar && <Btn onClick={speichern} loading={busy === 'speichern'}>Speichern</Btn>}
      </>}>
      <div className="space-y-3">
        <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3">
          <div className="text-[13px] font-semibold mb-1 flex items-center gap-2"><Paperclip size={14} /> Beleg{bearbeitbar && <span className="ml-auto"><KiEntwurfDialog art="beleg" onUebernehmen={(v) => setF((x) => ({ ...x, lieferant: v.lieferant || x.lieferant, lieferant_ustid: v.lieferant_ustid || x.lieferant_ustid, rechnungsnummer: v.rechnungsnummer || x.rechnungsnummer, rechnungsdatum: v.rechnungsdatum || x.rechnungsdatum, faellig_am: v.faellig_am || x.faellig_am, netto: v.netto ?? x.netto, ust: v.ust ?? x.ust, brutto: v.brutto ?? x.brutto }))}>KI aus Text</KiEntwurfDialog></span>}</div>
          {beleg ? <div className="text-[13px] flex items-center gap-2 flex-wrap"><button type="button" className="text-[#C41E3A] font-medium" onClick={() => openFile(`/api/dokumente/${beleg.id}/datei`).catch((e) => toast.error(e.message))}>{beleg.filename}</button><span className="text-[#6E6E73]">{Math.round((beleg.size || 0) / 1024)} KB</span>{vorschlag && <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#E8F0FE] text-[#1D4ED8]">aus {vorschlag.quelle === 'zugferd' ? 'ZUGFeRD' : 'XRechnung'} vorausgefüllt – bitte prüfen</span>}</div> : <div className="text-[13px] text-[#6E6E73]">Noch kein Beleg.</div>}
          {bearbeitbar && <div className="flex items-center gap-2 mt-2"><input ref={datei} type="file" accept=".pdf,.xml,image/*,application/pdf,application/xml,text/xml" className="text-[13px]" /><Btn size="sm" variant="soft" onClick={hochladen} loading={busy === 'upload'}>Hochladen</Btn></div>}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Lieferant"><TextInput value={f.lieferant} onChange={set('lieferant')} disabled={!bearbeitbar} /></Field>
          <Field label="USt-IdNr. Lieferant (optional)"><TextInput value={f.lieferant_ustid || ''} onChange={set('lieferant_ustid')} disabled={!bearbeitbar} /></Field>
          <Field label="Rechnungsnummer"><TextInput value={f.rechnungsnummer} onChange={set('rechnungsnummer')} disabled={!bearbeitbar} /></Field>
          <div className="grid grid-cols-2 gap-2"><Field label="Rechnungsdatum"><TextInput type="date" value={f.rechnungsdatum || ''} onChange={set('rechnungsdatum')} disabled={!bearbeitbar} /></Field><Field label="Fällig am"><TextInput type="date" value={f.faellig_am || ''} onChange={set('faellig_am')} disabled={!bearbeitbar} /></Field></div>
          <div className="grid grid-cols-3 gap-2 sm:col-span-2">
            <Field label="Netto"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.netto} onChange={setBetrag('netto')} disabled={!bearbeitbar} /></Field>
            <Field label="Umsatzsteuer"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.ust} onChange={setBetrag('ust')} disabled={!bearbeitbar} /></Field>
            <Field label="Brutto"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.brutto} onChange={setBetrag('brutto')} disabled={!bearbeitbar} /></Field>
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1"><div className="text-[13px] font-semibold">Aufteilung auf Projekte und Kostenarten</div><div className={`text-[12px] ${rest < 0 ? 'text-[#C41E3A]' : 'text-[#6E6E73]'}`}>zugeordnet {fmtGeld(zugeordnet)} · nicht zugeordnet {fmtGeld(rest)}</div></div>
          {f.zuordnungen.map((z, i) => (
            <div key={i} className="grid grid-cols-[1fr_110px_150px_32px] gap-2 items-center mb-1.5">
              <Select value={z.project_id || ''} onChange={(e) => zuordnung(i, { project_id: e.target.value })} disabled={!bearbeitbar}><option value="">Projekt …</option>{projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>
              <TextInput type="number" inputMode="decimal" step="0.01" min="0" value={z.betrag_netto ?? ''} onChange={(e) => zuordnung(i, { betrag_netto: e.target.value })} className="text-right" disabled={!bearbeitbar} />
              <Select value={z.kostenart || 'material'} onChange={(e) => zuordnung(i, { kostenart: e.target.value })} disabled={!bearbeitbar}>{Object.entries(kostenarten).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
              {bearbeitbar ? <IconBtn size={28} onClick={() => setF((x) => ({ ...x, zuordnungen: x.zuordnungen.filter((_, j) => j !== i) }))} className="text-[#C41E3A]"><Trash2 size={14} /></IconBtn> : <span />}
            </div>
          ))}
          {bearbeitbar && <div className="flex gap-2"><Btn size="sm" variant="ghost" onClick={() => setF((x) => ({ ...x, zuordnungen: [...x.zuordnungen, { project_id: '', betrag_netto: rest > 0 ? rest : '', kostenart: x.kostenart || 'material' }] }))}><Plus size={14} /> Projekt zuordnen</Btn></div>}
          <div className="text-[11px] text-[#86868B] mt-1">Nicht zugeordnete Beträge gelten als Gemeinkosten der Firma und erscheinen in keiner Projekt-Nachkalkulation.</div>
        </div>
        <Field label="Notiz"><TextArea rows={2} value={f.notiz || ''} onChange={set('notiz')} /></Field>
        {rechnung?.verlauf?.length > 0 && <div className="text-[12px] text-[#6E6E73]">{rechnung.verlauf.map((v, i) => <div key={i}>{v.at ? new Date(v.at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''} · {v.aktion} · {v.user_name}{v.text ? ` – ${v.text}` : ''}</div>)}</div>}
      </div>
    </Sheet>
  );
}

/** Eingangsrechnungen (Lieferantenrechnungen): erfassen mit Beleg, prüfen, bezahlen, stornieren – Kosten fließen nach der Prüfung in die Nachkalkulation. */
export default function EingangsrechnungenPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || '';
  const [d, setD] = useState(null);
  const [projekte, setProjekte] = useState([]);
  const [dialog, setDialog] = useState(false);
  const [edit, setEdit] = useState(null);
  const laden = useCallback(() => api.get(`/api/eingangsrechnungen${status ? `?status=${status}` : ''}`).then(setD).catch((err) => toast.error(err.message)), [status]);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => { api.get('/api/projekte').then((r) => setProjekte((r.projekte || r).filter((p) => !p.archived))).catch(() => {}); }, []);
  useEffect(() => {
    const id = params.get('id');
    if (id && d) { const r = d.eingangsrechnungen.find((x) => x.id === id); if (r) { setEdit(r); setDialog(true); } const p = new URLSearchParams(params); p.delete('id'); setParams(p, { replace: true }); }
  }, [params, d, setParams]);
  const z = d?.zaehler || {};
  return (
    <Layout title="Eingangsrechnungen" subtitle="Lieferantenrechnungen mit Beleg erfassen, prüfen und Projekten zuordnen. Aus XRechnung oder ZUGFeRD werden die Werte vorausgefüllt – geprüft wird immer von Hand."
      action={<Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={16} /> Eingangsrechnung</Btn>}>
      {!d ? <Ladeanzeige /> : (
        <>
          <div className="grid grid-cols-3 gap-3 mb-5">
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Offen (brutto)</div><div className="text-[20px] font-semibold">{fmtGeld(d.offen_brutto)}</div><div className="text-[12px] text-[#6E6E73]">{(z.erfasst || 0) + (z.geprueft || 0)} Rechnungen</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Zu prüfen</div><div className="text-[20px] font-semibold">{z.erfasst || 0}</div><div className="text-[12px] text-[#6E6E73]">zählen noch nicht</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Überfällig</div><div className={`text-[20px] font-semibold ${d.ueberfaellig ? 'text-[#C41E3A]' : ''}`}>{d.ueberfaellig}</div><div className="text-[12px] text-[#6E6E73]">Fälligkeit überschritten</div></Card>
          </div>
          <div className="flex flex-wrap gap-2 mb-4">{FILTER.map(([k, l]) => <Chip key={k} active={status === k} onClick={() => setParams(k ? { status: k } : {}, { replace: true })}>{l}{k && z[k] ? ` (${z[k]})` : ''}</Chip>)}</div>
          {d.eingangsrechnungen.length === 0 ? <Card><Empty icon={ReceiptText} title="Keine Eingangsrechnungen" text="Erfasse die erste Lieferantenrechnung – mit PDF, Foto oder E-Rechnung als Beleg." /></Card> : (
            <Card className="overflow-hidden">
              <ul className="divide-y divide-black/[0.06]">
                {d.eingangsrechnungen.map((r) => (
                  <li key={r.id} role="button" tabIndex={0} onClick={() => { setEdit(r); setDialog(true); }} onKeyDown={(e) => e.key === 'Enter' && (setEdit(r), setDialog(true))} className="px-4 sm:px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-black/[0.02]">
                    <FileText size={18} className="text-[#6E6E73] shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-[15px] truncate">{r.lieferant} · {r.rechnungsnummer}</div>
                      <div className="text-[12px] text-[#6E6E73] truncate">{r.rechnungsdatum ? fmtDate(fromKey(r.rechnungsdatum)) : ''}{r.faellig_am ? ` · fällig ${fmtDate(fromKey(r.faellig_am))}` : ''}{r.projekte?.length ? ` · ${r.projekte.join(', ')}` : ' · ohne Projekt'}{r.nicht_zugeordnet_netto > 0 && r.zuordnungen?.length ? ` · ${fmtGeld(r.nicht_zugeordnet_netto)} nicht zugeordnet` : ''}{r.dublette_hinweis ? ' · Dublettenhinweis' : ''}</div>
                    </div>
                    <div className="text-right"><div className="font-semibold text-[15px]">{fmtGeld(r.brutto)}</div><div className="text-[11px] text-[#6E6E73]">{fmtGeld(r.netto)} netto</div></div>
                    {r.ueberfaellig && <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#FDE8E8] text-[#C41E3A]">überfällig</span>}
                    <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 whitespace-nowrap ${STATUS_CLS[r.status] || ''}`}>{r.status_name}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
      <RechnungDialog open={dialog} onOpenChange={setDialog} rechnung={edit} projekte={projekte} kostenarten={d?.kostenarten || {}} onChanged={laden} />
    </Layout>
  );
}
