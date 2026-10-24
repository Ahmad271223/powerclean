import React, { useCallback, useEffect, useState } from 'react';
import { Archive, Download, FileArchive, Loader2, ShieldCheck, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty } from './ui';
import { api, download } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate, fromKey } from '../lib/dates';

const fmtZeit = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '–');
const fmtGroesse = (b) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
// Zähler der ZIP sind Dateien (eine Zeiten-Tabelle, ein Stundennachweis je Monat, ein PDF je Nachtrag …)
const INHALT = { stundennachweise: 'Stundennachweise', fotos: 'Fotos', dokumente: 'Dokumente', rechnungen: 'Rechnungen', unterschriften: 'Unterschriften', ausschreibungen: 'Ausschreibungen', angebote: 'Angebote', vergaben: 'Vergaben', tagesberichte: 'Bautagesberichte', nachtraege_pdf: 'Nachträge', abnahmen_pdf: 'Abnahmen', plattform_dokumente: 'geteilte Dokumente' };
const TABELLEN = { nachrichten: 'Nachrichten', zeiten: 'Zeiten', aufgaben: 'Aufgaben', maengel: 'Mängel', lieferungen: 'Lieferungen', protokoll: 'Protokoll', emails: 'E-Mail-Nachweise', nachweise: 'Nachweise', kommentare: 'Kommentare', checklisten: 'Checklisten' };
const inhaltText = (inhalt) => {
  const teile = Object.entries(inhalt || {}).filter(([k]) => INHALT[k]).map(([k, v]) => `${v} ${INHALT[k]}`);
  const tabellen = Object.keys(inhalt || {}).filter((k) => TABELLEN[k]).map((k) => TABELLEN[k]);
  if (tabellen.length) teile.push(`Tabellen: ${tabellen.join(', ')}`);
  return teile.join(' · ');
};

/** Projektakte (ZIP) eines Projekts: erstellen, herunterladen. Im Firmenabo enthalten – auch für normale Handwerksfirmen. */
export default function ProjektakteKarte({ projectId, className = '' }) {
  const [daten, setDaten] = useState(null);
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/projektakten`).then(setDaten).catch(() => setDaten({ projektakten: [], fehler: true })), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  // Läuft eine Akte im Hintergrund, alle 1,5 s nachfragen, bis sie fertig ist (oder fehlgeschlagen)
  const laeuft = (daten?.projektakten || []).some((a) => a.status === 'laeuft');
  useEffect(() => {
    if (!laeuft) return undefined;
    const t = setInterval(() => laden(), 1500);
    return () => clearInterval(t);
  }, [laeuft, laden]);
  const erstellen = async () => {
    setBusy('erstellen');
    try {
      const r = await api.post(`/api/projekte/${projectId}/projektakte`, {});
      toast.success(r.projektakte.status === 'laeuft' ? 'Projektakte wird im Hintergrund erstellt' : `Projektakte erstellt (${fmtGroesse(r.projektakte.size)})`);
      laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const holen = async (a) => { setBusy(a.id); try { await download(`/api/projektakten/${a.id}.zip`, a.dateiname); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  return (
    <Card className={`p-5 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h2 className="text-[16px] flex items-center gap-2"><FileArchive size={16} /> Vollständige Projektakte (ZIP)</h2>
        <Btn size="sm" onClick={erstellen} loading={busy === 'erstellen'}><Archive size={15} /> Projektakte erstellen</Btn>
      </div>
      <p className="text-[13px] text-[#6E6E73] mb-3">Arbeitszeiten mit Stundennachweisen je Monat, Fotos nach Mitarbeiter und Tag, Dokumente, Rechnungen, Unterschriften, eigene Angebote und Aufträge, Nachträge, Abnahmen, Protokoll und E-Mail-Nachweise – bei Projekten mit anderen Firmen zusätzlich alle für euch freigegebenen Unterlagen. Bereiche ohne Daten werden ausgelassen.</p>
      {!daten ? <p className="text-[13px] text-[#A1A1A6]">Wird geladen …</p> : daten.projektakten.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine Projektakte erstellt. Alle Archive findet ihr unter „Exporte → Projektarchive“ (Aufbewahrung {daten.aufbewahrung_jahre || 10} Jahre).</p> : (
        <ul className="divide-y divide-black/[0.06] text-[14px]">
          {daten.projektakten.map((a) => (
            <li key={a.id} className="py-2 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-medium flex items-center gap-2">{fmtZeit(a.created_at)}{a.status === 'fertig' || !a.status ? ` · ${fmtGroesse(a.size)}` : ''} · {a.created_by_name}{a.status === 'laeuft' && <span className="inline-flex items-center gap-1 text-[11px] font-semibold rounded-full bg-[#E8F0FE] text-[#1D4ED8] px-2 py-0.5" data-testid="akte-laeuft"><Loader2 size={11} className="animate-spin" /> {a.fortschritt || 'läuft'}</span>}{a.status === 'fehler' && <span className="text-[11px] font-semibold rounded-full bg-[#FDE8E8] text-[#C41E3A] px-2 py-0.5">Fehlgeschlagen</span>}{a.manifest_eintraege > 0 && <span className="inline-flex items-center gap-1 text-[11px] text-[#1B7F3B]" title="manifest.json mit SHA-256-Prüfsummen und 00_Index.pdf enthalten"><ShieldCheck size={12} /> Prüfsummen</span>}</div>
                <div className="text-[12px] text-[#6E6E73] truncate">{a.status === 'fehler' ? a.fehler : (inhaltText(a.inhalt) || (a.status === 'laeuft' ? 'wird zusammengestellt …' : 'leer'))}{a.hinweise?.length ? ` · ${a.hinweise.length} Hinweise` : ''}</div>
              </div>
              <Btn size="sm" variant="soft" onClick={() => holen(a)} loading={busy === a.id} disabled={a.status === 'laeuft' || a.status === 'fehler'}><Download size={14} /> ZIP</Btn>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Alle Projektarchive der Firma (Exporte-Seite): herunterladen, Aufbewahrungsfrist, Löschen durch den Inhaber. */
export function ProjektarchiveKarte({ className = '' }) {
  const { isInhaber } = useAuth();
  const [daten, setDaten] = useState(null);
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get('/api/projektakten').then(setDaten).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  const holen = async (a) => { setBusy(a.id); try { await download(`/api/projektakten/${a.id}.zip`, a.dateiname); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const loeschen = async (a) => {
    const frueh = !a.ablauf_erreicht;
    if (!window.confirm(frueh ? `Die Aufbewahrungsfrist läuft bis ${fmtDate(fromKey(a.aufbewahren_bis))}. Archiv „${a.project_name}“ trotzdem löschen? Vorher eine Kopie sichern.` : `Archiv „${a.project_name}“ löschen?`)) return;
    setBusy(a.id);
    try { await api.del(`/api/projektakten/${a.id}${frueh ? '?erzwingen=true' : ''}`); toast.success('Archiv gelöscht'); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  return (
    <Card className={`p-5 space-y-3 ${className}`}>
      <h2 className="text-[17px] flex items-center gap-2"><FileArchive size={18} /> Projektarchive</h2>
      <p className="text-[13px] text-[#6E6E73]">Vollständige Projektakten (ZIP) aller Projekte. Erstellen unter „Projekt → Akte → Projektakte erstellen“. Aufbewahrung {daten?.aufbewahrung_jahre || 10} Jahre (Rechnungen und Belege nach § 147 AO); enthält personenbezogene Daten – nur verschlüsselt aufbewahren.</p>
      {!daten ? <p className="text-[13px] text-[#A1A1A6]">Wird geladen …</p> : daten.projektakten.length === 0 ? <Empty icon={Archive} title="Noch keine Projektarchive" /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-3 font-medium">Projekt</th><th className="py-1 pr-3 font-medium">Erstellt</th><th className="py-1 pr-3 font-medium">Größe</th><th className="py-1 pr-3 font-medium">Aufbewahren bis</th><th className="py-1 font-medium" /></tr></thead>
            <tbody>{daten.projektakten.map((a) => (
              <tr key={a.id} className="border-t border-black/[0.06]">
                <td className="py-1.5 pr-3"><div className="font-medium">{a.project_name}</div><div className="text-[11px] text-[#86868B]">{a.rolle === 'eigentuemer' ? 'eigenes Projekt' : 'Projekt eines Auftraggebers'} · {inhaltText(a.inhalt)}</div></td>
                <td className="py-1.5 pr-3 whitespace-nowrap">{fmtZeit(a.created_at)}<div className="text-[11px] text-[#86868B]">{a.created_by_name}</div></td>
                <td className="py-1.5 pr-3 whitespace-nowrap">{a.status === 'laeuft' ? 'läuft …' : a.status === 'fehler' ? 'Fehler' : fmtGroesse(a.size)}</td>
                <td className="py-1.5 pr-3 whitespace-nowrap">{a.aufbewahren_bis ? fmtDate(fromKey(a.aufbewahren_bis)) : '–'}</td>
                <td className="py-1.5 whitespace-nowrap text-right"><Btn size="sm" variant="soft" onClick={() => holen(a)} loading={busy === a.id}><Download size={14} /> ZIP</Btn>{isInhaber && <Btn size="sm" variant="ghost" className="ml-1" onClick={() => loeschen(a)} disabled={busy === a.id}><Trash2 size={14} /></Btn>}</td>
              </tr>
            ))}</tbody>
          </table>
          <p className="text-[12px] text-[#86868B] mt-2">Gesamt {fmtGroesse(daten.gesamt_bytes || 0)}.</p>
        </div>
      )}
    </Card>
  );
}
