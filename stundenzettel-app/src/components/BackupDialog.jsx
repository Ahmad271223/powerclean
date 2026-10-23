import React, { useEffect, useRef, useState } from 'react';
import { Download, Upload, Share2, ShieldCheck, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { exportBackup, importBackup, useStore, totalEntryCount } from '../lib/store';
import { downloadBlob, shareOrDownload } from '../lib/utils';
import { daysSince, fmtDate } from '../lib/dates';
import { Sheet, Btn, SectionLabel } from './ui';

const mb = (bytes) => `${(bytes / 1024 / 1024).toLocaleString('de-DE', { maximumFractionDigits: 1 })} MB`;

/** Datensicherung: export everything as a JSON file, restore from a file. */
export default function BackupDialog({ open, onOpenChange }) {
  const { state, storage } = useStore();
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const filename = `Stundenzettel-Sicherung_${new Date().toISOString().slice(0, 10)}.json`;
  const canShare = typeof navigator !== 'undefined' && !!navigator.share;

  useEffect(() => {
    if (!open) return;
    try { navigator.storage?.estimate?.().then(setEstimate).catch(() => {}); } catch { /* ignore */ }
  }, [open]);

  const makeBlob = async () => new Blob([await exportBackup()], { type: 'application/json' });

  const share = async () => {
    setBusy(true);
    try {
      const result = await shareOrDownload(await makeBlob(), filename, 'Stundenzettel Sicherung');
      if (result === 'downloaded') toast.success('Sicherung heruntergeladen');
      if (result === 'shared') toast.success('Sicherung weitergegeben');
    } catch (err) {
      console.error(err);
      toast.error('Sicherung fehlgeschlagen');
    } finally { setBusy(false); }
  };

  const download = async () => {
    setBusy(true);
    try { downloadBlob(await makeBlob(), filename); toast.success('Sicherung heruntergeladen'); }
    catch (err) { console.error(err); toast.error('Sicherung fehlgeschlagen'); }
    finally { setBusy(false); }
  };

  const restore = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const replace = window.confirm('Vorhandene Daten durch die Sicherung ERSETZEN?\n\nOK = ersetzen · Abbrechen = Sicherung zu den vorhandenen Daten hinzufügen');
      setBusy(true);
      try {
        const r = await importBackup(String(reader.result), { merge: !replace });
        toast.success(`Wiederhergestellt: ${r.companies} Firmen, ${r.projects} Projekte, ${r.entries} Einträge, ${r.invoices} Rechnungen`);
        onOpenChange(false);
      } catch (err) {
        console.error(err);
        toast.error(err.message || 'Sicherung konnte nicht gelesen werden');
      } finally { setBusy(false); }
    };
    reader.onerror = () => toast.error('Datei konnte nicht gelesen werden');
    reader.readAsText(file);
  };

  const last = state.meta?.lastBackupAt;
  const days = daysSince(last);

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Datensicherung" subtitle="Alle Daten liegen nur auf diesem Gerät. Sichere sie regelmäßig.">
      <div className="space-y-6">
        <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 text-[14px] space-y-2">
          <div className="flex items-start gap-3">
            <ShieldCheck size={20} className="text-[#34C759] shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">{state.companies.length} Firmen · {state.projects.length} Projekte · {totalEntryCount()} Einträge · {state.invoices.length} Rechnungen</div>
              <div className="text-[#6E6E73] mt-0.5">Die Sicherung ist eine Datei, die du z. B. in iCloud, Google Drive oder per E-Mail aufbewahren kannst.</div>
            </div>
          </div>
          <div className="flex items-start gap-3 text-[13px] text-[#6E6E73]">
            <Clock size={18} className="shrink-0 mt-0.5" />
            <div>
              Letzte Sicherung: <strong className={days > 30 ? 'text-[#C41E3A]' : 'text-[#1D1D1F]'}>{last ? `${fmtDate(new Date(last))} (vor ${days} Tagen)` : 'noch nie'}</strong>
              {estimate?.usage != null && estimate?.quota ? <span> · Speicher: {mb(estimate.usage)} von {mb(estimate.quota)} belegt</span> : null}
              {storage.mode !== 'idb' && <span className="text-[#C41E3A]"> · Notfallspeicher aktiv</span>}
            </div>
          </div>
        </div>

        <section className="space-y-2">
          <SectionLabel>Sichern</SectionLabel>
          <div className="flex flex-wrap gap-2">
            <Btn className="flex-1 min-w-[200px]" onClick={canShare ? share : download} loading={busy}>
              {canShare ? <Share2 size={17} /> : <Download size={17} />} {canShare ? 'Sicherung teilen / speichern' : 'Sicherung herunterladen'}
            </Btn>
            {canShare && <Btn variant="soft" onClick={download} disabled={busy} title="Direkt herunterladen"><Download size={17} /></Btn>}
          </div>
        </section>

        <section className="space-y-2">
          <SectionLabel>Wiederherstellen</SectionLabel>
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={restore} className="hidden" />
          <Btn variant="soft" className="w-full" onClick={() => fileRef.current?.click()} disabled={busy}><Upload size={17} /> Sicherungsdatei auswählen</Btn>
          <p className="text-[12px] text-[#86868B]">Du kannst die Sicherung auch auf einem anderen Handy einspielen, um dort weiterzuarbeiten.</p>
        </section>
      </div>
    </Sheet>
  );
}
