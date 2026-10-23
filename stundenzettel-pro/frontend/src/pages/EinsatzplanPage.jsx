import React, { useCallback, useEffect, useState } from 'react';
import { Bell, CalendarDays, CheckCircle2, Clock3, MapPin, Plus, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Field, Select, TextArea, TextInput } from '../components/ui';
import { api, download } from '../lib/api';
import { useAuth } from '../lib/auth';
import { toKey, addDays } from '../lib/dates';

const WOCHENTAGE = [['Mo', 0], ['Di', 1], ['Mi', 2], ['Do', 3], ['Fr', 4], ['Sa', 5], ['So', 6]];
const minuten = (n) => n === null || n === undefined ? '–' : `${Math.floor(n / 60)} h ${String(n % 60).padStart(2, '0')} min`;
const geld = (n) => Number(n || 0).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });
const titelTag = (key) => new Date(key + 'T12:00:00').toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });

function Freigabe({ einsatz, onChanged }) {
  const actual = einsatz.stempel || {};
  const [offen, setOffen] = useState(false);
  const [start, setStart] = useState(actual.start_time || einsatz.start_time);
  const [ende, setEnde] = useState(actual.end_time || einsatz.end_time);
  const [pause, setPause] = useState(einsatz.pause_minutes || 0);
  const [grund, setGrund] = useState('');
  const [bestaetigt, setBestaetigt] = useState(false);
  const [busy, setBusy] = useState(false);
  if (einsatz.status === 'freigegeben') {
    return <p className="text-[12px] text-[#187A42] flex gap-1 items-center"><CheckCircle2 size={14} /> {minuten(einsatz.freigabe?.net_minutes)} vom Inhaber freigegeben</p>;
  }
  if (!offen) return <Btn variant="soft" size="sm" onClick={() => setOffen(true)}>Arbeitszeit prüfen</Btn>;
  const speichern = async () => {
    setBusy(true);
    try {
      await api.post(`/api/einsatzplan/${einsatz.id}/freigabe`, { start_time: start, end_time: ende, pause_minutes: Number(pause), grund, arbeitsleistung_bestaetigt: bestaetigt });
      toast.success('Arbeitszeit mit Änderungsnachweis freigegeben');
      onChanged();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-2xl border border-[#E3E3E7] p-3 space-y-3 mt-2">
      <p className="text-[12px] text-[#6E6E73]">Das Stempelergebnis wird nicht überschrieben. Hier wird eine gesondert freigegebene Abrechnungszeit gespeichert.</p>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Von"><TextInput type="time" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
        <Field label="Bis"><TextInput type="time" value={ende} onChange={(e) => setEnde(e.target.value)} /></Field>
        <Field label="Pause, min"><TextInput type="number" min="0" max="600" value={pause} onChange={(e) => setPause(e.target.value)} /></Field>
      </div>
      <Field label="Begründung bei Abweichung oder fehlendem Stempel"><TextArea rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} placeholder="Beispiel: Vor Ort pünktlich begonnen; Stempeluhr später geöffnet" /></Field>
      <label className="flex items-start gap-2 text-[13px]">
        <input type="checkbox" checked={bestaetigt} onChange={(e) => setBestaetigt(e.target.checked)} className="mt-1" />
        Ich habe die tatsächlich geleistete Arbeitszeit geprüft und bestätige eine eventuelle Abweichung.
      </label>
      <div className="flex flex-wrap gap-2 justify-end">
        <Btn variant="soft" size="sm" onClick={() => setOffen(false)}>Abbrechen</Btn>
        <Btn size="sm" onClick={speichern} loading={busy}>Freigeben</Btn>
      </div>
    </div>
  );
}

export default function EinsatzplanPage() {
  const { isInhaber } = useAuth();
  const heute = new Date();
  const [von, setVon] = useState(toKey(heute));
  const [bis, setBis] = useState(toKey(addDays(heute, 13)));
  const [plaene, setPlaene] = useState(null);
  const [projekte, setProjekte] = useState([]);
  const [mitarbeiter, setMitarbeiter] = useState([]);
  const [analyse, setAnalyse] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    project_id: '', user_ids: [], from_date: toKey(addDays(heute, 1)),
    to_date: toKey(addDays(heute, 7)), weekdays: [0, 1, 2, 3, 4],
    start_time: '08:00', end_time: '16:00', pause_minutes: 30, address: '', note: '',
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const laden = useCallback(async () => {
    try {
      const r = await api.get(`/api/einsatzplan?von=${von}&bis=${bis}`);
      setPlaene(r.einsatzplaene);
      if (isInhaber) {
        const a = await api.get(`/api/einsatzplan/auswertung?von=${von}&bis=${bis}`);
        setAnalyse(a);
      }
    } catch (err) { toast.error(err.message); setPlaene([]); }
  }, [von, bis, isInhaber]);

  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    if (!isInhaber) return;
    Promise.all([api.get('/api/projekte'), api.get('/api/mitarbeiter')])
      .then(([p, m]) => {
        setProjekte(p.projekte || []);
        setMitarbeiter((m.mitarbeiter || []).filter((u) => u.active !== false));
        setForm((f) => ({ ...f, project_id: f.project_id || p.projekte?.[0]?.id || '' }));
      })
      .catch((err) => toast.error(err.message));
  }, [isInhaber]);

  const toggleMitarbeiter = (id) => setForm((f) => ({
    ...f, user_ids: f.user_ids.includes(id) ? f.user_ids.filter((i) => i !== id) : [...f.user_ids, id],
  }));
  const toggleWochentag = (tag) => setForm((f) => ({
    ...f, weekdays: f.weekdays.includes(tag) ? f.weekdays.filter((x) => x !== tag) : [...f.weekdays, tag].sort(),
  }));
  const speichern = async () => {
    if (!form.project_id || !form.user_ids.length || !form.weekdays.length) {
      toast.error('Bitte Projekt, Mitarbeiter und Wochentage wählen.');
      return;
    }
    setBusy(true);
    try {
      const r = await api.post('/api/einsatzplan/serie', { ...form, pause_minutes: Number(form.pause_minutes) });
      toast.success(`${r.angelegt_oder_aktualisiert} Einsätze geplant`);
      setVon(form.from_date);
      setBis(form.to_date);
      laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  return (
    <Layout title={isInhaber ? 'Einsatzplanung' : 'Meine Einsätze'} subtitle={isInhaber ? 'Mitarbeiter einteilen, Zeiten vergleichen und nur nach Prüfung freigeben.' : 'Deine persönlichen Einsatzorte und Schichten – keine Zeiten anderer Mitarbeiter.'} wide>
      {isInhaber && (
        <Card className="p-5 mb-5 space-y-4">
          <h2 className="font-semibold text-[17px] flex items-center gap-2"><Plus size={18} /> Mitarbeiter einteilen</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Projekt"><Select className="w-full" value={form.project_id} onChange={set('project_id')}>
              <option value="">Bitte wählen</option>{projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select></Field>
            <Field label="Von"><TextInput type="date" value={form.from_date} onChange={set('from_date')} /></Field>
            <Field label="Bis"><TextInput type="date" value={form.to_date} onChange={set('to_date')} /></Field>
            <Field label="Beginn"><TextInput type="time" value={form.start_time} onChange={set('start_time')} /></Field>
            <Field label="Ende"><TextInput type="time" value={form.end_time} onChange={set('end_time')} /></Field>
            <Field label="Pause in Minuten"><TextInput type="number" min="0" max="600" value={form.pause_minutes} onChange={set('pause_minutes')} /></Field>
          </div>
          <div className="space-y-2">
            <p className="text-[13px] font-medium">Wochentage</p>
            <div className="flex flex-wrap gap-2">{WOCHENTAGE.map(([name, tag]) => (
              <label key={tag} className={`rounded-full px-3 py-2 text-[13px] cursor-pointer ${form.weekdays.includes(tag) ? 'bg-[#1D1D1F] text-white' : 'bg-black/[0.06]'}`}>
                <input className="sr-only" type="checkbox" checked={form.weekdays.includes(tag)} onChange={() => toggleWochentag(tag)} />{name}
              </label>
            ))}</div>
          </div>
          <div className="space-y-2">
            <p className="text-[13px] font-medium">Mitarbeiter zuordnen</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">{mitarbeiter.map((m) => (
              <label key={m.id} className="flex items-center gap-2 rounded-xl bg-[#F5F5F7] p-3 text-[13px]">
                <input type="checkbox" checked={form.user_ids.includes(m.id)} onChange={() => toggleMitarbeiter(m.id)} />{m.name}
              </label>
            ))}</div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Einsatzadresse (optional: sonst Projektadresse)"><TextInput value={form.address} onChange={set('address')} placeholder="Straße, Hausnummer, Stadt" /></Field>
            <Field label="Information für Mitarbeiter"><TextInput value={form.note} onChange={set('note')} placeholder="Treffpunkt, Zugang, Material" /></Field>
          </div>
          <div className="flex justify-between gap-3 items-center flex-wrap">
            <p className="text-[12px] text-[#6E6E73] flex items-center gap-1"><Bell size={14} /> Abends ab 18 Uhr erscheint eine In-App-Erinnerung für den Folgetag.</p>
            <Btn onClick={speichern} loading={busy}><CalendarDays size={16} /> Einsätze speichern</Btn>
          </div>
        </Card>
      )}
      <div className="flex items-end justify-between gap-3 mb-4 flex-wrap">
        <h2 className="text-[18px] font-semibold">{isInhaber ? 'Geplante Einsätze und Zeitprüfung' : 'Dein Dienstplan'}</h2>
        <div className="flex gap-2">
          <Field label="Von"><TextInput type="date" value={von} onChange={(e) => setVon(e.target.value)} /></Field>
          <Field label="Bis"><TextInput type="date" value={bis} onChange={(e) => setBis(e.target.value)} /></Field>
        </div>
      </div>
      {plaene === null ? <Ladeanzeige /> : plaene.length === 0 ? <Card className="p-6 text-[14px] text-[#6E6E73]">Für diesen Zeitraum sind keine Einsätze geplant.</Card> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {plaene.map((p) => (
            <Card className="p-4 space-y-3" key={p.id}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-[12px] text-[#6E6E73]">{titelTag(p.date)} · {p.mitarbeiter || 'Dein Einsatz'}</p>
                  <h3 className="font-semibold text-[16px]">{p.projekt?.name}</h3>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${p.status === 'freigegeben' ? 'bg-[#EAF7ED] text-[#187A42]' : 'bg-[#F5F5F7] text-[#606067]'}`}>{p.status === 'freigegeben' ? 'Freigegeben' : 'Geplant'}</span>
              </div>
              <p className="text-[13px] flex gap-2 items-center"><Clock3 size={15} /> Geplant {p.start_time}–{p.end_time} · {p.pause_minutes} min Pause ({minuten(p.planned_minutes)} netto)</p>
              <p className="text-[13px] flex gap-2 items-center"><MapPin size={15} /> {p.projekt?.address || 'Adresse beim Chef erfragen'}</p>
              {p.note && <p className="text-[13px] text-[#6E6E73]">{p.note}</p>}
              {isInhaber ? (
                <div className="space-y-2">
                  <p className="text-[13px]">{p.stempel?.vorhanden
                    ? `Gestempelt ${p.stempel.start_time}–${p.stempel.end_time} · ${minuten(p.stempel.net_minutes)}`
                    : 'Kein Stempel vorhanden – nur geplanter Sollwert, noch keine bestätigte Arbeitszeit.'}</p>
                  {p.stempel?.spaet_minuten > 0 && <p className="text-[12px] text-[#995600]"><ShieldAlert size={13} className="inline" /> {p.stempel.spaet_minuten} Minuten nach geplantem Beginn gestempelt (kein Beweis verspäteten Erscheinens).</p>}
                  {p.stempel?.frueher_minuten > 0 && <p className="text-[12px] text-[#995600]">{p.stempel.frueher_minuten} Minuten vor geplantem Ende ausgestempelt.</p>}
                  <Freigabe key={p.id + p.status} einsatz={p} onChanged={laden} />
                </div>
              ) : <p className="text-[12px] text-[#6E6E73]">Stempelung: {p.stempel?.vorhanden ? `${p.stempel.start_time}–${p.stempel.end_time}` : 'noch nicht erfasst'}</p>}
            </Card>
          ))}
        </div>
      )}
      {isInhaber && (
        <Card className="p-4 mt-5 space-y-3">
          <h2 className="text-[16px] font-semibold">Stundenzettel für Projektleitung oder Auftraggeber</h2>
          <p className="text-[13px] text-[#6E6E73]">Das PDF verwendet nur von dir freigegebene Zeiten. Es ersetzt weder rohe Stempelereignisse noch Pflichtnachweise.</p>
          <div className="flex flex-wrap gap-3">
            <Select value={form.project_id} onChange={set('project_id')}><option value="">Projekt wählen</option>{projekte.map((p) => <option value={p.id} key={p.id}>{p.name}</option>)}</Select>
            <Btn size="sm" disabled={!form.project_id} onClick={() => download(`/api/einsatzplan/stundenzettel.pdf?project_id=${encodeURIComponent(form.project_id)}&von=${von}&bis=${bis}`).catch((err) => toast.error(err.message))}>Freigegebenen Stundenzettel (PDF)</Btn>
          </div>
        </Card>
      )}
      {isInhaber && analyse?.projekte?.length > 0 && (
        <Card className="p-5 mt-5 space-y-3">
          <h2 className="text-[17px] font-semibold">Projekt-Auswertung (nur Inhaber)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] min-w-[650px]">
              <thead><tr className="text-left text-[#606067]"><th>Projekt</th><th>Geplant</th><th>Gestempelt</th><th>Berücksichtigt</th><th>Zu prüfen</th><th>Geschätzte Lohnkosten</th></tr></thead>
              <tbody>{analyse.projekte.map((p) => (
                <tr key={p.project_id} className="border-t border-black/[0.06]"><td className="py-2 font-medium">{p.projekt}</td><td>{minuten(p.geplant_minuten)}</td><td>{minuten(p.gestempelt_minuten)}</td><td>{minuten(p.beruecksichtigt_minuten)}</td><td>{p.noch_zu_pruefen}</td><td>{geld(p.lohnkosten_schaetzung)}</td></tr>
              ))}</tbody>
            </table>
          </div>
          {analyse.projekte.filter((p) => p.pauschale_netto !== undefined).map((p) => (
            <div key={p.project_id} className="rounded-xl bg-[#EAF7ED] p-3 text-[13px]">
              <strong>{p.projekt} – Pauschalauftrag:</strong> {geld(p.pauschale_netto)} netto,
              abzgl. bisher berücksichtigter direkter Lohnkosten: {geld(p.deckung_vor_nebenkosten)} übrig.
              <span className="block text-[12px] text-[#606067]">Kein endgültiger Gewinn: Material, Arbeitgebernebenkosten, Gemeinkosten, andere Zeiträume und weitere Kosten fehlen.</span>
            </div>
          ))}
          <p className="text-[12px] text-[#606067]">Nur eine Kostenschätzung aus hinterlegtem Stundenlohn. Arbeitgebernebenkosten und die endgültige Lohnabrechnung sind nicht enthalten. Geplante Stunden ohne Bestätigung zählen hier nicht als gearbeitet.</p>
        </Card>
      )}
    </Layout>
  );
}
