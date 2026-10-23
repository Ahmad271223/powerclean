import React, { useEffect, useState } from 'react';
import { PenLine } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { fmtDate, fromKey, addDays, isoWeek } from '../lib/dates';
import SignaturePad from './SignaturePad';
import { Sheet, Btn, Field, TextInput, TextArea } from './ui';
import { useAuth } from '../lib/auth';

/** Kunde / Objektleiter unterschreibt den Stundenzettel einer Kalenderwoche direkt auf dem Handy. */
export default function UnterschriftDialog({ open, onOpenChange, projectId, mondayKey, customerName = '', onSaved }) {
  const { isBuero } = useAuth();
  const [name, setName] = useState('');
  const [bild, setBild] = useState(null);
  const [grund, setGrund] = useState('');
  const [busy, setBusy] = useState(false);
  const vorhanden = !!customerName;   // für diese Woche gibt es schon eine Unterschrift

  useEffect(() => { if (open) { setName(customerName || ''); setBild(null); setGrund(''); } }, [open, customerName]);
  if (!mondayKey) return null;
  const monday = fromKey(mondayKey);
  const { week, year } = isoWeek(monday);

  const speichern = async () => {
    if (!name.trim()) { toast.error('Bitte den Namen des Unterzeichners eingeben'); return; }
    if (!bild) { toast.error('Bitte unterschreiben'); return; }
    if (vorhanden && !grund.trim()) { toast.error('Bitte begründen, warum die vorhandene Unterschrift ersetzt wird'); return; }
    setBusy(true);
    try {
      await api.post(`/api/projekte/${projectId}/unterschriften`, { week_monday: mondayKey, signer_name: name.trim(), image: bild, grund: grund.trim() });
      toast.success(`Unterschrift für KW ${week} gespeichert`);
      onSaved?.();
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={`Unterschrift KW ${week} / ${year}`} subtitle={`${fmtDate(monday)} – ${fmtDate(addDays(monday, 6))} · erscheint auf dem Stundenzettel bei „Unterschrift Auftraggeber“.`}>
      <div className="space-y-5">
        {vorhanden && !isBuero && <div className="rounded-2xl bg-[#FDE8E8] text-[#C41E3A] px-4 py-3 text-[13px]">Diese Woche ist bereits unterschrieben ({customerName}). Eine Änderung kann nur das Büro mit Begründung vornehmen – die alte Unterschrift bleibt nachvollziehbar erhalten.</div>}
        {vorhanden && isBuero && <div className="rounded-2xl bg-[#FFF4E5] text-[#7A4100] px-4 py-3 text-[13px]">Diese Woche ist bereits unterschrieben ({customerName}). Die neue Unterschrift ersetzt sie als Version 2; die alte bleibt mit Begründung, Zeitpunkt und Name nachvollziehbar.</div>}
        <Field label="Name des Unterzeichners (Auftraggeber / Objektleitung)"><TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Frau Richter, Objektleitung" disabled={vorhanden && !isBuero} /></Field>
        {vorhanden && isBuero && <Field label="Begründung für das Ersetzen"><TextArea rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} placeholder="z. B. falsche Person hatte unterschrieben" /></Field>}
        {open && (!vorhanden || isBuero) && <SignaturePad label="Unterschrift des Auftraggebers" onChange={setBild} height={180} />}
        <p className="text-[12px] text-[#86868B]">Mit der Unterschrift bestätigt der Auftraggeber die erfassten Zeiten dieser Woche. Zeitpunkt und Name werden gespeichert.</p>
        <div className="flex justify-end gap-2">
          <Btn variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn>
          <Btn onClick={speichern} loading={busy} disabled={vorhanden && !isBuero}><PenLine size={16} /> {vorhanden && isBuero ? 'Unterschrift ersetzen' : 'Unterschrift speichern'}</Btn>
        </div>
      </div>
    </Sheet>
  );
}
