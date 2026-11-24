import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CalendarDays, Clock, HelpCircle, Loader2, MapPin, Mic, RotateCcw, Sparkles, Users, X } from 'lucide-react';
import { Btn, Card, TextArea } from './ui';
import { api } from '../lib/api';
import { aufnahmeAbbrechen, aufnahmeBeenden, aufnahmeStarten, geraetZerlegen, modellLaden, sprachFehler, spracheMoeglich, sprachStatus } from '../lib/sprache';

const BEISPIEL = '„Teile Nils an die Hauptstraße ein, Projekt Badsanierung Müller, von 7 bis 16 Uhr die ganze Woche.“';

/**
 * Einteilung per Sprache (Flag „sprachplanung“): großer Mikrofon-Knopf – gedrückt halten zum Sprechen, loslassen = fertig.
 * Der erkannte Text erscheint im Feld und lässt sich ändern. Im Browser (ohne App) wird nur getippt.
 * Schritt 3: nur Text. Den Einteilungsvorschlag (Schritt 4/5) übergibt `onText` später an den Vorschlag – gespeichert wird hier nichts.
 */
export default function SprachEinteilung({ onSchliessen }) {
  const nativ = spracheMoeglich();
  const [stand, setStand] = useState(null);            // Status des Bausteins
  const [phase, setPhase] = useState('bereit');         // bereit | laden | aufnahme | erkennen
  const [anteil, setAnteil] = useState(0);
  const [text, setText] = useState('');
  const [fehler, setFehler] = useState('');
  const [fragen, setFragen] = useState(false);          // Rückfrage vor dem ersten Download
  const [vorschlag, setVorschlag] = useState(null);     // Einteilungsvorschlag vom Server (nichts gespeichert)
  const [denkt, setDenkt] = useState(false);
  const start = useRef(0);
  const gedrueckt = useRef(false);

  useEffect(() => { if (nativ) sprachStatus().then(setStand).catch(() => setStand(null)); }, [nativ]);
  useEffect(() => () => { if (nativ) aufnahmeAbbrechen(); }, [nativ]);

  const laden = async () => {
    setFragen(false); setFehler(''); setPhase('laden'); setAnteil(0);
    try { await modellLaden(setAnteil); setStand(await sprachStatus()); setPhase('bereit'); }
    catch (err) { setFehler(sprachFehler(err)); setPhase('bereit'); }
  };

  const druecken = async (ev) => {
    ev.preventDefault();
    if (phase !== 'bereit') return;
    if (stand && stand.plattform === 'ios' && !stand.modellGeladen) { setFragen(true); return; }
    try { ev.currentTarget.setPointerCapture?.(ev.pointerId); } catch { /* ignore */ }
    gedrueckt.current = true;
    start.current = Date.now();
    setFehler('');
    setPhase('aufnahme');
    try {
      await aufnahmeStarten();
      if (!gedrueckt.current) loslassen();   // sehr kurz gedrückt: sofort beenden
    } catch (err) { gedrueckt.current = false; setFehler(sprachFehler(err)); setPhase('bereit'); }
  };

  const loslassen = async () => {
    if (!gedrueckt.current && phase !== 'aufnahme') return;
    gedrueckt.current = false;
    if (Date.now() - start.current < 600) {
      await aufnahmeAbbrechen();
      setPhase('bereit');
      setFehler('Knopf gedrückt halten, sprechen, dann loslassen.');
      return;
    }
    setPhase('erkennen');
    try {
      const r = await aufnahmeBeenden();
      setText((alt) => (alt.trim() ? `${alt.trim()} ${r.text}` : r.text));
    } catch (err) { setFehler(sprachFehler(err)); }
    setPhase('bereit');
  };

  // Satz → Vorschlag: erst Apple-KI auf dem iPhone (Felder), sonst zerlegt der Server (Mistral mit Flag „ki“ oder feste Regeln)
  const vorschlagHolen = async () => {
    setDenkt(true); setFehler('');
    try {
      const geraet = await geraetZerlegen(text.trim());
      const body = geraet ? { felder: geraet.felder, quelle: 'apple' } : { text: text.trim() };
      setVorschlag((await api.post('/api/sprachplanung/vorschlag', body)).vorschlag);
    } catch (err) { setFehler(err.message); }
    setDenkt(false);
  };

  const groesse = stand?.modellGroesseMB ? `${stand.modellGroesseMB} MB` : '';
  return (
    <Card className="p-4 mb-4 border border-[#C41E3A]/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-[16px]">Einteilung per Sprache</div>
          <div className="text-[13px] text-[#6E6E73]">{nativ ? 'Knopf gedrückt halten, sprechen, loslassen.' : 'In der App per Sprache – hier im Browser eintippen.'} Zum Beispiel: {BEISPIEL}</div>
        </div>
        {onSchliessen && <button type="button" onClick={onSchliessen} className="p-2 -m-2 text-[#6E6E73]" aria-label="Schließen"><X size={18} /></button>}
      </div>

      {nativ && (
        <div className="flex flex-col items-center my-4 select-none">
          <button type="button"
            onPointerDown={druecken} onPointerUp={loslassen} onPointerCancel={loslassen} onContextMenu={(e) => e.preventDefault()}
            disabled={phase === 'laden' || phase === 'erkennen'}
            style={{ touchAction: 'none', WebkitTouchCallout: 'none', WebkitUserSelect: 'none' }}
            aria-label="Gedrückt halten und Einteilung sprechen"
            className={`w-24 h-24 rounded-full flex items-center justify-center text-white shadow-lg transition-transform ${phase === 'aufnahme' ? 'bg-[#C41E3A] scale-110 animate-pulse' : 'bg-[#C41E3A] active:scale-105'} disabled:opacity-50`}>
            {phase === 'erkennen' ? <Loader2 size={38} className="animate-spin" /> : <Mic size={40} />}
          </button>
          <div className="text-[14px] font-medium mt-2 h-5">
            {phase === 'aufnahme' && 'Ich höre zu … loslassen = fertig'}
            {phase === 'erkennen' && 'Wird erkannt …'}
            {phase === 'laden' && `Sprachmodell wird geladen … ${Math.round(anteil * 100)} %`}
          </div>
          {phase === 'laden' && <div className="w-full max-w-xs h-2 rounded-full bg-black/[0.08] overflow-hidden mt-1"><div className="h-full bg-[#C41E3A] transition-all" style={{ width: `${Math.round(anteil * 100)}%` }} /></div>}
        </div>
      )}

      {fragen && (
        <div className="rounded-xl bg-[#FFF4E5] text-[#7A4100] p-3 text-[14px] my-3">
          <div className="font-semibold mb-1">Sprachmodell einmalig laden{groesse ? ` (${groesse})` : ''}?</div>
          <p>Die Erkennung läuft danach ganz auf diesem iPhone, auch ohne Netz. Am besten im WLAN laden.</p>
          <div className="flex gap-2 mt-2">
            <Btn size="sm" onClick={laden}>Jetzt laden</Btn>
            <Btn size="sm" variant="ghost" onClick={() => setFragen(false)}>Später</Btn>
          </div>
        </div>
      )}

      {fehler && <p className="text-[14px] text-[#C41E3A] my-2" role="alert">{fehler}</p>}

      <TextArea rows={3} value={text} onChange={(e) => { setText(e.target.value); setVorschlag(null); }} placeholder={nativ ? 'Hier erscheint, was erkannt wurde – zum Ändern antippen.' : 'Einteilung eintippen, z. B. Nils morgen von 7 bis 16 Uhr bei Müller'} className="text-[16px]" />
      <div className="flex items-center justify-between gap-2 mt-2">
        <span className="text-[12px] text-[#86868B]">Die Aufnahme bleibt auf dem Gerät und wird nicht gespeichert. Gespeichert wird erst eine bestätigte Einteilung.</span>
        {text && <Btn size="sm" variant="ghost" onClick={() => setText('')}><RotateCcw size={14} /> Leeren</Btn>}
      </div>
      {text.trim() && !vorschlag && (
        <Btn className="w-full mt-3 h-12 text-[16px]" onClick={vorschlagHolen} loading={denkt} disabled={denkt}><Sparkles size={17} /> Vorschlag erstellen</Btn>
      )}
      {vorschlag && <VorschlagAnzeige v={vorschlag} />}
    </Card>
  );
}

const QUELLEN = { apple: 'Apple-KI auf diesem iPhone', mistral: 'KI auf dem Server (Mistral)', regeln: 'festen Regeln (ohne KI)' };

function Zeile({ icon: Icon, titel, unsicher, children }) {
  return (
    <div className="flex gap-3 py-2 border-b border-black/[0.06] last:border-0">
      <Icon size={18} className="text-[#C41E3A] mt-0.5 shrink-0" />
      <div className="min-w-0">
        <div className="text-[12px] text-[#6E6E73] flex items-center gap-1.5">{titel}{unsicher && <span className="rounded-full bg-[#FFF4E5] text-[#B25E00] px-1.5 text-[11px] font-semibold">bitte prüfen</span>}</div>
        <div className="text-[15px] font-medium">{children}</div>
      </div>
    </div>
  );
}

/** Schritt 4: Vorschlag lesen (Rückfragen, Hinweise, Konflikte). Ändern und „Einteilen & benachrichtigen“ folgen in Schritt 5. */
function VorschlagAnzeige({ v }) {
  const u = new Set(v.unsicher || []);
  const personen = (v.mitarbeiter || []).map((p) => p.name || `„${p.gesagt}“ – ?`).join(', ') || '–';
  return (
    <div className="mt-4 rounded-2xl bg-[#F5F5F7] p-3">
      <div className="text-[12px] text-[#6E6E73] mb-1">Vorschlag · zerlegt mit {QUELLEN[v.quelle] || v.quelle}</div>
      <Zeile icon={Users} titel="Mitarbeiter" unsicher={u.has('mitarbeiter')}>{personen}</Zeile>
      <Zeile icon={Sparkles} titel="Projekt" unsicher={u.has('projekt')}>{v.projekt?.name || '–'}</Zeile>
      <Zeile icon={MapPin} titel="Adresse" unsicher={u.has('standort')}>{v.adresse || '–'}</Zeile>
      <Zeile icon={CalendarDays} titel="Tage" unsicher={u.has('zeitraum')}>{v.tage_text || '–'}</Zeile>
      <Zeile icon={Clock} titel="Uhrzeit" unsicher={u.has('startzeit') || u.has('endzeit')}>{v.start_time}–{v.end_time} Uhr · {v.pause_minutes} Min. Pause</Zeile>
      {(v.rueckfragen || []).map((r, i) => (
        <div key={`r${i}`} className="mt-2 flex gap-2 text-[14px] text-[#1D1D1F]"><HelpCircle size={16} className="text-[#C41E3A] mt-0.5 shrink-0" /><span className="font-medium">{r.frage}</span></div>
      ))}
      {(v.konflikte || []).map((k, i) => (
        <div key={`k${i}`} className="mt-2 flex gap-2 text-[14px] text-[#B25E00]"><AlertTriangle size={16} className="mt-0.5 shrink-0" />{k.text}</div>
      ))}
      {(v.hinweise || []).map((h, i) => <p key={`h${i}`} className="mt-2 text-[13px] text-[#6E6E73]">{h}</p>)}
      <p className="mt-3 text-[12px] text-[#86868B]">{v.hinweis} Prüfen, ändern und bestätigen kommt im nächsten Schritt.</p>
    </div>
  );
}
