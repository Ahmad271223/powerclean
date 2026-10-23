import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Gavel, Plus } from 'lucide-react';
import { toast } from 'sonner';
import AusschreibungDialog from '../ausschreibung/AusschreibungDialog';
import { Btn, Card, Empty } from '../ui';
import { api } from '../../lib/api';
import { STATUS_CLS, fmtGeld, fristText } from '../../lib/ausschreibung';

/** Projektreiter (Eigentümer-Leitung): Ausschreibungen des Projekts mit Angebotszählern; neue Ausschreibung anlegen. */
export default function AusschreibungenTab({ projectId }) {
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [neu, setNeu] = useState(false);
  const laden = useCallback(() => api.get(`/api/projekte/${projectId}/ausschreibungen`).then(setD).catch((err) => toast.error(err.message)), [projectId]);
  useEffect(() => { laden(); }, [laden]);
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] text-[#6E6E73]">Je Gewerk oder Bauabschnitt eine Ausschreibung: als Entwurf anlegen, Unterlagen hochladen, Firmen einladen, veröffentlichen, Angebote vergleichen, vergeben.</p>
        <Btn onClick={() => setNeu(true)}><Plus size={17} /> Neue Ausschreibung</Btn>
      </div>
      {d.ausschreibungen.length === 0 ? <Card><Empty icon={Gavel} title="Noch keine Ausschreibung" text="Beispiel: Elektroinstallation, Trockenbau, Sanitär und Heizung – jede mit eigenen Fristen, Unterlagen und Angeboten." /></Card> : (
        <Card className="p-4"><ul className="divide-y divide-black/[0.06]">
          {d.ausschreibungen.map((a) => (
            <li key={a.id} className="py-2.5 flex flex-wrap items-center gap-3">
              <Link to={`/ausschreibungen/${a.id}`} className="flex-1 min-w-[220px]"><div className="text-[15px] font-semibold">{a.titel}</div><div className="text-[12px] text-[#6E6E73]">{a.nummer} · {a.gewerk} · {a.sichtbarkeit_name} · Frist {fristText(a)}{a.budget ? ` · Budget ${fmtGeld(a.budget)}` : ''}</div></Link>
              {a.zaehler && <span className="text-[12px] text-[#6E6E73]">{a.zaehler.angebote} Angebote{a.zaehler.neu ? ` (${a.zaehler.neu} neu)` : ''} · {a.zaehler.einladungen} eingeladen{a.zaehler.fragen_offen ? ` · ${a.zaehler.fragen_offen} offene Rückfragen` : ''}</span>}
              <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[a.status] || ''}`}>{a.status_name}</span>
            </li>
          ))}
        </ul></Card>
      )}
      <AusschreibungDialog open={neu} onOpenChange={setNeu} projectId={projectId} gewerke={d.gewerke} onSaved={(a) => navigate(`/ausschreibungen/${a.id}`)} />
    </div>
  );
}
