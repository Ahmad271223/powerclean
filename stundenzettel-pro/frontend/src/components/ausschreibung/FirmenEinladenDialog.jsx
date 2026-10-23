import React, { useEffect, useState } from 'react';
import { Search, Send } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Chip, Field, Sheet, TextArea, TextInput } from '../ui';
import { api } from '../../lib/api';

/** Registrierte Firmen aus dem Verzeichnis auswählen und direkt zur Ausschreibung einladen (nur sie sehen eine private Ausschreibung). */
export default function FirmenEinladenDialog({ open, onOpenChange, ausschreibungId, bereits = [], gewerk = '', onDone }) {
  const [q, setQ] = useState('');
  const [firmen, setFirmen] = useState([]);
  const [auswahl, setAuswahl] = useState([]);
  const [nachricht, setNachricht] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setAuswahl([]); setNachricht(''); setQ(gewerk || ''); } }, [open, gewerk]);
  useEffect(() => {
    if (!open) return undefined;
    const t = setTimeout(() => api.get(`/api/verzeichnis/firmen?q=${encodeURIComponent(q)}`).then((r) => setFirmen(r.firmen || [])).catch((err) => toast.error(err.message)), 250);
    return () => clearTimeout(t);
  }, [q, open]);
  const toggle = (id) => setAuswahl((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  const senden = async () => {
    if (!auswahl.length) { toast.error('Bitte mindestens eine Firma auswählen'); return; }
    setBusy(true);
    try {
      const r = await api.post(`/api/ausschreibungen/${ausschreibungId}/einladungen`, { firma_ids: auswahl, nachricht });
      toast.success(`${r.einladungen.length} Firma/Firmen eingeladen${r.uebersprungen.length ? `, ${r.uebersprungen.length} übersprungen` : ''}`);
      onDone?.(r);
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Ausschreibung an ausgewählte Firmen senden" subtitle="Nur Firmen mit Verzeichnis-Eintrag sind auffindbar. Eingeladene Firmen bekommen eine Benachrichtigung und Zugriff auf die Unterlagen.">
      <div className="space-y-4">
        <Field label="Suche (Name, Ort, Gewerk)"><div className="relative"><Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#86868B]" /><TextInput value={q} onChange={(e) => setQ(e.target.value)} className="pl-10" placeholder="z. B. Elektro Hannover" /></div></Field>
        <div className="max-h-72 overflow-y-auto divide-y divide-black/[0.06] rounded-2xl bg-[#F5F5F7] px-3">
          {firmen.length === 0 && <p className="text-[13px] text-[#86868B] py-4">Keine Firma gefunden.</p>}
          {firmen.map((f) => {
            const schon = bereits.includes(f.id);
            return (
              <label key={f.id} className={`flex items-center gap-3 py-2.5 ${schon ? 'opacity-50' : 'cursor-pointer'}`}>
                <input type="checkbox" className="w-4 h-4 accent-[#C41E3A]" checked={schon || auswahl.includes(f.id)} disabled={schon} onChange={() => toggle(f.id)} />
                <span className="flex-1 min-w-0"><span className="block text-[14px] font-medium truncate">{f.name}</span><span className="block text-[12px] text-[#6E6E73] truncate">{[f.art === 'auftraggeber' ? 'Auftraggeber (vergibt selbst Aufträge)' : null, f.ort || f.city, (f.gewerke || []).join(', '), f.beschreibung].filter(Boolean).join(' · ')}</span></span>
                {schon && <Chip className="text-[11px]">eingeladen</Chip>}
              </label>
            );
          })}
        </div>
        <Field label="Nachricht an die Firmen (optional)"><TextArea rows={2} value={nachricht} onChange={(e) => setNachricht(e.target.value)} placeholder="z. B. Wir würden uns über Ihr Angebot freuen." /></Field>
        <div className="flex justify-end gap-2"><Btn variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={senden} loading={busy}><Send size={15} /> Ausschreibung an {auswahl.length || ''} Firmen senden</Btn></div>
      </div>
    </Sheet>
  );
}
