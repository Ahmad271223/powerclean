import React, { useEffect, useState } from 'react';
import { CreditCard, Mail, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Field, IconBtn, Select, Sheet, TextArea, TextInput, Toggle } from '../ui';
import { api } from '../../lib/api';
import { fmtDate, fromKey, todayKey } from '../../lib/dates';

export const fmtEur = (n) => `${Number(n || 0).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
export const ART_CLS = { abschlag: 'bg-[#E8F0FE] text-[#1D4ED8]', schluss: 'bg-[#E8F8EC] text-[#1B7F3B]', storno: 'bg-[#FDE8E8] text-[#C41E3A]', gutschrift: 'bg-[#FFF4E5] text-[#B25E00]', pauschal: 'bg-black/[0.06] text-[#6E6E73]' };
export const STATUS_CLS = { offen: 'bg-[#FFF4E5] text-[#B25E00]', teilbezahlt: 'bg-[#E8F0FE] text-[#1D4ED8]', bezahlt: 'bg-[#E8F8EC] text-[#1B7F3B]', storniert: 'bg-black/[0.06] text-[#6E6E73]' };
const ZAHLUNGSARTEN = { ueberweisung: 'Überweisung', bar: 'Bar', karte: 'Karte', lastschrift: 'Lastschrift', verrechnung: 'Verrechnung', skonto: 'Skonto / Nachlass' };
const zahl = (s) => parseFloat(String(s).replace(',', '.')) || 0;

/** Zahlungen einer Rechnung: Teilzahlungen erfassen und löschen; der Server setzt offen/teilbezahlt/bezahlt. */
export function ZahlungDialog({ rechnung, onOpenChange, onSaved }) {
  const [r, setR] = useState(rechnung);
  const [f, setF] = useState({ betrag: '', am: todayKey(), art: 'ueberweisung', notiz: '' });
  const [busy, setBusy] = useState('');
  useEffect(() => { setR(rechnung); if (rechnung) setF({ betrag: rechnung.offen_betrag ? String(rechnung.offen_betrag) : '', am: todayKey(), art: 'ueberweisung', notiz: '' }); }, [rechnung]);
  if (!r) return null;
  const buchen = async () => {
    if (!(zahl(f.betrag) > 0)) { toast.error('Betrag angeben'); return; }
    setBusy('buchen');
    try { const x = await api.post(`/api/rechnungen/${r.id}/zahlungen`, { betrag: zahl(f.betrag), am: f.am, art: f.art, notiz: f.notiz }); setR(x.rechnung); setF((v) => ({ ...v, betrag: x.rechnung.offen_betrag ? String(x.rechnung.offen_betrag) : '', notiz: '' })); toast.success(x.rechnung.status === 'bezahlt' ? 'Vollständig bezahlt' : 'Zahlung erfasst'); onSaved?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const loeschen = async (z) => {
    setBusy(z.id);
    try { const x = await api.del(`/api/rechnungen/${r.id}/zahlungen/${z.id}`); setR(x.rechnung); toast.success('Zahlung entfernt'); onSaved?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  return (
    <Sheet open={!!rechnung} onOpenChange={onOpenChange} title={`Zahlungen · ${r.number}`} subtitle={`${fmtEur(r.gross)} brutto · bezahlt ${fmtEur(r.bezahlt_betrag)} · offen ${fmtEur(r.offen_betrag)}`}>
      <div className="space-y-3">
        {(r.zahlungen || []).length > 0 && (
          <ul className="divide-y divide-black/[0.06] text-[13px]">{r.zahlungen.map((z) => <li key={z.id} className="py-2 flex items-center gap-2"><span className="flex-1">{fmtDate(fromKey(z.am))} · {ZAHLUNGSARTEN[z.art] || z.art}{z.notiz ? ` · ${z.notiz}` : ''}<span className="text-[#6E6E73]"> · {z.erfasst_von}</span></span><span className="font-semibold">{fmtEur(z.betrag)}</span><IconBtn size={28} onClick={() => loeschen(z)} className="text-[#C41E3A]" title="Zahlung entfernen"><Trash2 size={14} /></IconBtn></li>)}</ul>
        )}
        {r.status !== 'storniert' && r.offen_betrag > 0 && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Betrag €"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.betrag} onChange={(e) => setF((v) => ({ ...v, betrag: e.target.value }))} /></Field>
            <Field label="Am"><TextInput type="date" value={f.am} onChange={(e) => setF((v) => ({ ...v, am: e.target.value }))} /></Field>
            <Field label="Zahlungsart"><Select value={f.art} onChange={(e) => setF((v) => ({ ...v, art: e.target.value }))}>{Object.entries(ZAHLUNGSARTEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
            <Field label="Notiz"><TextInput value={f.notiz} onChange={(e) => setF((v) => ({ ...v, notiz: e.target.value }))} placeholder="z. B. Verwendungszweck" /></Field>
            <div className="col-span-2 flex justify-end"><Btn onClick={buchen} loading={busy === 'buchen'}><CreditCard size={16} /> Zahlung erfassen</Btn></div>
          </div>
        )}
      </div>
    </Sheet>
  );
}

/** Rechnung per E-Mail an den Kunden (PDF, mit ZUGFeRD-XML wenn die Daten vollständig sind). */
export function SendenDialog({ rechnung, kundeEmail, onOpenChange, onSaved }) {
  const [an, setAn] = useState('');
  const [nachricht, setNachricht] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (rechnung) { setAn(kundeEmail || ''); setNachricht(''); } }, [rechnung, kundeEmail]);
  if (!rechnung) return null;
  const los = async () => {
    setBusy(true);
    try { const r = await api.post(`/api/rechnungen/${rechnung.id}/senden`, { an, nachricht }); toast.success(`${r.rechnung.art_name || 'Rechnung'} an ${an} gesendet${r.profil === 'zugferd' ? ' (mit ZUGFeRD-XML)' : ''}`); onSaved?.(); onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={!!rechnung} onOpenChange={onOpenChange} title={`${rechnung.art_name || 'Rechnung'} ${rechnung.number} senden`} subtitle="Das PDF hängt an; die Rechnung gilt damit als ausgestellt. Jede E-Mail steht unter Protokoll → E-Mail-Nachweise."
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={los} loading={busy}><Mail size={16} /> Senden</Btn></>}>
      <div className="space-y-3">
        <Field label="An"><TextInput type="email" value={an} onChange={(e) => setAn(e.target.value)} placeholder="kunde@beispiel.de" /></Field>
        <Field label="Persönliche Nachricht (optional)"><TextArea rows={3} value={nachricht} onChange={(e) => setNachricht(e.target.value)} /></Field>
      </div>
    </Sheet>
  );
}

/** Gutschrift an einen Kunden: Positionen positiv eingeben, gespeichert und gedruckt wird eine Gutschrift (negativer Beleg, XML 381). */
export function GutschriftDialog({ open, onOpenChange, kunden, projekte, onSaved }) {
  const [f, setF] = useState({ customer_id: '', project_id: '', grund: '', bezug_nummer: '', text: '' });
  const [zeilen, setZeilen] = useState([{ text: '', quantity: '1', unit: 'Psch.', unit_price: '' }]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setF({ customer_id: '', project_id: '', grund: '', bezug_nummer: '', text: '' }); setZeilen([{ text: '', quantity: '1', unit: 'Psch.', unit_price: '' }]); } }, [open]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const setZ = (i, k, v) => setZeilen((z) => z.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  const summe = zeilen.reduce((s, x) => s + zahl(x.quantity) * zahl(x.unit_price), 0);
  const anlegen = async () => {
    const positionen = zeilen.filter((x) => x.text.trim() && zahl(x.unit_price) > 0).map((x) => ({ text: x.text.trim(), quantity: zahl(x.quantity), unit: x.unit || 'Psch.', unit_price: zahl(x.unit_price) }));
    if (!positionen.length) { toast.error('Mindestens eine Position mit Betrag'); return; }
    if (!f.customer_id && !f.project_id) { toast.error('Kunde oder Projekt wählen'); return; }
    if (!f.grund.trim()) { toast.error('Grund angeben'); return; }
    setBusy(true);
    try { const r = await api.post('/api/rechnungen/gutschrift', { ...f, customer_id: f.customer_id || null, project_id: f.project_id || null, positionen }); toast.success(`Gutschrift ${r.rechnung.number} angelegt`); onSaved?.(); onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Gutschrift anlegen" subtitle="Rechnungskorrektur zugunsten des Kunden mit eigener Nummer – Beträge positiv eingeben." width="sm:max-w-2xl"
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={anlegen} loading={busy}>Gutschrift anlegen ({fmtEur(summe)} netto)</Btn></>}>
      <div className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Kunde"><Select value={f.customer_id} onChange={set('customer_id')}><option value="">Kunde wählen …</option>{kunden.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}</Select></Field>
          <Field label="Projekt (optional)"><Select value={f.project_id} onChange={set('project_id')}><option value="">Kein Projekt</option>{projekte.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
          <Field label="Grund"><TextInput value={f.grund} onChange={set('grund')} placeholder="z. B. Kulanz, Mangel, Doppelberechnung" /></Field>
          <Field label="Bezug auf Rechnung (optional)"><TextInput value={f.bezug_nummer} onChange={set('bezug_nummer')} placeholder="RE-2026-0012" /></Field>
        </div>
        <div className="space-y-2">
          {zeilen.map((x, i) => (
            <div key={i} className="grid grid-cols-2 sm:grid-cols-[1fr_80px_90px_110px_36px] gap-2 items-center">
              <TextInput value={x.text} onChange={(e) => setZ(i, 'text', e.target.value)} placeholder="Bezeichnung" className="col-span-2 sm:col-span-1" />
              <TextInput type="number" step="0.01" min="0" inputMode="decimal" value={x.quantity} onChange={(e) => setZ(i, 'quantity', e.target.value)} placeholder="Menge" />
              <TextInput value={x.unit} onChange={(e) => setZ(i, 'unit', e.target.value)} placeholder="Einheit" />
              <TextInput type="number" step="0.01" min="0" inputMode="decimal" value={x.unit_price} onChange={(e) => setZ(i, 'unit_price', e.target.value)} placeholder="Einzelpreis €" />
              <IconBtn size={32} onClick={() => setZeilen((z) => z.filter((_, j) => j !== i))} className="text-[#C41E3A]" title="Entfernen"><Trash2 size={14} /></IconBtn>
            </div>
          ))}
          <Btn size="sm" variant="ghost" onClick={() => setZeilen((z) => [...z, { text: '', quantity: '1', unit: 'Psch.', unit_price: '' }])}><Plus size={14} /> Position</Btn>
        </div>
        <Field label="Text auf der Gutschrift (optional)"><TextArea rows={2} value={f.text} onChange={set('text')} /></Field>
      </div>
    </Sheet>
  );
}

/** Abschlagsrechnung: kumulativ nach Leistungsstand (Prozent des Auftragswerts) oder pauschaler Betrag; mit Vorschau. */
export function AbschlagDialog({ open, onOpenChange, projekt, abrechnung, onSaved }) {
  const [f, setF] = useState({ kumulativ: true, prozent: '', betrag: '', text: '', leistung_von: '', leistung_bis: '' });
  const [vorschau, setVorschau] = useState(null);
  const [busy, setBusy] = useState('');
  useEffect(() => { if (open) { setF({ kumulativ: !abrechnung?.abschlaege?.length || !!abrechnung.abschlaege[0].kumulativ, prozent: '', betrag: '', text: '', leistung_von: '', leistung_bis: '' }); setVorschau(null); } }, [open, abrechnung]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); setVorschau(null); };
  const daten = (pruefen) => ({ project_id: projekt.id, art: 'abschlag', leistungsstand_prozent: f.kumulativ ? zahl(f.prozent) || null : null, betrag_netto: f.kumulativ ? null : zahl(f.betrag) || null, text: f.text, leistung_von: f.leistung_von || null, leistung_bis: f.leistung_bis || null, nur_pruefen: pruefen });
  const pruefen = async () => { setBusy('pruefen'); try { setVorschau((await api.post('/api/rechnungen/auftrag', daten(true))).vorschau); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const anlegen = async () => { setBusy('anlegen'); try { const r = await api.post('/api/rechnungen/auftrag', daten(false)); toast.success(`Abschlagsrechnung ${r.rechnung.number} angelegt`); onSaved?.(); onOpenChange(false); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const nr = abrechnung?.naechster_abschlag_nr || 1;
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={`${nr}. Abschlagsrechnung`} subtitle={`Auftragssumme ${fmtEur(abrechnung?.basis?.basis_netto)} netto${abrechnung?.basis?.nachtraege_netto ? ` (inkl. ${fmtEur(abrechnung.basis.nachtraege_netto)} Nachträge)` : ''} · bisher gestellt ${fmtEur(abrechnung?.summen?.gestellt_netto)}`}
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn variant="soft" onClick={pruefen} loading={busy === 'pruefen'}>Vorschau</Btn><Btn onClick={anlegen} loading={busy === 'anlegen'}>Rechnung anlegen</Btn></>}>
      <div className="space-y-3">
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={f.kumulativ} onChange={(v) => { if (!abrechnung?.abschlaege?.length) { setF((x) => ({ ...x, kumulativ: v })); setVorschau(null); } }} label="Kumulativ nach Leistungsstand" hint={abrechnung?.abschlaege?.length ? 'Die Art steht nach dem ersten Abschlag fest.' : 'Aus: pauschaler Abschlagsbetrag. An: Prozent der Auftragssumme, bereits gestellte Abschläge werden abgezogen.'} /></div>
        {f.kumulativ ? <Field label="Leistungsstand in % der Auftragssumme"><TextInput type="number" inputMode="decimal" step="1" min="1" max="100" value={f.prozent} onChange={set('prozent')} placeholder="z. B. 30" /></Field>
          : <Field label="Abschlagsbetrag netto €"><TextInput type="number" inputMode="decimal" step="0.01" min="0" value={f.betrag} onChange={set('betrag')} /></Field>}
        <div className="grid grid-cols-2 gap-2"><Field label="Leistung von (optional)"><TextInput type="date" value={f.leistung_von} onChange={set('leistung_von')} /></Field><Field label="bis"><TextInput type="date" value={f.leistung_bis} onChange={set('leistung_bis')} /></Field></div>
        <Field label="Text auf der Rechnung (optional)"><TextArea rows={2} value={f.text} onChange={set('text')} placeholder="z. B. Abschlag nach Montage der ersten Etage" /></Field>
        {vorschau && (
          <div className="rounded-2xl bg-[#E8F8EC] px-4 py-3 text-[13px]">
            {vorschau.zeilen.map((z, i) => <div key={i} className="flex justify-between"><span>{z.text}</span><span>{fmtEur(z.amount)}</span></div>)}
            <div className="flex justify-between font-semibold border-t border-black/10 mt-1 pt-1"><span>Netto / Brutto</span><span>{fmtEur(vorschau.net)} / {fmtEur(vorschau.gross)}</span></div>
          </div>
        )}
      </div>
    </Sheet>
  );
}

/** Zahlungserinnerung / Mahnung: Text prüfen, optional per E-Mail, Gebühr nur wenn gewollt – ausgelöst immer von Hand. */
export function MahnungDialog({ eintrag, regeln, onOpenChange, onSaved }) {
  const [text, setText] = useState('');
  const [perEmail, setPerEmail] = useState(true);
  const [gebuehr, setGebuehr] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!eintrag) return;
    const s = eintrag.naechste_stufe;
    setText(s === 1 ? regeln?.text_erinnerung : s === 2 ? regeln?.text_mahnung : regeln?.text_letzte || '');
    setGebuehr(String(s === 2 ? regeln?.gebuehr_mahnung ?? 0 : s === 3 ? regeln?.gebuehr_letzte ?? 0 : 0));
    setPerEmail(!!eintrag.kunde_email);
  }, [eintrag, regeln]);
  if (!eintrag) return null;
  const los = async () => {
    setBusy(true);
    try { const r = await api.post(`/api/rechnungen/${eintrag.id}/mahnung`, { text, per_email: perEmail, gebuehr: zahl(gebuehr), erzwingen: !eintrag.jetzt_faellig }); toast.success(`${r.mahnung.name} erstellt${r.mahnung.an ? ` und an ${r.mahnung.an} gesendet` : ''}`); onSaved?.(); onOpenChange(false); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={!!eintrag} onOpenChange={onOpenChange} title={`${eintrag.naechste_name} · ${eintrag.number}`} subtitle={`${eintrag.kunde_name || ''} · offen ${fmtEur(eintrag.offen_betrag)} · ${eintrag.tage_ueberfaellig} Tage überfällig${!eintrag.jetzt_faellig && eintrag.faellig_ab ? ` · Frist läuft bis ${fmtDate(fromKey(eintrag.faellig_ab))} (wird übersprungen)` : ''}`}
      footer={<><Btn variant="ghost" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn onClick={los} loading={busy}><Mail size={16} /> {perEmail && eintrag.kunde_email ? 'Erstellen und senden' : 'PDF erstellen'}</Btn></>}>
      <div className="space-y-3">
        <Field label="Text des Schreibens"><TextArea rows={5} value={text} onChange={(e) => setText(e.target.value)} /></Field>
        {eintrag.naechste_stufe > 1 && <Field label="Mahngebühr €" hint="Nur, wenn vertraglich oder gesetzlich zulässig – Standard aus den Regeln"><TextInput type="number" inputMode="decimal" step="0.5" min="0" value={gebuehr} onChange={(e) => setGebuehr(e.target.value)} /></Field>}
        <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={perEmail} onChange={setPerEmail} label={eintrag.kunde_email ? `Per E-Mail an ${eintrag.kunde_email}` : 'Per E-Mail (keine Adresse beim Kunden)'} hint="Sonst nur als PDF zum Ausdrucken." /></div>
      </div>
    </Sheet>
  );
}
