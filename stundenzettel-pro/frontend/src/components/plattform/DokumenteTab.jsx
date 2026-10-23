import React, { useCallback, useEffect, useState } from 'react';
import { ExternalLink, FileText, Globe, Lock, Paperclip, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty, IconBtn, Select, TextInput, Toggle } from '../ui';
import { api, openFile } from '../../lib/api';
import { useAuth } from '../../lib/auth';

const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

/** Geteilte Projektdokumente (Baupläne, Protokolle): Eigentümer gibt für alle beteiligten Firmen frei, Partner laden eigene hoch. */
export default function DokumenteTab({ projectId }) {
  const { user, isBuero } = useAuth();
  const [d, setD] = useState(null);
  const [kategorie, setKategorie] = useState('Baupläne');
  const [note, setNote] = useState('');
  const [fuerAlle, setFuerAlle] = useState(true);
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/dokumente`).then(setD).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('datei', file); fd.append('kategorie', kategorie); fd.append('note', note); fd.append('fuer_alle', fuerAlle ? 'true' : 'false');
    setBusy(true);
    try { await api.upload(`/api/projekte/${projectId}/dokumente`, fd); toast.success('Dokument gespeichert'); setNote(''); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const freigabe = async (doc, wert) => { try { await api.put(`/api/projektdokumente/${doc.id}`, { fuer_alle: wert }); laden(); } catch (err) { toast.error(err.message); } };
  const loeschen = async (doc) => { if (!window.confirm(`„${doc.filename}“ löschen?`)) return; try { await api.del(`/api/dokumente/${doc.id}`); laden(); } catch (err) { toast.error(err.message); } };
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <Card className="p-5 space-y-4">
      <h2 className="text-[16px] flex items-center gap-2"><Paperclip size={16} /> Projektdokumente</h2>
      {d.hochladen && (
        <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <Select value={kategorie} onChange={(e) => setKategorie(e.target.value)}>{d.kategorien.map((k) => <option key={k} value={k}>{k}</option>)}</Select>
            <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Bezeichnung, z. B. Grundriss EG" className="flex-1 min-w-[180px]" />
            <label className="inline-flex"><input type="file" accept="application/pdf,image/*,.doc,.docx,.xls,.xlsx,.txt" className="hidden" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ''; }} /><span className="inline-flex items-center gap-2 h-10 px-4 rounded-full bg-[#1D1D1F] text-white text-[14px] font-semibold cursor-pointer">{busy ? '…' : <Paperclip size={15} />} Hochladen</span></label>
          </div>
          {d.leitung && <Toggle checked={fuerAlle} onChange={setFuerAlle} label="Für alle beteiligten Firmen freigeben" hint="Sonst sieht es nur die eigene Firma." />}
        </div>
      )}
      {d.dokumente.length === 0 ? <Empty icon={FileText} title="Noch keine Dokumente" text="Baupläne, Aufträge, Protokolle, Unterweisungen – mit Freigabe für die beteiligten Firmen." /> : (
        <ul className="divide-y divide-black/[0.06]">
          {d.dokumente.map((doc) => (
            <li key={doc.id} className="py-2.5 flex items-center gap-3 text-[14px]">
              <span className="w-9 h-9 rounded-xl bg-[#F5F5F7] flex items-center justify-center text-[#6E6E73] shrink-0">{doc.freigabe_alle ? <Globe size={16} /> : <Lock size={16} />}</span>
              <div className="flex-1 min-w-0"><div className="font-medium truncate">{doc.note || doc.filename}</div><div className="text-[12px] text-[#86868B]">{doc.category} · {doc.firma_name} · {doc.uploaded_by_name} · {fmtZeit(doc.created_at)} · {Math.round(doc.size / 1024)} KB{doc.freigabe_alle ? ' · für alle Firmen' : ' · nur eigene Firma'}</div></div>
              {d.leitung && <Btn size="sm" variant="ghost" onClick={() => freigabe(doc, !doc.freigabe_alle)}>{doc.freigabe_alle ? 'Freigabe entziehen' : 'Freigeben'}</Btn>}
              <IconBtn size={30} onClick={() => openFile(`/api/dokumente/${doc.id}/datei`).catch((err) => toast.error(err.message))} title="Öffnen"><ExternalLink size={15} /></IconBtn>
              {(isBuero && doc.uploaded_by === user?.id) || (isBuero && d.leitung) ? <IconBtn size={30} variant="danger" onClick={() => loeschen(doc)} title="Löschen"><Trash2 size={14} /></IconBtn> : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
