import React, { useEffect, useRef, useState } from 'react';
import { Upload, Trash2, ImageIcon, Stamp, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import { processLogoFile } from '../lib/utils';
import { BUNDESLAENDER, WEEKDAYS_DE } from '../lib/dates';
import StempelDialog from './StempelDialog';
import { Btn, Chip, Field, SectionLabel, TextInput, TextArea, Toggle } from './ui';

export const COMPANY_DEFAULTS = {
  name: '', owner: '', street: '', zip_code: '', city: '', phone: '', email: '', website: '',
  tax_number: '', vat_id: '', bank_name: '', iban: '', bic: '',
  default_hourly_rate: 0, vat_rate: 19, small_business: false,
  invoice_prefix: 'RE-', payment_days: 14,
  invoice_text: 'Reinigungsarbeiten laut beiliegenden Stundenzetteln',
  logo: null, logo_w: 0, logo_h: 0,
  stamp: null, stamp_w: 0, stamp_h: 0, stamp_on_sheet: true, stamp_on_invoice: true, stamp_scale: 100, stamp_config: null,
  bundesland: '', auto_pause: false, arbzg_pruefung: true, sperre_tage_mitarbeiter: 7, workdays: [0, 1, 2, 3, 4],
};

const toForm = (c) => ({
  ...COMPANY_DEFAULTS,
  ...(c || {}),
  default_hourly_rate: c?.default_hourly_rate ? String(c.default_hourly_rate) : '',
  vat_rate: String(c?.vat_rate ?? 19),
  payment_days: String(c?.payment_days ?? 14),
});

const STAMP_KEYS = ['stamp', 'stamp_w', 'stamp_h', 'stamp_on_sheet', 'stamp_on_invoice', 'stamp_scale', 'stamp_config'];
const FELDER = ['name', 'owner', 'street', 'zip_code', 'city', 'phone', 'email', 'website', 'tax_number', 'vat_id', 'bank_name', 'iban', 'bic',
  'default_hourly_rate', 'vat_rate', 'small_business', 'invoice_prefix', 'payment_days', 'invoice_text', 'logo', 'logo_w', 'logo_h', ...STAMP_KEYS,
  'bundesland', 'auto_pause', 'arbzg_pruefung', 'sperre_tage_mitarbeiter', 'workdays'];

/** Firmendaten (Server-Version): `onSave(daten)` speichert über die API; Stempel-Änderungen werden sofort gespeichert. */
export default function CompanyForm({ company, onSave, submitLabel = 'Speichern' }) {
  const [form, setForm] = useState(toForm(company));
  const [drag, setDrag] = useState(false);
  const [stampOpen, setStampOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => { setForm(toForm(company)); }, [company]);

  const set = (key) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [key]: v })); };

  const useFile = async (file) => {
    if (!file) return;
    try { const { dataUrl, w, h } = await processLogoFile(file); setForm((f) => ({ ...f, logo: dataUrl, logo_w: w, logo_h: h })); }
    catch (err) { toast.error(err.message); }
  };

  const speichern = async (daten, meldung) => {
    setBusy(true);
    try { await onSave(daten); if (meldung) toast.success(meldung); }
    catch (err) { toast.error(err.message || 'Speichern fehlgeschlagen'); }
    finally { setBusy(false); }
  };

  const applyStamp = (fields) => { setForm((f) => ({ ...f, ...fields })); speichern(fields, 'Stempel gespeichert'); };
  const removeStamp = () => {
    const fields = { stamp: null, stamp_w: 0, stamp_h: 0, stamp_config: null };
    setForm((f) => ({ ...f, ...fields }));
    speichern(fields, 'Stempel entfernt');
  };
  const current = Object.fromEntries(STAMP_KEYS.map((k) => [k, form[k]]));

  const submit = (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Bitte den Firmennamen eingeben'); return; }
    const data = Object.fromEntries(FELDER.map((k) => [k, form[k]]));
    data.name = form.name.trim();
    data.default_hourly_rate = parseFloat(String(form.default_hourly_rate).replace(',', '.')) || 0;
    data.vat_rate = parseFloat(String(form.vat_rate).replace(',', '.')) || 0;
    data.payment_days = parseInt(form.payment_days, 10) || 14;
    data.logo_w = Number(data.logo_w) || 0;
    data.logo_h = Number(data.logo_h) || 0;
    if (!data.logo) { data.logo = null; }
    data.sperre_tage_mitarbeiter = Math.max(0, Math.min(365, parseInt(form.sperre_tage_mitarbeiter, 10) || 0));
    data.workdays = (form.workdays || []).length ? form.workdays : [0, 1, 2, 3, 4];
    speichern(data, 'Firmendaten gespeichert');
  };
  const toggleDay = (i) => setForm((f) => { const w = f.workdays || []; return { ...f, workdays: w.includes(i) ? w.filter((d) => d !== i) : [...w, i].sort() }; });

  return (
    <form onSubmit={submit} className="space-y-8" data-testid="company-form">
      <section className="space-y-3">
        <SectionLabel>Logo</SectionLabel>
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); useFile(e.dataTransfer.files?.[0]); }}
          className={`flex items-center gap-5 p-4 rounded-2xl border-2 border-dashed cursor-pointer transition-colors ${drag ? 'border-[#C41E3A] bg-[#C41E3A]/5' : 'border-black/10 bg-[#F5F5F7] hover:bg-black/[0.04]'}`}
        >
          <div className="w-28 h-16 shrink-0 rounded-xl bg-white shadow-card flex items-center justify-center overflow-hidden">
            {form.logo ? <img src={form.logo} alt="Firmenlogo" className="max-w-[90%] max-h-[90%] object-contain" /> : <ImageIcon size={22} className="text-[#A1A1A6]" />}
          </div>
          <div className="min-w-0">
            <div className="text-[15px] font-semibold flex items-center gap-2"><Upload size={16} /> {form.logo ? 'Logo ändern' : 'Firmenlogo hochladen'}</div>
            <div className="text-[12px] text-[#86868B] mt-0.5">PNG, JPG oder SVG · erscheint oben links auf allen PDFs</div>
            {form.logo && <button type="button" onClick={(e) => { e.stopPropagation(); setForm((f) => ({ ...f, logo: null, logo_w: 0, logo_h: 0 })); }} className="mt-1.5 text-[13px] text-[#C41E3A] font-medium flex items-center gap-1"><Trash2 size={13} /> Entfernen</button>}
          </div>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/svg+xml,.png,.jpg,.jpeg,.svg" onChange={(e) => { useFile(e.target.files?.[0]); e.target.value = ''; }} className="hidden" />
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Firmenstempel &amp; Unterschrift</SectionLabel>
        <div className="rounded-2xl bg-[#F5F5F7] p-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="w-full sm:w-56 h-28 shrink-0 rounded-xl bg-white shadow-card flex items-center justify-center overflow-hidden p-2">
            {form.stamp ? <img src={form.stamp} alt="Firmenstempel" className="max-w-full max-h-full object-contain" /> : <Stamp size={26} className="text-[#A1A1A6]" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[15px] font-semibold">{form.stamp ? 'Stempel vorhanden' : 'Noch kein Stempel'}</div>
            <div className="text-[12px] text-[#86868B] mt-0.5">
              {form.stamp
                ? `Erscheint ${[form.stamp_on_sheet !== false && 'auf jedem Stundenzettel', form.stamp_on_invoice !== false && 'auf jeder Rechnung'].filter(Boolean).join(' und ') || 'auf keinem PDF'} · Größe ${form.stamp_scale || 100} %`
                : 'Aus den Firmendaten erzeugt, mit Unterschrift per Finger. Erscheint groß auf Stundenzetteln und Rechnungen.'}
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              <Btn type="button" variant={form.stamp ? 'soft' : 'dark'} size="sm" onClick={() => setStampOpen(true)}>
                {form.stamp ? <><Pencil size={14} /> Stempel bearbeiten</> : <><Stamp size={14} /> Stempel erstellen</>}
              </Btn>
              {form.stamp && <Btn type="button" variant="danger" size="sm" onClick={removeStamp}><Trash2 size={14} /> Entfernen</Btn>}
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Mein Unternehmen</SectionLabel>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Firmenname" className="sm:col-span-2"><TextInput value={form.name} onChange={set('name')} required placeholder="z. B. PowerCleanService" /></Field>
          <Field label="Inhaber / Geschäftsführer" className="sm:col-span-2"><TextInput value={form.owner} onChange={set('owner')} /></Field>
          <Field label="Straße und Hausnummer" className="sm:col-span-2"><TextInput value={form.street} onChange={set('street')} /></Field>
          <Field label="Postleitzahl"><TextInput value={form.zip_code} onChange={set('zip_code')} inputMode="numeric" /></Field>
          <Field label="Ort"><TextInput value={form.city} onChange={set('city')} /></Field>
          <Field label="Telefon"><TextInput value={form.phone} onChange={set('phone')} type="tel" /></Field>
          <Field label="E-Mail"><TextInput value={form.email} onChange={set('email')} type="email" /></Field>
          <Field label="Webseite (optional)" className="sm:col-span-2"><TextInput value={form.website} onChange={set('website')} placeholder="www.beispiel.de" /></Field>
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Rechnungsdaten</SectionLabel>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Steuernummer"><TextInput value={form.tax_number} onChange={set('tax_number')} /></Field>
          <Field label="USt-IdNr."><TextInput value={form.vat_id} onChange={set('vat_id')} /></Field>
          <Field label="IBAN" className="sm:col-span-2"><TextInput value={form.iban} onChange={set('iban')} /></Field>
          <Field label="BIC"><TextInput value={form.bic} onChange={set('bic')} /></Field>
          <Field label="Bank"><TextInput value={form.bank_name} onChange={set('bank_name')} /></Field>
          <Field label="Standard-Stundensatz (€ netto)" hint="Wird für neue Projekte übernommen.">
            <TextInput type="number" step="0.01" min="0" inputMode="decimal" value={form.default_hourly_rate} onChange={set('default_hourly_rate')} placeholder="z. B. 32,50" />
          </Field>
          <Field label="Zahlungsziel (Tage)"><TextInput type="number" min="0" inputMode="numeric" value={form.payment_days} onChange={set('payment_days')} /></Field>
        </div>
        <div className="rounded-2xl bg-[#F5F5F7] px-4 divide-y divide-black/[0.06]">
          <Toggle checked={!!form.small_business} onChange={(v) => setForm((f) => ({ ...f, small_business: v }))} label="Kleinunternehmer (§ 19 UStG)" hint="Keine Umsatzsteuer auf der Rechnung" />
          {!form.small_business && (
            <div className="flex items-center justify-between py-2.5 gap-4">
              <span className="text-[15px]">Umsatzsteuer</span>
              <span className="flex items-center gap-2"><TextInput type="number" step="0.1" min="0" inputMode="decimal" value={form.vat_rate} onChange={set('vat_rate')} className="w-24 h-9 text-right bg-white" /><span className="text-[#6E6E73]">%</span></span>
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Rechnungsnummer-Präfix" hint={`z. B. ${form.invoice_prefix || ''}${new Date().getFullYear()}-0001, läuft je Jahr fort`}>
            <TextInput value={form.invoice_prefix} onChange={set('invoice_prefix')} placeholder="RE-" />
          </Field>
          <Field label="Leistungstext auf der Rechnung" className="sm:col-span-2"><TextArea rows={2} value={form.invoice_text} onChange={set('invoice_text')} /></Field>
        </div>
        <p className="text-[12px] text-[#86868B]">Kunden, die selbst Gebäudereinigung erbringen, bekommen Rechnungen ohne Umsatzsteuer (§ 13b UStG). Das wird beim Kunden eingestellt.</p>
      </section>

      <section className="space-y-3">
        <SectionLabel>Arbeitszeitregeln</SectionLabel>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Bundesland (Feiertage)" hint="Feiertage zählen nicht als Sollzeit und werden bei Serien übersprungen.">
            <select value={form.bundesland || ''} onChange={set('bundesland')} className="w-full h-11 rounded-xl bg-[#F5F5F7] px-3.5 text-[15px] outline-none">
              {BUNDESLAENDER.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
            </select>
          </Field>
          <Field label="Mitarbeiter dürfen Einträge ändern bis (Tage zurück)" hint="Ältere Tage ändert nur das Büro (MiLoG: Aufzeichnung bis zum 7. Folgetag).">
            <TextInput type="number" min="0" max="365" inputMode="numeric" value={form.sperre_tage_mitarbeiter} onChange={set('sperre_tage_mitarbeiter')} />
          </Field>
        </div>
        <div>
          <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Arbeitstage (für Sollstunden)</span>
          <div className="flex flex-wrap gap-2">{WEEKDAYS_DE.map((d, i) => <Chip key={d} active={(form.workdays || []).includes(i)} onClick={() => toggleDay(i)}>{d}</Chip>)}</div>
        </div>
        <div className="rounded-2xl bg-[#F5F5F7] px-4 divide-y divide-black/[0.06]">
          <Toggle checked={!!form.auto_pause} onChange={(v) => setForm((f) => ({ ...f, auto_pause: v }))} label="Gesetzliche Pause automatisch abziehen" hint="Ab 6 Stunden 30 Min., ab 9 Stunden 45 Min. (§ 4 ArbZG), wenn weniger eingetragen wurde" />
          <Toggle checked={form.arbzg_pruefung !== false} onChange={(v) => setForm((f) => ({ ...f, arbzg_pruefung: v }))} label="Arbeitszeitgesetz prüfen" hint="Hinweise bei über 10 Stunden, zu kurzer Pause, Ruhezeit unter 11 Stunden, Sonntagsarbeit" />
        </div>
      </section>

      <div className="flex justify-end gap-2 pt-1">
        <Btn type="submit" loading={busy}>{submitLabel}</Btn>
      </div>

      <StempelDialog open={stampOpen} onOpenChange={setStampOpen} company={{ ...form }} current={current} onApply={applyStamp} onRemove={removeStamp} />
    </form>
  );
}
