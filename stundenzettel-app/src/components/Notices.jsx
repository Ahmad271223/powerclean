import React, { useState } from 'react';
import { AlertTriangle, DatabaseBackup, X } from 'lucide-react';
import { useStore, totalEntryCount } from '../lib/store';
import { daysSince } from '../lib/dates';
import { Btn } from './ui';

/** Red banner when data cannot be stored reliably on this device. */
export function StorageNotice() {
  const { storage } = useStore();
  if (storage.mode === 'idb' && !storage.error) return null;
  const text = storage.error
    ? `Speicherfehler: ${storage.error}. Bitte sofort eine Sicherung erstellen.`
    : storage.mode === 'memory'
      ? 'Daten können auf diesem Gerät nicht gespeichert werden (privater Modus?). Nach dem Schließen ist alles weg.'
      : 'Eingeschränkter Speicher: Die Datenbank des Browsers ist nicht verfügbar, es wird ein kleiner Notfallspeicher genutzt. Bitte regelmäßig sichern.';
  return (
    <div className="mb-5 rounded-2xl bg-[#C41E3A]/10 border border-[#C41E3A]/30 px-4 py-3 text-[14px] text-[#8a1528] flex items-start gap-3" role="alert">
      <AlertTriangle size={18} className="shrink-0 mt-0.5" />
      <span>{text}</span>
    </div>
  );
}

/** Gentle reminder when the last backup is older than two weeks (data only lives on this device). */
export function BackupNotice({ onBackup, minDays = 14 }) {
  const { state } = useStore();
  const [hidden, setHidden] = useState(false);
  const entries = totalEntryCount();
  const days = daysSince(state.meta?.lastBackupAt);
  if (hidden || entries === 0 || days < minDays) return null;
  const when = days === Infinity ? 'noch nie gesichert' : `letzte Sicherung vor ${days} Tagen`;
  return (
    <div className="mb-5 rounded-2xl bg-white shadow-card px-4 py-3 text-[14px] flex items-center gap-3">
      <span className="w-9 h-9 rounded-xl bg-[#FFF4E5] text-[#B25E00] flex items-center justify-center shrink-0"><DatabaseBackup size={18} /></span>
      <span className="flex-1 min-w-0">
        <span className="font-semibold">Daten sichern?</span>
        <span className="text-[#6E6E73]"> {entries} Einträge, {when}. Alles liegt nur auf diesem Gerät.</span>
      </span>
      <Btn size="sm" onClick={onBackup}>Jetzt sichern</Btn>
      <button type="button" onClick={() => setHidden(true)} className="w-8 h-8 rounded-full hover:bg-black/[0.05] flex items-center justify-center text-[#86868B]" aria-label="Hinweis ausblenden"><X size={15} /></button>
    </div>
  );
}
