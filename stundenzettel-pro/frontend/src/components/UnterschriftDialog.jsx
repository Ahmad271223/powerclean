import React, { useEffect, useState } from 'react';
import { PenLine } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { fmtDate, fromKey, addDays, isoWeek } from '../lib/dates';
import SignaturePad from './SignaturePad';
import { Sheet, Btn, Field, TextInput } from './ui';

/** Kunde / Objektleiter unterschreibt den Stundenzettel einer Kalenderwoche direkt auf dem Handy. */
export default function UnterschriftDialog({ open, onOpenChange, projectId, mondayKey, customerName = '', onSaved }) {
  const [name, setName] = useState('');
  const [bild, setBild] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (open) { setName(customerName || ''); setBild(null); } }, [open, customerName]);
  if (!mondayKey) return null;
  const monday = fromKey(mondayKey);
  const { week, year } = isoWeek(monday);

  const speichern = async () => {
    if (!name.trim()) { toast.error('Bitte den Namen des Unterzeichners eingeben'); return; }
    if (!bild) { toast.error('Bitte unterschreiben'); return; }
    setBusy(true);
    try {
      await api.post(`/api/projekte/${projectId}/unterschriften`, { week_monday: mondayKey, signer_name: name.trim(), image: bild });
      toast.success(`Unterschrift für KW ${week} gespeichert`);
      onSaved?.();
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={`Unterschrift KW ${week} / ${year}`} subtitle={`${fmtDate(monday)} – ${fmtDate(addDays(monday, 6))} · erscheint auf dem Stundenzettel bei „Unterschrift Auftraggeber“.`}>
      <div className="space-y-5">
        <Field label="Name des Unterzeichners (Auftraggeber / Objektleitung)"><TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Frau Richter, Objektleitung" /></Field>
        {open && <SignaturePad label="Unterschrift des Auftraggebers" onChange={setBild} height={180} />}
        <p className="text-[12px] text-[#86868B]">Mit der Unterschrift bestätigt der Auftraggeber die erfassten Zeiten dieser Woche. Zeitpunkt und Name werden gespeichert.</p>
        <div className="flex justify-end gap-2">
          <Btn variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn>
          <Btn onClick={speichern} loading={busy}><PenLine size={16} /> Unterschrift speichern</Btn>
        </div>
      </div>
    </Sheet>
  );
}
