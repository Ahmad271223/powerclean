import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Empty } from '../ui';
import { api } from '../../lib/api';
import { STATUS_CLS, STATUS_NAMEN, fmtGeld, fmtMenge } from '../../lib/angebot';
import { fmtDate, fromKey } from '../../lib/dates';

/** Projekt → „Angebot & Auftrag“: der beauftragte Umfang (aus dem angenommenen Angebot) und alle Angebote zu diesem Projekt. */
export default function AuftragTab({ projekt }) {
  const navigate = useNavigate();
  const [liste, setListe] = useState(null);
  useEffect(() => {
    api.get(`/api/kundenangebote?project_id=${projekt.id}&alle=1`).then((r) => setListe(r.angebote)).catch((err) => { setListe([]); toast.error(err.message); });
  }, [projekt.id]);
  const auftrag = projekt.auftrag;
  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 className="text-[17px] flex items-center gap-2"><FileText size={17} /> Auftrag</h2>
          {!auftrag && <Btn size="sm" onClick={() => navigate(`/angebote?neu=1&project_id=${projekt.id}`)}><Plus size={15} /> Angebot für dieses Projekt</Btn>}
        </div>
        {auftrag ? (
          <>
            <div className="text-[14px]">Aus Angebot <button type="button" className="text-[#C41E3A] font-medium" onClick={() => navigate(`/angebote/${auftrag.angebot_id}`)}>{auftrag.nummer}{auftrag.version > 1 ? ` (Version ${auftrag.version})` : ''}</button>{auftrag.titel ? ` – ${auftrag.titel}` : ''}, angelegt am {auftrag.am ? fmtDate(fromKey(auftrag.am)) : '–'} von {auftrag.von_name || '–'}.</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
              <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Auftragswert netto</div><div className="text-[18px] font-semibold">{fmtGeld(auftrag.netto)}</div></div>
              <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Brutto</div><div className="text-[18px] font-semibold">{fmtGeld(auftrag.brutto)}</div></div>
              <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Abrechnung</div><div className="text-[18px] font-semibold">{auftrag.abrechnungsart === 'pauschal' ? 'Pauschal' : 'Nach Stunden'}</div></div>
              <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3"><div className="text-[12px] text-[#6E6E73]">Positionen</div><div className="text-[18px] font-semibold">{(auftrag.positionen || []).length}</div></div>
            </div>
            {auftrag.positionen?.length > 0 && (
              <table className="w-full text-[13px] mt-3">
                <thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="py-1 pr-2">Pos.</th><th className="py-1 pr-2">Leistung</th><th className="py-1 pr-2 text-right">Menge</th><th className="py-1 pr-2">Einheit</th><th className="py-1 text-right">Gesamt</th></tr></thead>
                <tbody>{auftrag.positionen.map((p, i) => <tr key={i} className="border-t border-black/[0.06]"><td className="py-1 pr-2 text-[#6E6E73]">{p.nr}</td><td className="py-1 pr-2">{p.text}</td><td className="py-1 pr-2 text-right">{fmtMenge(p.menge)}</td><td className="py-1 pr-2">{p.einheit}</td><td className="py-1 text-right">{fmtGeld(p.gesamt)}</td></tr>)}</tbody>
              </table>
            )}
          </>
        ) : <p className="text-[14px] text-[#6E6E73]">Noch kein Auftrag aus einem Angebot. Nach der Annahme eines Angebots legst du den Auftrag mit einem Klick hier ab – mit Auftragswert und Abrechnungsart für die Nachkalkulation.</p>}
      </Card>
      <Card className="p-5">
        <h2 className="text-[17px] mb-2">Angebote zu diesem Projekt</h2>
        {!liste ? <p className="text-[14px] text-[#6E6E73]">Lädt …</p> : liste.length === 0 ? <Empty icon={FileText} title="Keine Angebote" text="Angebote, die diesem Projekt zugeordnet sind, erscheinen hier." /> : (
          <ul className="divide-y divide-black/[0.06]">
            {liste.map((a) => (
              <li key={a.id} role="button" tabIndex={0} onClick={() => navigate(`/angebote/${a.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/angebote/${a.id}`)} className="py-2.5 flex items-center gap-3 cursor-pointer">
                <div className="min-w-0 flex-1"><div className="font-semibold text-[14px] truncate">{a.nummer}{a.version > 1 ? ` (v${a.version})` : ''}{a.titel ? ` – ${a.titel}` : ''}</div><div className="text-[12px] text-[#6E6E73]">{a.datum ? fmtDate(fromKey(a.datum)) : ''} · {fmtGeld(a.netto)} netto</div></div>
                <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[a.status] || ''}`}>{STATUS_NAMEN[a.status] || a.status}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
