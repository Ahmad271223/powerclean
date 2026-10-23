import React from 'react';
import { AlertTriangle, ClipboardList, Flag, Truck } from 'lucide-react';
import { Btn } from '../ui';

const BLOECKE = [
  ['aufgaben', 'Aufgaben', ClipboardList, 'bg-[#E8F0FE] text-[#1D4ED8]', (a) => `${a.start_time ? `${a.start_time} · ` : ''}${a.titel}`, (a) => [a.firma_name, a.bereich].filter(Boolean).join(' · ')],
  ['lieferungen', 'Lieferungen', Truck, 'bg-[#FFF4E5] text-[#B25E00]', (l) => `${l.zeitfenster_von ? `${l.zeitfenster_von} · ` : ''}${l.material}`, (l) => l.firma_name],
  ['meilensteine', 'Meilensteine', Flag, 'bg-[#EEE8FD] text-[#6D28D9]', (m) => m.titel, (m) => (m.erledigt ? 'erreicht' : m.notiz || '')],
  ['fristen', 'Mängel-Fristen', AlertTriangle, 'bg-[#FDE8E8] text-[#C41E3A]', (f) => f.beschreibung, (f) => f.firma_name],
];
const STATUS = { geplant: 'Geplant', zugewiesen: 'Zugewiesen', in_bearbeitung: 'In Bearbeitung', blockiert: 'Blockiert', eingereicht: 'Eingereicht', erledigt: 'Erledigt', abgenommen: 'Abgenommen',
  angefragt: 'Angefragt', bestaetigt: 'Bestätigt', unterwegs: 'Unterwegs', eingetroffen: 'Eingetroffen', entladen: 'Entladen', abgeschlossen: 'Abgeschlossen', verspaetet: 'Verspätet', storniert: 'Storniert',
  offen: 'Offen', behoben_gemeldet: 'Behoben gemeldet', in_pruefung: 'In Prüfung', erneut_geoeffnet: 'Erneut geöffnet' };
const ZIEL = { aufgaben: 'aufgaben', lieferungen: 'lieferungen', meilensteine: 'firmen', fristen: 'maengel' };

/** Im Tagesdialog: was die Plattform für diesen Tag kennt – Aufgaben, Lieferungen, Meilensteine, Mängel-Fristen. */
export default function PlattformTag({ daten, onTab }) {
  const bloecke = BLOECKE.filter(([k]) => (daten?.[k] || []).length > 0);
  if (!bloecke.length) return null;
  return (
    <div className="rounded-2xl bg-[#F5F5F7] p-4 space-y-3">
      {bloecke.map(([k, titel, Icon, cls, zeile, unter]) => (
        <div key={k}>
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <span className={`inline-flex items-center gap-1 text-[11px] font-semibold rounded-full px-2 py-0.5 ${cls}`}><Icon size={11} /> {titel} ({daten[k].length})</span>
            {onTab && <Btn size="sm" variant="ghost" onClick={() => onTab(ZIEL[k])}>Öffnen</Btn>}
          </div>
          <ul className="space-y-1">
            {daten[k].map((x) => (
              <li key={x.id} className="text-[13px] flex items-center gap-2 min-w-0">
                <span className="flex-1 min-w-0 truncate"><span className="font-medium">{zeile(x)}</span>{unter(x) ? <span className="text-[#6E6E73]"> · {unter(x)}</span> : null}</span>
                {x.status && <span className="text-[11px] text-[#6E6E73] shrink-0">{STATUS[x.status] || x.status}</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
