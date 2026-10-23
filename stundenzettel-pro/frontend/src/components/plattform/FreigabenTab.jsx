import React, { useCallback, useEffect, useState } from 'react';
import { Share2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, IconBtn, Select, Toggle } from '../ui';
import { api } from '../../lib/api';
import { addDays, fmtDate, fromKey, isoWeek, monthWeeks, toKey } from '../../lib/dates';

/** Partnerseite: Wochen-Nachweise für den Auftraggeber freigeben und Namen in der Anwesenheit freischalten. */
export default function FreigabenTab({ project }) {
  const v = project.verknuepft || {};
  const heute = new Date();
  const wochen = [-1, 0].flatMap((m) => monthWeeks(heute.getFullYear(), heute.getMonth() + m)).map(toKey).filter((w, i, arr) => arr.indexOf(w) === i).reverse();
  const [woche, setWoche] = useState(wochen.find((w) => w <= toKey(heute)) || wochen[0]);
  const [d, setD] = useState(null);
  const [namen, setNamen] = useState(false);
  const [busy, setBusy] = useState(false);
  const laden = useCallback(() => Promise.all([api.get(`/api/projekte/${project.id}/freigaben`), api.get('/api/beteiligungen')]).then(([f, b]) => { setD(f); const mine = b.aktiv.find((x) => x.id === v.beteiligung_id); setNamen(!!mine?.freigaben?.namen); }).catch((err) => toast.error(err.message)), [project.id, v.beteiligung_id]);
  useEffect(() => { laden(); }, [laden]);
  const freigeben = async () => { setBusy(true); try { await api.post(`/api/projekte/${project.id}/freigaben`, { week_monday: woche }); toast.success('Woche freigegeben'); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(false); } };
  const zurueck = async (f) => { try { await api.del(`/api/projekte/${project.id}/freigaben/${f.id}`); laden(); } catch (err) { toast.error(err.message); } };
  const namenSetzen = async (wert) => { try { await api.put(`/api/beteiligungen/${v.beteiligung_id}/freigaben`, { namen: wert }); setNamen(wert); } catch (err) { toast.error(err.message); } };
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card className="p-5 space-y-3">
        <h2 className="text-[16px] flex items-center gap-2"><Share2 size={16} /> Wochen-Nachweis für {d.auftraggeber} freigeben</h2>
        <p className="text-[13px] text-[#6E6E73]">Der Auftraggeber sieht erst nach deiner Freigabe die Zeiten dieser Woche mit Namen und Kunden-Unterschrift. Lohndaten, Konten und Rechnungen bleiben immer bei euch.</p>
        <div className="flex gap-2 flex-wrap items-center">
          <Select value={woche} onChange={(e) => setWoche(e.target.value)}>{wochen.map((w) => <option key={w} value={w}>KW {isoWeek(fromKey(w)).week} · {fmtDate(fromKey(w))} – {fmtDate(addDays(fromKey(w), 6))}</option>)}</Select>
          <Btn onClick={freigeben} loading={busy} disabled={v.status === 'entfernt'}><Share2 size={15} /> Freigeben</Btn>
        </div>
        {d.freigaben.length > 0 && <ul className="divide-y divide-black/[0.06] text-[14px]">{d.freigaben.map((f) => <li key={f.id} className="py-2 flex items-center gap-2"><span className="flex-1">KW {isoWeek(fromKey(f.week_monday)).week} · ab {fmtDate(fromKey(f.week_monday))} <span className="text-[12px] text-[#6E6E73]">· {f.freigegeben_von}</span></span><IconBtn size={30} variant="danger" onClick={() => zurueck(f)} title="Freigabe zurückziehen"><Trash2 size={14} /></IconBtn></li>)}</ul>}
      </Card>
      <Card className="p-5 space-y-3">
        <h2 className="text-[16px]">Anwesenheit</h2>
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={namen} onChange={namenSetzen} label="Namen unserer Mitarbeiter in der Anwesenheitsübersicht zeigen" hint="Ohne Freigabe sieht der Auftraggeber nur Zahlen (eingestempelt, heute gearbeitet)." /></div>
      </Card>
    </div>
  );
}
