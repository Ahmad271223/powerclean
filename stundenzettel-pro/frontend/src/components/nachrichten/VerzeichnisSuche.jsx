import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { toast } from 'sonner';
import ChatKnopf from './ChatKnopf';
import { Btn, Card, TextInput } from '../ui';
import { api } from '../../lib/api';

/** Firmenverzeichnis durchsuchen und eine Kontaktanfrage (Chat zwischen zwei Firmen, nur Büro/Inhaber) starten. */
export default function VerzeichnisSuche({ className = '' }) {
  const [q, setQ] = useState('');
  const [treffer, setTreffer] = useState(null);
  const [busy, setBusy] = useState(false);
  const suchen = async (e) => {
    e?.preventDefault();
    setBusy(true);
    try { setTreffer((await api.get(`/api/verzeichnis/firmen?q=${encodeURIComponent(q)}`)).firmen || []); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Card className={`p-5 space-y-3 ${className}`}>
      <h2 className="text-[16px]">Firmen finden und Kontakt aufnehmen</h2>
      <form onSubmit={suchen} className="flex gap-2"><TextInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Firma, Gewerk oder Ort" /><Btn type="submit" variant="dark" loading={busy}><Search size={15} /> Suchen</Btn></form>
      {treffer && (treffer.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Keine Firma gefunden.</p> : (
        <ul className="divide-y divide-black/[0.06]">
          {treffer.map((t) => (
            <li key={t.id} className="py-2 flex items-center gap-3">
              <div className="flex-1 min-w-0"><div className="text-[14px] font-semibold truncate">{t.name} <span className="text-[12px] font-normal text-[#6E6E73]">{t.ort}</span>{t.verifiziert && <span className="ml-1 text-[11px] font-medium text-[#1B7F3B] bg-[#E8F8EC] rounded-full px-2 py-0.5">Geprüft</span>}</div><div className="text-[12px] text-[#6E6E73] truncate">{(t.gewerke || []).join(', ')}{t.beschreibung ? ` · ${t.beschreibung}` : ''}</div></div>
              <ChatKnopf koerper={{ art: 'kontakt', firma_id: t.id }}>Kontakt</ChatKnopf>
            </li>
          ))}
        </ul>
      ))}
      <p className="text-[12px] text-[#86868B]">Kontaktanfragen sind Chats zwischen den Büros beider Firmen – nur Firmen, die im Verzeichnis sichtbar sind. Die andere Seite wird per E-Mail informiert.</p>
    </Card>
  );
}
