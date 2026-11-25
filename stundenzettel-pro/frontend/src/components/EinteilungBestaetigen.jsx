import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Ban, CalendarDays, Check, ChevronDown, Clock, HelpCircle, Info, MapPin, Plus, Sparkles, Users, X } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, TextInput, Toggle } from './ui';
import { api } from '../lib/api';

const QUELLEN = { apple: 'Apple-KI auf diesem iPhone', mistral: 'KI auf dem Server (Mistral)', regeln: 'festen Regeln (ohne KI)' };
const TAGE = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
const tagKurz = (iso) => { const d = new Date(`${iso}T12:00:00`); return `${TAGE[d.getDay()]} ${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.`; };
const vorname = (name) => (name || '').split(' ')[0] || name;
// lokales Datum (toISOString wäre UTC – kurz nach Mitternacht sonst „gestern“)
const heuteIso = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const minuten = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };

/** Nettodauer in Minuten; Ende vor Beginn = über Mitternacht (wie die Plantafel). */
export function dauerMinuten(start, ende, pause) {
  if (!/^\d{2}:\d{2}$/.test(start || '') || !/^\d{2}:\d{2}$/.test(ende || '')) return null;
  let d = minuten(ende) - minuten(start);
  if (d <= 0) d += 24 * 60;
  return Math.max(0, d - (Number(pause) || 0));
}
const dauerText = (min) => `${Math.floor(min / 60)}:${String(min % 60).padStart(2, '0')} Std.`;

/** Eine Zeile der Karte: groß, per Tipp aufklappbar zum Ändern. */
function Feld({ icon: Icon, titel, wert, pruefen, offen, onTipp, children }) {
  return (
    <div className="border-b border-black/[0.06] last:border-0">
      <button type="button" onClick={onTipp} className="w-full flex items-center gap-3 py-3 text-left min-h-[56px]" aria-expanded={offen}
        aria-label={`${titel}: ${wert || 'fehlt'}${pruefen ? ' (bitte prüfen)' : ''} – ändern`}>
        <Icon size={20} className="text-[#C41E3A] shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="text-[12px] text-[#6E6E73] flex items-center gap-1.5">{titel}{pruefen && <span className="rounded-full bg-[#FFF4E5] text-[#B25E00] px-1.5 text-[11px] font-semibold">bitte prüfen</span>}</span>
          <span className="block text-[16px] font-semibold leading-snug">{wert || <span className="text-[#C41E3A]">fehlt – antippen</span>}</span>
        </span>
        <ChevronDown size={18} className={`text-[#86868B] shrink-0 transition-transform ${offen ? 'rotate-180' : ''}`} />
      </button>
      {offen && <div className="pb-3">{children}</div>}
    </div>
  );
}

const Wahl = ({ aktiv, onClick, children }) => (
  <button type="button" onClick={onClick}
    className={`min-h-[48px] px-4 rounded-xl text-[15px] font-medium border transition-colors ${aktiv ? 'bg-[#C41E3A] text-white border-[#C41E3A]' : 'bg-white border-black/[0.12] active:bg-black/[0.04]'}`}>{children}</button>
);

/**
 * Bestätigungsfenster (Schritt 5): Vorschlag als Karte, jedes Feld per Tipp änderbar, Rückfragen als Auswahl, Konflikte vom Server
 * (nach jeder Änderung neu geprüft). „Einteilen & benachrichtigen“ speichert über die normale Plantafel-Route – erst dann geht die Push raus.
 */
export default function EinteilungBestaetigen({ vorschlag: v, mitarbeiter = [], projekte = [], onEingeteilt, onVerwerfen }) {
  const [personen, setPersonen] = useState(() => (v.mitarbeiter || []).filter((p) => p.id).map((p) => ({ id: p.id, name: p.name })));
  const [fragen, setFragen] = useState(() => (v.rueckfragen || []).filter((r) => ['mitarbeiter', 'projekt'].includes(r.feld) && r.optionen?.length));
  const [projekt, setProjekt] = useState(v.projekt || null);
  const [adresse, setAdresse] = useState(v.adresse || '');
  const [tage, setTage] = useState(v.tage || []);
  const [start, setStart] = useState(v.start_time || '07:00');
  const [ende, setEnde] = useState(v.end_time || '16:00');
  const [pause, setPause] = useState(v.pause_minutes ?? 30);
  const [pruefen, setPruefen] = useState(() => new Set(v.unsicher || []));
  const [offen, setOffen] = useState(null);
  const [pruefung, setPruefung] = useState({ konflikte: v.konflikte || [], blockiert: (v.konflikte || []).some((k) => k.art === 'ueberschneidung'), trotzdem_noetig: (v.konflikte || []).some((k) => k.art === 'abwesenheit') });
  const [trotzdem, setTrotzdem] = useState(false);
  const [nachtOk, setNachtOk] = useState(false);       // Ende vor Beginn nur mit bewusster Bestätigung (sonst meist ein Versprecher)
  const [zeitGeaendert, setZeitGeaendert] = useState(false);
  const [neuerTag, setNeuerTag] = useState('');
  const [sendet, setSendet] = useState(false);
  const [fehler, setFehler] = useState('');

  const geaendert = (feld) => setPruefen((s) => { const n = new Set(s); n.delete(feld); if (feld === 'zeit') { n.delete('startzeit'); n.delete('endzeit'); } return n; });
  const umschalten = (feld) => setOffen((o) => (o === feld ? null : feld));

  // Konflikte nach jeder Änderung neu prüfen (kurz verzögert)
  const schluessel = JSON.stringify([personen.map((p) => p.id), tage, start, ende]);
  useEffect(() => {
    if (!personen.length || !tage.length || !start || !ende) { setPruefung({ konflikte: [], blockiert: false, trotzdem_noetig: false }); return undefined; }
    const t = setTimeout(() => {
      setPruefung((alt) => ({ ...alt, laeuft: true }));
      api.post('/api/sprachplanung/pruefen', { user_ids: personen.map((p) => p.id), dates: tage, start_time: start, end_time: ende })
        .then(setPruefung)
        // Prüfung fehlgeschlagen: nicht so tun, als gäbe es keine Konflikte – Speichern sperren, bis die Prüfung klappt
        .catch((err) => setPruefung({ konflikte: [], blockiert: true, trotzdem_noetig: false, fehler: err.message || 'Prüfung nicht möglich.' }));
    }, 350);
    return () => clearTimeout(t);
  }, [schluessel]); // eslint-disable-line react-hooks/exhaustive-deps

  const person = (u) => {
    setPersonen((liste) => (liste.some((p) => p.id === u.id) ? liste.filter((p) => p.id !== u.id) : [...liste, { id: u.id, name: u.name }]));
    geaendert('mitarbeiter');
  };
  const projektWaehlen = (p) => {
    if (!adresse || adresse === projekt?.address) setAdresse(p.address || '');
    setProjekt({ id: p.id, name: p.name, address: p.address || '' });
    geaendert('projekt');
  };
  const frageBeantworten = (frage, option) => {
    if (frage.feld === 'mitarbeiter') { if (!personen.some((p) => p.id === option.id)) setPersonen((l) => [...l, { id: option.id, name: option.name }]); geaendert('mitarbeiter'); }
    else projektWaehlen(option);
    setFragen((f) => f.filter((x) => x !== frage));
  };
  const tagHinzu = () => {
    if (!neuerTag || tage.includes(neuerTag)) return;
    setTage((t) => [...t, neuerTag].sort()); setNeuerTag(''); geaendert('zeitraum');
  };

  const offeneFragen = fragen.length > 0;
  const zeitOk = /^\d{2}:\d{2}$/.test(start) && /^\d{2}:\d{2}$/.test(ende) && start !== ende;
  const nacht = zeitOk && ende < start;
  const netto = dauerMinuten(start, ende, pause);
  const bereit = projekt && personen.length && tage.length && zeitOk && (!nacht || nachtOk) && !offeneFragen && !pruefung.laeuft && !pruefung.blockiert && (!pruefung.trotzdem_noetig || trotzdem);
  const knopf = personen.length === 1 ? `Einteilen & ${vorname(personen[0].name)} benachrichtigen` : `Einteilen & ${personen.length || ''} Mitarbeiter benachrichtigen`.replace('  ', ' ');
  const tageText = useMemo(() => (tage.length ? (tage.length > 3 ? `${tagKurz(tage[0])} – ${tagKurz(tage[tage.length - 1])} (${tage.length} Tage)` : tage.map(tagKurz).join(', ')) : ''), [tage]);
  const grund = !projekt ? 'Projekt fehlt.' : !personen.length ? 'Mitarbeiter fehlt.' : !tage.length ? 'Tage fehlen.' : !zeitOk ? 'Uhrzeit prüfen.'
    : (nacht && !nachtOk) ? 'Ende liegt vor Beginn: Uhrzeit ändern oder Nachtschicht bestätigen.' : offeneFragen ? 'Bitte zuerst die Rückfrage beantworten.' : pruefung.fehler ? `Konflikte konnten nicht geprüft werden: ${pruefung.fehler}` : pruefung.laeuft ? 'Konflikte werden geprüft …' : pruefung.blockiert ? 'Überschneidung: Person oder Tag ändern.' : (pruefung.trotzdem_noetig && !trotzdem) ? 'Abwesenheit: bewusst „trotzdem einteilen“ wählen.' : '';

  const einteilen = async () => {
    setSendet(true); setFehler('');
    try {
      const r = await api.post('/api/einsatzplan', {
        project_id: projekt.id, user_ids: personen.map((p) => p.id), dates: tage, start_time: start, end_time: ende, pause_minutes: Number(pause) || 0,
        address: adresse && adresse !== projekt.address ? adresse : '', erzwingen: trotzdem,
      });
      const namen = personen.map((p) => vorname(p.name)).join(', ');
      toast.success(`Eingeteilt: ${r.einsaetze.length} ${r.einsaetze.length === 1 ? 'Einsatz' : 'Einsätze'}. ${namen} ${personen.length > 1 ? 'werden' : 'wird'} benachrichtigt.`);
      onEingeteilt?.(r);
    } catch (err) {
      setFehler(err.message);
      api.post('/api/sprachplanung/pruefen', { user_ids: personen.map((p) => p.id), dates: tage, start_time: start, end_time: ende })
        .then(setPruefung).catch((e) => setPruefung({ konflikte: [], blockiert: true, trotzdem_noetig: false, fehler: e.message }));
    }
    setSendet(false);
  };

  return (
    <div className="mt-4 rounded-2xl bg-[#F5F5F7] p-3">
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-[12px] text-[#6E6E73]">Vorschlag · zerlegt mit {QUELLEN[v.quelle] || v.quelle}</span>
        {onVerwerfen && <button type="button" onClick={onVerwerfen} className="text-[13px] text-[#6E6E73] flex items-center gap-1 min-h-[40px] px-1"><X size={14} /> Verwerfen</button>}
      </div>

      {fragen.map((f, i) => (
        <div key={`f${i}`} className="rounded-xl bg-white border border-[#C41E3A]/25 p-3 mb-2">
          <div className="flex gap-2 text-[15px] font-semibold"><HelpCircle size={18} className="text-[#C41E3A] mt-0.5 shrink-0" />{f.frage}</div>
          <div className="flex flex-wrap gap-2 mt-2">
            {f.optionen.map((o) => <Wahl key={o.id} onClick={() => frageBeantworten(f, o)}>{o.name}</Wahl>)}
            <Wahl onClick={() => setFragen((alle) => alle.filter((x) => x !== f))}>Keiner davon</Wahl>
          </div>
        </div>
      ))}

      <div className="rounded-xl bg-white px-3">
        <Feld icon={Users} titel="Mitarbeiter" wert={personen.map((p) => p.name).join(', ')} pruefen={pruefen.has('mitarbeiter')} offen={offen === 'mitarbeiter'} onTipp={() => umschalten('mitarbeiter')}>
          <div className="flex flex-wrap gap-2">{mitarbeiter.map((m) => <Wahl key={m.id} aktiv={personen.some((p) => p.id === m.id)} onClick={() => person(m)}>{m.name}</Wahl>)}</div>
        </Feld>
        <Feld icon={Sparkles} titel="Projekt" wert={projekt?.name} pruefen={pruefen.has('projekt')} offen={offen === 'projekt'} onTipp={() => umschalten('projekt')}>
          <div className="flex flex-wrap gap-2">{projekte.map((p) => <Wahl key={p.id} aktiv={projekt?.id === p.id} onClick={() => { projektWaehlen(p); setOffen(null); }}>{p.name}</Wahl>)}</div>
        </Feld>
        <Feld icon={MapPin} titel="Adresse" wert={adresse} pruefen={pruefen.has('standort')} offen={offen === 'adresse'} onTipp={() => umschalten('adresse')}>
          <TextInput value={adresse} onChange={(e) => { setAdresse(e.target.value); geaendert('standort'); }} placeholder="Straße, Ort" className="h-12 text-[16px]" />
          {projekt?.address && adresse !== projekt.address && <button type="button" className="text-[13px] text-[#C41E3A] mt-2 min-h-[40px]" onClick={() => { setAdresse(projekt.address); geaendert('standort'); }}>Projektadresse nehmen: {projekt.address}</button>}
        </Feld>
        <Feld icon={CalendarDays} titel="Tage" wert={tageText} pruefen={pruefen.has('zeitraum')} offen={offen === 'tage'} onTipp={() => umschalten('tage')}>
          <div className="flex flex-wrap gap-2">
            {tage.map((t) => (
              <span key={t} className="inline-flex items-center gap-1 min-h-[44px] pl-3 pr-1 rounded-xl bg-[#F5F5F7] text-[15px] font-medium">
                {tagKurz(t)}<button type="button" onClick={() => { setTage((x) => x.filter((y) => y !== t)); geaendert('zeitraum'); }} className="w-9 h-9 flex items-center justify-center" aria-label={`${tagKurz(t)} entfernen`}><X size={16} /></button>
              </span>
            ))}
          </div>
          <div className="flex gap-2 mt-2">
            <input type="date" min={heuteIso()} value={neuerTag} onChange={(e) => setNeuerTag(e.target.value)} className="flex-1 h-12 rounded-xl border border-black/[0.12] px-3 text-[16px] bg-white" aria-label="Tag hinzufügen" />
            <Btn variant="soft" className="h-12" onClick={tagHinzu} disabled={!neuerTag}><Plus size={16} /> Tag</Btn>
          </div>
        </Feld>
        <Feld icon={Clock} titel="Uhrzeit" wert={`${start}–${ende} Uhr · ${pause} Min. Pause${netto != null ? ` · ${dauerText(netto)}` : ''}`} pruefen={pruefen.has('startzeit') || pruefen.has('endzeit') || nacht} offen={offen === 'zeit'} onTipp={() => umschalten('zeit')}>
          <div className="grid grid-cols-3 gap-2">
            <label className="text-[12px] text-[#6E6E73]">Beginn<input type="time" aria-label="Beginn" value={start} onChange={(e) => { setStart(e.target.value); setNachtOk(false); setZeitGeaendert(true); geaendert('zeit'); }} className="w-full h-12 rounded-xl border border-black/[0.12] px-2 text-[16px] bg-white mt-1" /></label>
            <label className="text-[12px] text-[#6E6E73]">Ende<input type="time" aria-label="Ende" value={ende} onChange={(e) => { setEnde(e.target.value); setNachtOk(false); setZeitGeaendert(true); geaendert('zeit'); }} className="w-full h-12 rounded-xl border border-black/[0.12] px-2 text-[16px] bg-white mt-1" /></label>
            <label className="text-[12px] text-[#6E6E73]">Pause<select aria-label="Pause" value={pause} onChange={(e) => setPause(Number(e.target.value))} className="w-full h-12 rounded-xl border border-black/[0.12] px-2 text-[16px] bg-white mt-1">{[0, 15, 30, 45, 60].map((m) => <option key={m} value={m}>{m} Min.</option>)}</select></label>
          </div>
        </Feld>
      </div>

      {pruefung.konflikte.map((k, i) => (
        <div key={`k${i}`} className={`mt-2 flex gap-2 text-[14px] rounded-xl p-2.5 ${k.art === 'ueberschneidung' ? 'bg-[#FDE8E8] text-[#8a1528]' : k.art === 'abwesenheit' ? 'bg-[#FFF4E5] text-[#7A4100]' : 'bg-white text-[#6E6E73]'}`}>
          {k.art === 'ueberschneidung' ? <Ban size={16} className="mt-0.5 shrink-0" /> : k.art === 'abwesenheit' ? <AlertTriangle size={16} className="mt-0.5 shrink-0" /> : <Info size={16} className="mt-0.5 shrink-0" />}{k.text}
        </div>
      ))}
      {pruefung.trotzdem_noetig && <div className="mt-2 rounded-xl bg-white p-2"><Toggle checked={trotzdem} onChange={setTrotzdem} label="Trotzdem einteilen" hint="Abwesenheit bewusst überstimmen" /></div>}
      {nacht && (
        <div className="mt-2 rounded-xl bg-[#FFF4E5] text-[#7A4100] p-2.5 text-[14px]">
          <div className="flex gap-2"><AlertTriangle size={16} className="mt-0.5 shrink-0" />Ende {ende} liegt vor Beginn {start} – das wäre eine Nachtschicht bis {ende} Uhr am nächsten Morgen ({dauerText(netto)}).</div>
          <div className="mt-1 rounded-lg bg-white px-2"><Toggle checked={nachtOk} onChange={setNachtOk} label="Ja, Nachtschicht über Mitternacht" /></div>
        </div>
      )}
      {netto != null && netto > 600 && (
        <div className="mt-2 flex gap-2 text-[14px] rounded-xl p-2.5 bg-[#FFF4E5] text-[#7A4100]"><AlertTriangle size={16} className="mt-0.5 shrink-0" />Mehr als 10 Stunden Arbeitszeit am Tag – nach dem Arbeitszeitgesetz nur ausnahmsweise erlaubt.</div>
      )}
      {(v.hinweise || []).filter((h) => !(zeitGeaendert && h.startsWith('Keine Uhrzeit'))).map((h, i) => <p key={`h${i}`} className="mt-2 text-[13px] text-[#6E6E73]">{h}</p>)}
      {fehler && <p className="mt-2 text-[14px] text-[#C41E3A]" role="alert">{fehler}</p>}

      <Btn className="w-full mt-3 h-14 text-[17px]" onClick={einteilen} disabled={!bereit || sendet} loading={sendet}><Check size={19} /> {knopf}</Btn>
      {grund ? <p className="mt-2 text-[13px] text-[#B25E00] text-center">{grund}</p> : <p className="mt-2 text-[12px] text-[#86868B] text-center">Gespeichert wird erst jetzt – danach bekommt {personen.length === 1 ? vorname(personen[0].name) : 'jeder'} eine Push-Nachricht.</p>}
    </div>
  );
}
