import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Stamp, Share2, Trash2, Check } from 'lucide-react';
import { toast } from 'sonner';
import SignaturePad from './SignaturePad';
import { Sheet, Btn, Chip, Field, SectionLabel, TextInput, Toggle } from './ui';
import {
  VARIANTEN, VARIANTE_STANDARD, STEMPEL_FARBEN, stempelCanvasFarbig, stempelPng, unterschriftZuschneiden, bildLaden, datenAusFirma,
} from '../lib/stempel';
import { shareOrDownload } from '../lib/utils';

const FELDER = [
  ['name', 'Firmenname'], ['zusatz', 'Zusatz (z. B. Inhaber)'], ['strasse', 'Straße und Hausnummer'],
  ['ort', 'PLZ und Ort'], ['tel', 'Telefon'], ['mail', 'E-Mail'], ['ust', 'Steuernummer / USt-IdNr.'],
];
const SIG_STANDARD = { an: true, groesse: 55, x: 50, y: 65 };
const MM = { sheet: 62, invoice: 72 };

/** Draw a transparent stamp canvas onto a display canvas with white background. */
function zeichneAuf(ziel, quelle, maxW) {
  if (!ziel) return;
  const s = Math.min(1, maxW / quelle.width);
  ziel.width = Math.round(quelle.width * s);
  ziel.height = Math.round(quelle.height * s);
  const x = ziel.getContext('2d');
  x.fillStyle = '#FFFFFF';
  x.fillRect(0, 0, ziel.width, ziel.height);
  x.drawImage(quelle, 0, 0, ziel.width, ziel.height);
}

const Slider = ({ label, value, min, max, onChange, suffix = '' }) => (
  <label className="grid grid-cols-[96px_1fr_52px] items-center gap-3 text-[13px]">
    <span className="text-[#6E6E73]">{label}</span>
    <input type="range" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-[#C41E3A]" />
    <span className="text-right font-medium">{value}{suffix}</span>
  </label>
);

function StempelEditor({ company, current, onApply, onRemove, onClose }) {
  const cfg = current?.stamp_config || {};
  const [daten, setDaten] = useState(() => cfg.daten || datenAusFirma(company));
  const [variante, setVariante] = useState(cfg.variante || VARIANTE_STANDARD);
  const [gleich, setGleich] = useState(!!cfg.gleich);
  const [schraeg, setSchraeg] = useState(cfg.schraeg ?? true);
  const [abnutzung, setAbnutzung] = useState(!!cfg.abnutzung);
  const [farbe, setFarbe] = useState(cfg.farbe || 'blau');
  const [sig, setSig] = useState(cfg.sig || SIG_STANDARD);
  const [unterschrift, setUnterschrift] = useState(null); // {img, w, h, dataUrl}
  const [gespeicherteSig, setGespeicherteSig] = useState(cfg.signature || null);
  const [onSheet, setOnSheet] = useState(current?.stamp_on_sheet ?? true);
  const [onInvoice, setOnInvoice] = useState(current?.stamp_on_invoice ?? true);
  const [scale, setScale] = useState(current?.stamp_scale || 100);
  const [fehler, setFehler] = useState('');
  const vorschau = useRef(null);
  const thumbs = useRef({});

  // stored signature (from an earlier session) -> usable image
  useEffect(() => {
    if (!gespeicherteSig) return;
    let aktiv = true;
    bildLaden(gespeicherteSig).then((img) => { if (aktiv) setUnterschrift({ img, w: img.width, h: img.height, dataUrl: gespeicherteSig }); }).catch(() => {});
    return () => { aktiv = false; };
  }, [gespeicherteSig]);

  const unterschriftGezeichnet = useCallback(async (dataUrl) => {
    if (!dataUrl) { setUnterschrift(null); setGespeicherteSig(null); return; }
    try { setUnterschrift(await unterschriftZuschneiden(dataUrl)); setGespeicherteSig(null); }
    catch { setUnterschrift(null); }
  }, []);

  const optionen = { daten, variante, gleich, schraeg, abnutzung, unterschrift, einst: sig };

  // redraw thumbnails + big preview, bundled per animation frame
  useEffect(() => {
    let frame = 0;
    const zeichnen = () => {
      try {
        VARIANTEN.forEach((v) => {
          const t = thumbs.current[v.id];
          if (t) zeichneAuf(t, stempelCanvasFarbig({ ...optionen, variante: v.id, abnutzung: false }, farbe, 320), 320);
        });
        zeichneAuf(vorschau.current, stempelCanvasFarbig(optionen, farbe, 1000), 1000);
        setFehler('');
      } catch (e) {
        setFehler(e?.message || 'Vorschau konnte nicht gezeichnet werden');
      }
    };
    frame = requestAnimationFrame(zeichnen);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [daten, variante, gleich, schraeg, abnutzung, farbe, unterschrift, sig]);

  const setzen = (k) => (e) => { const v = e.target.value; setDaten((d) => ({ ...d, [k]: v })); };

  const anwenden = () => {
    try {
      const { dataUrl, w, h } = stempelPng(optionen, farbe, 1000);
      onApply({
        stamp: dataUrl, stamp_w: w, stamp_h: h,
        stamp_on_sheet: onSheet, stamp_on_invoice: onInvoice, stamp_scale: scale,
        stamp_config: { daten, variante, gleich, schraeg, abnutzung, farbe, sig, signature: unterschrift?.dataUrl || null },
      });
      toast.success('Stempel übernommen – wird mit der Firma gespeichert');
      onClose();
    } catch (e) {
      toast.error(e?.message || 'Stempel konnte nicht erstellt werden');
    }
  };

  const teilen = async () => {
    try {
      const { dataUrl } = stempelPng(optionen, farbe, 1000);
      const blob = await (await fetch(dataUrl)).blob();
      await shareOrDownload(blob, 'firmenstempel.png', 'Firmenstempel');
    } catch { toast.error('PNG konnte nicht erstellt werden'); }
  };

  const f = scale / 100;

  return (
    <div className="space-y-7" data-testid="stempel-editor">
      <section className="space-y-3">
        <SectionLabel>Design</SectionLabel>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {VARIANTEN.map((v) => (
            <button key={v.id} type="button" onClick={() => setVariante(v.id)} aria-pressed={variante === v.id}
              className={`rounded-2xl p-2 bg-white text-center text-[12px] font-medium transition-all ${variante === v.id ? 'ring-2 ring-[#C41E3A] shadow-card' : 'ring-1 ring-black/10 hover:ring-black/25'}`}>
              <canvas ref={(el) => { thumbs.current[v.id] = el; }} className="w-full block" style={{ height: 76, objectFit: 'contain' }} />
              <span className="block mt-1 flex items-center justify-center gap-1">{variante === v.id && <Check size={12} className="text-[#C41E3A]" />}{v.name}</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-[13px] text-[#6E6E73] mr-1">Farbe</span>
          {STEMPEL_FARBEN.map((c) => (
            <button key={c.id} type="button" onClick={() => setFarbe(c.id)} className="w-9 h-9 rounded-full flex items-center justify-center transition-transform active:scale-90" style={{ backgroundColor: c.css, boxShadow: farbe === c.id ? `0 0 0 2px #fff, 0 0 0 4px ${c.css}` : 'none' }} aria-label={c.name} title={c.name}>
              {farbe === c.id && <Check size={15} className="text-white" />}
            </button>
          ))}
          <span className="w-2" />
          <Chip active={schraeg} onClick={() => setSchraeg((v) => !v)}>Leicht schräg</Chip>
          <Chip active={abnutzung} onClick={() => setAbnutzung((v) => !v)}>Abnutzung</Chip>
          <Chip active={gleich} onClick={() => setGleich((v) => !v)}>Schrift gleich groß</Chip>
        </div>
      </section>

      <section className="space-y-2">
        <SectionLabel>Dein Stempel</SectionLabel>
        <div className="rounded-2xl bg-white ring-1 ring-black/10 p-4 flex justify-center" style={{ backgroundImage: 'linear-gradient(45deg, #f3f3f5 25%, transparent 25%, transparent 75%, #f3f3f5 75%), linear-gradient(45deg, #f3f3f5 25%, transparent 25%, transparent 75%, #f3f3f5 75%)', backgroundSize: '16px 16px', backgroundPosition: '0 0, 8px 8px' }}>
          <canvas ref={vorschau} className="max-w-full h-auto block" data-testid="stempel-vorschau" />
        </div>
        {fehler && <p className="text-[12px] text-[#C41E3A]">{fehler}</p>}
      </section>

      <section className="space-y-3">
        <SectionLabel>Daten auf dem Stempel</SectionLabel>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {FELDER.map(([k, label]) => (
            <Field key={k} label={label} className={k === 'name' ? 'sm:col-span-2' : ''}>
              <TextInput value={daten[k] || ''} onChange={setzen(k)} maxLength={120} />
            </Field>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Unterschrift</SectionLabel>
        {gespeicherteSig && unterschrift && (
          <div className="rounded-2xl bg-[#F5F5F7] px-4 py-3 flex items-center gap-3 text-[13px]">
            <img src={gespeicherteSig} alt="Gespeicherte Unterschrift" className="h-10 max-w-[160px] object-contain" />
            <span className="text-[#6E6E73] flex-1">Gespeicherte Unterschrift wird verwendet. Neu unterschreiben ersetzt sie.</span>
          </div>
        )}
        <SignaturePad label="Mit dem Finger, Stift oder der Maus unterschreiben" onChange={unterschriftGezeichnet} height={170} />
        <div className="rounded-2xl bg-[#F5F5F7] px-4 divide-y divide-black/[0.06]">
          <Toggle checked={!!sig.an} onChange={(v) => setSig((s) => ({ ...s, an: v }))} label="Unterschrift auf den Stempel setzen" />
          {sig.an && (
            <div className="py-3 space-y-2">
              <Slider label="Größe" value={sig.groesse} min={20} max={95} onChange={(v) => setSig((s) => ({ ...s, groesse: v }))} suffix=" %" />
              <Slider label="Horizontal" value={sig.x} min={0} max={100} onChange={(v) => setSig((s) => ({ ...s, x: v }))} suffix=" %" />
              <Slider label="Vertikal" value={sig.y} min={0} max={100} onChange={(v) => setSig((s) => ({ ...s, y: v }))} suffix=" %" />
            </div>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Auf den PDFs</SectionLabel>
        <div className="rounded-2xl bg-[#F5F5F7] px-4 divide-y divide-black/[0.06]">
          <Toggle checked={onSheet} onChange={setOnSheet} label="Auf jedem Stundenzettel" hint="Über der Linie „Unterschrift Mitarbeiter“" />
          <Toggle checked={onInvoice} onChange={setOnInvoice} label="Auf jeder Rechnung" hint="Unter „Mit freundlichen Grüßen“" />
          <div className="py-3 space-y-1">
            <Slider label="Größe" value={scale} min={50} max={150} onChange={setScale} suffix=" %" />
            <p className="text-[12px] text-[#86868B]">Etwa {Math.round(MM.invoice * f)} mm breit auf der Rechnung, {Math.round(MM.sheet * f)} mm auf dem Stundenzettel.</p>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <div className="flex gap-2">
          {current?.stamp && <Btn type="button" variant="danger" size="sm" onClick={() => { onRemove(); onClose(); }}><Trash2 size={15} /> Entfernen</Btn>}
          <Btn type="button" variant="ghost" size="sm" onClick={teilen}><Share2 size={15} /> PNG</Btn>
        </div>
        <div className="flex gap-2">
          <Btn type="button" variant="soft" onClick={onClose}>Abbrechen</Btn>
          <Btn type="button" onClick={anwenden} data-testid="stempel-uebernehmen"><Stamp size={16} /> Übernehmen</Btn>
        </div>
      </div>
    </div>
  );
}

/** Sheet for creating / editing the company stamp with signature. */
export default function StempelDialog({ open, onOpenChange, company, current, onApply, onRemove }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Firmenstempel & Unterschrift" subtitle="Design wählen, Daten prüfen, unterschreiben. Der Stempel erscheint auf Stundenzetteln und Rechnungen." width="sm:max-w-2xl">
      {open && <StempelEditor company={company} current={current} onApply={onApply} onRemove={onRemove} onClose={() => onOpenChange(false)} />}
    </Sheet>
  );
}
