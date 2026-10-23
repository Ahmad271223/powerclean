import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ExternalLink, FileText, Folder, Globe, History, Lock, Paperclip, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, IconBtn, Select, TextInput, Toggle } from '../ui';
import { api, openFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

/** Geteilte Projektdokumente mit Ordnern und Versionen: Eigentümer gibt für alle beteiligten Firmen frei, Partner laden eigene hoch. */
export default function DokumenteTab({ projectId }) {
  const { user, isBuero } = useAuth();
  const [d, setD] = useState(null);
  const [kategorie, setKategorie] = useState('Baupläne');
  const [note, setNote] = useState('');
  const [ordner, setOrdner] = useState('');
  const [fuerAlle, setFuerAlle] = useState(true);
  const [alteVersionen, setAlteVersionen] = useState(false);
  const [ersetzt, setErsetzt] = useState(null);
  const [busy, setBusy] = useState(false);
  const eingabe = useRef(null);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/dokumente`).then(setD).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('datei', file); fd.append('kategorie', ersetzt?.category || kategorie); fd.append('note', ersetzt ? (ersetzt.note || '') : note); fd.append('fuer_alle', (ersetzt ? !!ersetzt.freigabe_alle : fuerAlle) ? 'true' : 'false'); fd.append('ordner', ersetzt?.ordner || ordner);
    if (ersetzt) fd.append('ersetzt_id', ersetzt.id);
    setBusy(true);
    try { await api.upload(`/api/projekte/${projectId}/dokumente`, fd); toast.success(ersetzt ? `Neue Version von „${ersetzt.note || ersetzt.filename}“ gespeichert` : 'Dokument gespeichert'); setNote(''); setErsetzt(null); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const neueVersion = (doc) => { setErsetzt(doc); eingabe.current?.click(); };
  const freigabe = async (doc, wert) => { try { await api.put(`/api/projektdokumente/${doc.id}`, { fuer_alle: wert }); laden(); } catch (err) { toast.error(err.message); } };
  const loeschen = async (doc) => { if (!window.confirm(`„${doc.note || doc.filename}“ löschen?`)) return; try { await api.del(`/api/dokumente/${doc.id}`); laden(); } catch (err) { toast.error(err.message); } };
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  const sichtbar = d.dokumente.filter((x) => alteVersionen || x.aktuell !== false);
  const gruppen = {};
  for (const doc of sichtbar) (gruppen[doc.ordner || ''] ||= []).push(doc);
  const ordnerNamen = Object.keys(gruppen).sort((a, b) => (a === '' ? 1 : b === '' ? -1 : a.localeCompare(b)));
  return (
    <Card className="p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-[16px] flex items-center gap-2"><Paperclip size={16} /> Projektdokumente</h2><Toggle checked={alteVersionen} onChange={setAlteVersionen} label="Ältere Versionen anzeigen" /></div>
      <input ref={eingabe} type="file" accept="application/pdf,image/*,.doc,.docx,.xls,.xlsx,.txt" className="hidden" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ''; }} />
      {d.hochladen && (
        <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr_1fr_auto] gap-2 items-center">
            <Select value={kategorie} onChange={(e) => setKategorie(e.target.value)}>{d.kategorien.map((k) => <option key={k} value={k}>{k}</option>)}</Select>
            <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Bezeichnung, z. B. Grundriss EG" />
            <TextInput value={ordner} onChange={(e) => setOrdner(e.target.value)} placeholder="Ordner, z. B. Pläne/EG" list="ordner-vorschlaege" />
            <datalist id="ordner-vorschlaege">{[...new Set(d.dokumente.map((x) => x.ordner).filter(Boolean))].map((o) => <option key={o} value={o} />)}</datalist>
            <Btn variant="dark" onClick={() => { setErsetzt(null); eingabe.current?.click(); }} loading={busy}><Paperclip size={15} /> Hochladen</Btn>
          </div>
          {d.leitung && <Toggle checked={fuerAlle} onChange={setFuerAlle} label="Für alle beteiligten Firmen freigeben" hint="Sonst sieht es nur die eigene Firma. Interne Projektunterlagen bleiben ohne Freigabe privat." />}
        </div>
      )}
      {sichtbar.length === 0 ? <Empty icon={FileText} title="Noch keine Dokumente" text="Baupläne, Aufträge, Protokolle, Unterweisungen – in Ordnern, mit Versionen und Freigabe für die beteiligten Firmen." /> : ordnerNamen.map((o) => (
        <div key={o || '_'}>
          {ordnerNamen.length > 1 || o ? <div className="text-[12px] font-semibold text-[#6E6E73] flex items-center gap-1.5 mt-2 mb-1"><Folder size={13} /> {o || 'Ohne Ordner'}</div> : null}
          <ul className="divide-y divide-black/[0.06]">
            {gruppen[o].map((doc) => (
              <li key={doc.id} className={`py-2.5 flex items-center gap-3 text-[14px] ${doc.aktuell === false ? 'opacity-60' : ''}`}>
                <span className="w-9 h-9 rounded-xl bg-[#F5F5F7] flex items-center justify-center text-[#6E6E73] shrink-0">{doc.freigabe_alle ? <Globe size={16} /> : <Lock size={16} />}</span>
                <div className="flex-1 min-w-0"><div className="font-medium truncate">{doc.note || doc.filename}{(doc.version || 1) > 1 || doc.aktuell === false ? <span className="ml-2 text-[11px] font-semibold rounded-full px-1.5 py-0.5 bg-black/[0.06] text-[#6E6E73]">v{doc.version || 1}{doc.aktuell === false ? ' · ersetzt' : ''}</span> : null}</div><div className="text-[12px] text-[#86868B] truncate">{doc.category} · {doc.firma_name} · {doc.uploaded_by_name} · {fmtZeit(doc.created_at)} · {Math.max(1, Math.round(doc.size / 1024))} KB{doc.freigabe_alle ? ' · für alle Firmen' : ' · nur eigene Firma'}</div></div>
                {d.leitung && doc.aktuell !== false && <Btn size="sm" variant="ghost" onClick={() => freigabe(doc, !doc.freigabe_alle)}>{doc.freigabe_alle ? 'Freigabe entziehen' : 'Freigeben'}</Btn>}
                {d.hochladen && doc.aktuell !== false && doc.firma_id === user?.firma_id && <IconBtn size={30} onClick={() => neueVersion(doc)} title="Neue Version hochladen"><History size={15} /></IconBtn>}
                <IconBtn size={30} onClick={() => openFile(`/api/dokumente/${doc.id}/datei`).catch((err) => toast.error(err.message))} title="Öffnen"><ExternalLink size={15} /></IconBtn>
                {isBuero && doc.firma_id === user?.firma_id ? <IconBtn size={30} variant="danger" onClick={() => loeschen(doc)} title="Löschen"><Trash2 size={14} /></IconBtn> : null}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Card>
  );
}
