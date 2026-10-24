import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FileText, LayoutTemplate, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Chip, Empty, Field, IconBtn, Select, Sheet, TextArea, TextInput, Toggle } from '../components/ui';
import KundeDialog from '../components/KundeDialog';
import { useDialoge } from '../components/Dialoge';
import { api } from '../lib/api';
import { STATUS_CLS, STATUS_NAMEN, fmtGeld } from '../lib/angebot';
import { fmtDate, fromKey } from '../lib/dates';

const FILTER = [['', 'Alle'], ['anfrage', 'Anfragen'], ['entwurf', 'Entwürfe'], ['gesendet', 'Gesendet'], ['angenommen', 'Angenommen'], ['abgelehnt', 'Abgelehnt'], ['abgelaufen', 'Abgelaufen']];

/** Neues Angebot: Kunde (vorhanden oder neu), Titel, Vorlage, Projekt – oder nur die Kundenanfrage erfassen. */
function NeuDialog({ open, onOpenChange, kunden, vorlagen, projekte, vorgabe, onKunde }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ titel: '', customer_id: '', vorlage_id: '', project_id: '', nur_anfrage: false, anfrage_text: '', kanal: 'Telefon' });
  const [kundeDialog, setKundeDialog] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setForm((f) => ({ ...f, titel: '', vorlage_id: '', nur_anfrage: false, anfrage_text: '', project_id: vorgabe?.project_id || '', customer_id: vorgabe?.customer_id || f.customer_id || '' })); }, [open, vorgabe]);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const projektGewaehlt = (e) => {
    const id = e.target.value;
    const p = projekte.find((x) => x.id === id);
    setForm((f) => ({ ...f, project_id: id, customer_id: f.customer_id || p?.customer_id || '', titel: f.titel || (p ? p.name : '') }));
  };
  const anlegen = async () => {
    if (!form.customer_id && !form.nur_anfrage) { toast.error('Bitte einen Kunden wählen oder anlegen'); return; }
    setBusy(true);
    try {
      const daten = { titel: form.titel, customer_id: form.customer_id || null, vorlage_id: form.vorlage_id || null, project_id: form.project_id || null };
      if (form.nur_anfrage) { daten.status = 'anfrage'; daten.anfrage = { text: form.anfrage_text, kanal: form.kanal, eingegangen_am: new Date().toISOString().slice(0, 10) }; }
      const r = await api.post('/api/kundenangebote', daten);
      onOpenChange(false);
      navigate(`/angebote/${r.angebot.id}`);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange} title="Neues Angebot" subtitle="Aus leerem Entwurf oder einer Vorlage. Die Anfrage kannst du auch erst nur festhalten."
        footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={anlegen} loading={busy}>{form.nur_anfrage ? 'Anfrage erfassen' : 'Angebot anlegen'}</Btn></>}>
        <div className="space-y-3">
          <Field label="Kunde">
            <div className="flex gap-2">
              <Select value={form.customer_id} onChange={set('customer_id')} className="flex-1"><option value="">Kunde wählen …</option>{kunden.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}</Select>
              <Btn variant="soft" onClick={() => setKundeDialog(true)}><Plus size={15} /> Neu</Btn>
            </div>
          </Field>
          <Field label="Titel / Bauvorhaben"><TextInput value={form.titel} onChange={set('titel')} placeholder="z. B. Unterhaltsreinigung Bürogebäude Nord" /></Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Vorlage" hint={vorlagen.length ? 'Positionen und Texte werden übernommen' : 'Noch keine Vorlagen – speichere ein Angebot als Vorlage'}><Select value={form.vorlage_id} onChange={set('vorlage_id')} disabled={!vorlagen.length}><option value="">Ohne Vorlage</option>{vorlagen.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</Select></Field>
            <Field label="Projekt (optional)"><Select value={form.project_id} onChange={projektGewaehlt}><option value="">Kein Projekt</option>{projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
          </div>
          <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={form.nur_anfrage} onChange={(v) => setForm((f) => ({ ...f, nur_anfrage: v }))} label="Nur Kundenanfrage erfassen" hint="Das Angebot arbeitest du später aus; die Anfrage erscheint auf der Startseite." /></div>
          {form.nur_anfrage && (
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px] gap-3">
              <Field label="Was wünscht der Kunde?"><TextArea rows={3} value={form.anfrage_text} onChange={set('anfrage_text')} placeholder="Leistung, Umfang, Termin, Besonderheiten" /></Field>
              <Field label="Eingang über"><Select value={form.kanal} onChange={set('kanal')}>{['Telefon', 'E-Mail', 'Website', 'Persönlich', 'Empfehlung'].map((k) => <option key={k}>{k}</option>)}</Select></Field>
            </div>
          )}
        </div>
      </Sheet>
      <KundeDialog open={kundeDialog} onOpenChange={setKundeDialog} kunde={null} onSaved={(k) => { onKunde(k); setForm((f) => ({ ...f, customer_id: k.id })); }} />
    </>
  );
}

function VorlagenDialog({ open, onOpenChange, vorlagen, onChanged }) {
  const { bestaetigen } = useDialoge();
  const loeschen = async (v) => {
    if (!(await bestaetigen({ titel: 'Vorlage löschen?', text: `„${v.name}“ wird entfernt. Bestehende Angebote bleiben unverändert.`, gefaehrlich: true }))) return;
    try { await api.del(`/api/kundenangebote/vorlagen/${v.id}`); toast.success('Vorlage gelöscht'); onChanged(); } catch (err) { toast.error(err.message); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Angebotsvorlagen" subtitle="Eine Vorlage entsteht aus einem Angebot („Als Vorlage speichern“) und bringt Positionen, Texte und Gültigkeit mit.">
      {vorlagen.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch keine Vorlagen.</p> : (
        <ul className="divide-y divide-black/[0.06]">{vorlagen.map((v) => <li key={v.id} className="py-2.5 flex items-center gap-3"><div className="flex-1 min-w-0"><div className="font-semibold text-[14px] truncate">{v.name}</div><div className="text-[12px] text-[#6E6E73]">{(v.positionen || []).length} Positionen · gültig {v.gueltig_tage} Tage{v.titel ? ` · ${v.titel}` : ''}</div></div><IconBtn onClick={() => loeschen(v)} title="Löschen" className="text-[#C41E3A]"><Trash2 size={16} /></IconBtn></li>)}</ul>
      )}
    </Sheet>
  );
}

/** Angebote an Kunden: Liste mit Status, Summen und Filter; neue Angebote, Vorlagen. */
export default function AngebotePage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || '';
  const [daten, setDaten] = useState(null);
  const [kunden, setKunden] = useState([]);
  const [vorlagen, setVorlagen] = useState([]);
  const [projekte, setProjekte] = useState([]);
  const [neu, setNeu] = useState(false);
  const [vorlagenDialog, setVorlagenDialog] = useState(false);
  const laden = useCallback(() => {
    api.get(`/api/kundenangebote${status ? `?status=${status}` : ''}`).then(setDaten).catch((err) => toast.error(err.message));
  }, [status]);
  const stammdaten = useCallback(() => {
    api.get('/api/kunden').then((r) => setKunden(r.kunden)).catch(() => {});
    api.get('/api/kundenangebote/vorlagen').then((r) => setVorlagen(r.vorlagen)).catch(() => {});
    api.get('/api/projekte').then((r) => setProjekte((r.projekte || r).filter((p) => !p.archived && !p.verknuepft))).catch(() => {});
  }, []);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => { stammdaten(); }, [stammdaten]);
  useEffect(() => { if (params.get('neu')) { setNeu(true); } }, [params]);
  const vorgabe = { project_id: params.get('project_id') || '', customer_id: params.get('customer_id') || '' };
  const schliessen = (v) => { setNeu(v); if (!v && params.get('neu')) { const p = new URLSearchParams(params); p.delete('neu'); p.delete('project_id'); p.delete('customer_id'); setParams(p, { replace: true }); } };
  const z = daten?.zaehler || {};
  return (
    <Layout title="Angebote" subtitle="Kundenanfrage → Angebot → Annahme → Auftrag. Gesendete Angebote bleiben unverändert; Änderungen laufen über neue Versionen."
      action={<div className="flex gap-2"><Btn variant="soft" onClick={() => setVorlagenDialog(true)}><LayoutTemplate size={16} /> <span className="hidden sm:inline">Vorlagen</span></Btn><Btn onClick={() => setNeu(true)}><Plus size={16} /> Neues Angebot</Btn></div>}>
      {!daten ? <Ladeanzeige /> : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Offen (Entwurf + gesendet)</div><div className="text-[20px] font-semibold">{fmtGeld(daten.offen_netto)}</div><div className="text-[12px] text-[#6E6E73]">{(z.entwurf || 0) + (z.gesendet || 0)} Angebote netto</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Angenommen</div><div className="text-[20px] font-semibold text-[#1B7F3B]">{fmtGeld(daten.angenommen_netto)}</div><div className="text-[12px] text-[#6E6E73]">{z.angenommen || 0} Aufträge netto</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Anfragen</div><div className="text-[20px] font-semibold">{z.anfrage || 0}</div><div className="text-[12px] text-[#6E6E73]">noch ohne Angebot</div></Card>
            <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Abgelehnt / abgelaufen</div><div className="text-[20px] font-semibold">{(z.abgelehnt || 0) + (z.abgelaufen || 0)}</div><div className="text-[12px] text-[#6E6E73]">neue Version möglich</div></Card>
          </div>
          <div className="flex flex-wrap gap-2 mb-4">{FILTER.map(([k, l]) => <Chip key={k} active={status === k} onClick={() => setParams(k ? { status: k } : {}, { replace: true })}>{l}{k && z[k] ? ` (${z[k]})` : ''}</Chip>)}</div>
          {daten.angebote.length === 0 ? <Card><Empty icon={FileText} title={status ? 'Keine Angebote mit diesem Status' : 'Noch keine Angebote'} text="Lege das erste Angebot an – aus leerem Entwurf oder einer Vorlage." action={<Btn onClick={() => setNeu(true)}><Plus size={16} /> Neues Angebot</Btn>} /></Card> : (
            <Card className="overflow-hidden">
              <ul className="divide-y divide-black/[0.06]">
                {daten.angebote.map((a) => (
                  <li key={a.id} role="button" tabIndex={0} onClick={() => navigate(`/angebote/${a.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/angebote/${a.id}`)} className="px-4 sm:px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-black/[0.02]">
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-[15px] truncate">{a.nummer}{a.version > 1 ? <span className="ml-1 text-[11px] font-medium text-[#6E6E73] bg-black/[0.06] rounded-full px-1.5 py-0.5">v{a.version}</span> : null}{a.titel ? ` – ${a.titel}` : ''}</div>
                      <div className="text-[12px] text-[#6E6E73] truncate">{a.kunde_name || 'Kunde fehlt'}{a.projekt_name ? ` · ${a.projekt_name}` : ''}{a.datum ? ` · ${fmtDate(fromKey(a.datum))}` : ''}{a.status === 'gesendet' && a.gueltig_bis ? ` · gültig bis ${fmtDate(fromKey(a.gueltig_bis))}` : ''}{a.auftrag ? ' · Auftrag angelegt' : ''}</div>
                    </div>
                    <div className="text-right"><div className="font-semibold text-[15px]">{fmtGeld(a.netto)}</div><div className="text-[11px] text-[#6E6E73]">netto</div></div>
                    <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 whitespace-nowrap ${STATUS_CLS[a.status] || ''}`}>{STATUS_NAMEN[a.status] || a.status}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
      <NeuDialog open={neu} onOpenChange={schliessen} kunden={kunden} vorlagen={vorlagen} projekte={projekte} vorgabe={vorgabe} onKunde={(k) => setKunden((ks) => [...ks, k].sort((x, y) => x.name.localeCompare(y.name)))} />
      <VorlagenDialog open={vorlagenDialog} onOpenChange={setVorlagenDialog} vorlagen={vorlagen} onChanged={stammdaten} />
    </Layout>
  );
}
