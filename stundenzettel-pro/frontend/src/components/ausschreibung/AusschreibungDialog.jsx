import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Field, IconBtn, SectionLabel, Segmented, Select, Sheet, TextArea, TextInput, Toggle } from '../ui';
import { api } from '../../lib/api';
import { ANFORDERUNGEN, csvZuPositionen } from '../../lib/ausschreibung';

const GEWERKE_STANDARD = ['Reinigung', 'Elektro', 'Sanitär / Heizung', 'Trockenbau', 'Maler', 'Boden', 'Rohbau', 'Dach', 'Fenster / Glas', 'Garten / Außenanlagen', 'Logistik', 'Sicherheit', 'Sonstiges'];
const LEER = {
  titel: '', gewerk: 'Elektro', leistungsart: '', beschreibung: '', leistungsumfang: '', ausfuehrungsort: '', sichtbarkeit: 'privat', bewerbungsfrist: '', angebotsfrist: '', ausfuehrung_von: '', ausfuehrung_bis: '',
  anforderungen: Object.fromEntries(ANFORDERUNGEN.map(([k]) => [k, ''])), kaufmaennisch: { abrechnungsart: 'einheitspreise', budget: '', zahlungsbedingungen: '', vertragsbedingungen: '', preisaufschluesselung: '' },
  freigabe: { budget: false, auftraggeber: true, adresse: true }, positionen: [], intern: '',
};
const SICHTBARKEITEN = [{ value: 'oeffentlich', label: 'Plattformweit' }, { value: 'privat', label: 'Nur Einladungen' }, { value: 'kombiniert', label: 'Beides' }];

/** Ausschreibung anlegen oder bearbeiten: Grunddaten, Beschreibung, Termine, Anforderungen, Kaufmännisches, Leistungsverzeichnis, Sichtbarkeit. */
export default function AusschreibungDialog({ open, onOpenChange, projectId, ausschreibung, gewerke, onSaved }) {
  const [f, setF] = useState(LEER);
  const [csv, setCsv] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setCsv('');
    setF(ausschreibung ? {
      ...LEER, ...Object.fromEntries(Object.keys(LEER).map((k) => [k, ausschreibung[k] ?? LEER[k]])),
      anforderungen: { ...LEER.anforderungen, ...(ausschreibung.anforderungen || {}) },
      kaufmaennisch: { ...LEER.kaufmaennisch, ...(ausschreibung.kaufmaennisch || {}), budget: ausschreibung.kaufmaennisch?.budget ?? '' },
      freigabe: { ...LEER.freigabe, ...(ausschreibung.freigabe || {}) }, positionen: (ausschreibung.positionen || []).map((p) => ({ ...p })),
      bewerbungsfrist: ausschreibung.bewerbungsfrist || '', angebotsfrist: ausschreibung.angebotsfrist || '', ausfuehrung_von: ausschreibung.ausfuehrung_von || '', ausfuehrung_bis: ausschreibung.ausfuehrung_bis || '',
    } : LEER);
  }, [open, ausschreibung]);
  const set = (k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [k]: v })); };
  const setTeil = (teil, k) => (e) => { const v = e.target.value; setF((x) => ({ ...x, [teil]: { ...x[teil], [k]: v } })); };
  const setPos = (i, k, v) => setF((x) => ({ ...x, positionen: x.positionen.map((p, j) => (j === i ? { ...p, [k]: v } : p)) }));
  const posNeu = () => setF((x) => ({ ...x, positionen: [...x.positionen, { nr: String((x.positionen.length + 1) * 10).padStart(3, '0'), leistung: '', menge: 1, einheit: 'Stück', beschreibung: '' }] }));
  const posWeg = (i) => setF((x) => ({ ...x, positionen: x.positionen.filter((_, j) => j !== i) }));
  const csvUebernehmen = () => { try { const p = csvZuPositionen(csv); if (!p.length) throw new Error('Keine Positionen gefunden'); setF((x) => ({ ...x, positionen: p })); setCsv(''); toast.success(`${p.length} Positionen übernommen`); } catch (err) { toast.error(err.message); } };
  const speichern = async (e) => {
    e.preventDefault();
    if (!f.titel.trim()) { toast.error('Bitte einen Titel eingeben'); return; }
    const body = {
      ...f, titel: f.titel.trim(), bewerbungsfrist: f.bewerbungsfrist || null, angebotsfrist: f.angebotsfrist || null, ausfuehrung_von: f.ausfuehrung_von || null, ausfuehrung_bis: f.ausfuehrung_bis || null,
      kaufmaennisch: { ...f.kaufmaennisch, budget: f.kaufmaennisch.budget === '' || f.kaufmaennisch.budget === null ? null : parseFloat(String(f.kaufmaennisch.budget).replace(',', '.')) || 0 },
      positionen: f.positionen.filter((p) => p.nr && p.leistung).map((p) => ({ ...p, nr: String(p.nr).trim(), menge: parseFloat(String(p.menge).replace(',', '.')) || 0 })),
    };
    setBusy(true);
    try {
      const r = ausschreibung ? await api.put(`/api/ausschreibungen/${ausschreibung.id}`, body) : await api.post(`/api/projekte/${projectId}/ausschreibungen`, body);
      toast.success(ausschreibung ? 'Ausschreibung gespeichert' : 'Ausschreibung als Entwurf angelegt');
      onSaved?.(r.ausschreibung);
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const liste = [...new Set([...(gewerke || GEWERKE_STANDARD), f.gewerk].filter(Boolean))];
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={ausschreibung ? 'Ausschreibung bearbeiten' : 'Neue Ausschreibung'} subtitle="Wird als Entwurf gespeichert und erst nach „Veröffentlichen“ für Firmen sichtbar." width="sm:max-w-3xl">
      <form onSubmit={speichern} className="space-y-6">
        <section className="space-y-3">
          <SectionLabel>Grunddaten</SectionLabel>
          <Field label="Titel"><TextInput value={f.titel} onChange={set('titel')} placeholder="z. B. Elektroinstallation Halle A" required /></Field>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Gewerk"><Select value={f.gewerk} onChange={set('gewerk')} className="w-full">{liste.map((g) => <option key={g} value={g}>{g}</option>)}</Select></Field>
            <Field label="Leistungsart"><TextInput value={f.leistungsart} onChange={set('leistungsart')} placeholder="z. B. Neubau, Sanierung" /></Field>
            <Field label="Ausführungsort"><TextInput value={f.ausfuehrungsort} onChange={set('ausfuehrungsort')} placeholder="leer = Projektadresse" /></Field>
          </div>
          <div>
            <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Sichtbarkeit</span>
            <Segmented value={f.sichtbarkeit} onChange={(v) => setF((x) => ({ ...x, sichtbarkeit: v }))} options={SICHTBARKEITEN} />
            <span className="block text-[12px] text-[#86868B] mt-1.5">Plattformweit: alle registrierten Firmen finden sie unter „Ausschreibungen“. Nur Einladungen: ausschließlich eingeladene Firmen. Beides: sichtbar und zusätzlich gezielte Einladungen.</span>
          </div>
        </section>
        <section className="space-y-3">
          <SectionLabel>Beschreibung</SectionLabel>
          <Field label="Beschreibung"><TextArea rows={4} value={f.beschreibung} onChange={set('beschreibung')} /></Field>
          <Field label="Leistungsumfang"><TextArea rows={3} value={f.leistungsumfang} onChange={set('leistungsumfang')} /></Field>
        </section>
        <section className="space-y-3">
          <SectionLabel>Termine</SectionLabel>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Field label="Bewerbungsfrist"><TextInput type="date" value={f.bewerbungsfrist} onChange={set('bewerbungsfrist')} /></Field>
            <Field label="Angebotsfrist"><TextInput type="date" value={f.angebotsfrist} onChange={set('angebotsfrist')} /></Field>
            <Field label="Ausführung ab"><TextInput type="date" value={f.ausfuehrung_von} onChange={set('ausfuehrung_von')} /></Field>
            <Field label="Ausführung bis"><TextInput type="date" value={f.ausfuehrung_bis} onChange={set('ausfuehrung_bis')} /></Field>
          </div>
        </section>
        <section className="space-y-3">
          <SectionLabel>Kaufmännisch</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Abrechnungsart"><Select value={f.kaufmaennisch.abrechnungsart} onChange={setTeil('kaufmaennisch', 'abrechnungsart')} className="w-full"><option value="pauschal">Pauschalpreis</option><option value="einheitspreise">Einheitspreise (Leistungsverzeichnis)</option><option value="stunden">Stundenbasiert</option><option value="gemischt">Gemischt</option></Select></Field>
            <Field label="Budgetrahmen (€ netto, optional)"><TextInput type="number" step="0.01" min="0" inputMode="decimal" value={f.kaufmaennisch.budget ?? ''} onChange={setTeil('kaufmaennisch', 'budget')} /></Field>
            <Field label="Zahlungsbedingungen"><TextInput value={f.kaufmaennisch.zahlungsbedingungen} onChange={setTeil('kaufmaennisch', 'zahlungsbedingungen')} placeholder="z. B. 30 Tage netto, Abschlagszahlungen monatlich" /></Field>
            <Field label="Gewünschte Preisaufschlüsselung"><TextInput value={f.kaufmaennisch.preisaufschluesselung} onChange={setTeil('kaufmaennisch', 'preisaufschluesselung')} placeholder="z. B. Lohn/Material getrennt" /></Field>
          </div>
          <Field label="Vertragsbedingungen"><TextArea rows={2} value={f.kaufmaennisch.vertragsbedingungen} onChange={setTeil('kaufmaennisch', 'vertragsbedingungen')} placeholder="z. B. VOB/B, Gewährleistung, Sicherheitseinbehalt" /></Field>
          <div className="rounded-2xl bg-[#F5F5F7] px-4 divide-y divide-black/[0.06]">
            <Toggle checked={!!f.freigabe.budget} onChange={(v) => setF((x) => ({ ...x, freigabe: { ...x.freigabe, budget: v } }))} label="Budgetrahmen für Bieter sichtbar" />
            <Toggle checked={f.freigabe.auftraggeber !== false} onChange={(v) => setF((x) => ({ ...x, freigabe: { ...x.freigabe, auftraggeber: v } }))} label="Firmenname des Auftraggebers sichtbar" hint="Sonst erscheint „Auftraggeber (auf Anfrage)“." />
            <Toggle checked={f.freigabe.adresse !== false} onChange={(v) => setF((x) => ({ ...x, freigabe: { ...x.freigabe, adresse: v } }))} label="Projektadresse sichtbar" />
          </div>
        </section>
        <section className="space-y-3">
          <SectionLabel>Leistungsverzeichnis (Positionen)</SectionLabel>
          {f.positionen.length > 0 && (
            <div className="space-y-2">
              <div className="hidden sm:grid grid-cols-[70px_1fr_90px_90px_36px] gap-2 text-[11px] font-semibold uppercase tracking-wider text-[#86868B] px-1"><span>Nr</span><span>Leistung</span><span>Menge</span><span>Einheit</span><span /></div>
              {f.positionen.map((p, i) => (
                <div key={i} className="grid grid-cols-[70px_1fr_36px] sm:grid-cols-[70px_1fr_90px_90px_36px] gap-2 items-center">
                  <TextInput value={p.nr} onChange={(e) => setPos(i, 'nr', e.target.value)} className="h-9 text-[13px]" />
                  <TextInput value={p.leistung} onChange={(e) => setPos(i, 'leistung', e.target.value)} className="h-9 text-[13px]" placeholder="Leistung" />
                  <TextInput value={p.menge} onChange={(e) => setPos(i, 'menge', e.target.value)} className="h-9 text-[13px] col-start-1 sm:col-start-auto" inputMode="decimal" />
                  <TextInput value={p.einheit} onChange={(e) => setPos(i, 'einheit', e.target.value)} className="h-9 text-[13px]" placeholder="m, Stück, h" />
                  <IconBtn size={32} variant="danger" onClick={() => posWeg(i)} title="Position entfernen"><Trash2 size={14} /></IconBtn>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2"><Btn type="button" size="sm" variant="soft" onClick={posNeu}><Plus size={15} /> Position</Btn></div>
          <details className="rounded-2xl bg-[#F5F5F7] p-3">
            <summary className="text-[13px] font-medium cursor-pointer">Aus Tabelle einfügen (CSV: Nr;Leistung;Menge;Einheit)</summary>
            <TextArea rows={4} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={'001;Kabeltrassen montieren;450;m\n002;Leitungen verlegen;1200;m'} className="mt-2 font-mono text-[12px]" />
            <Btn type="button" size="sm" variant="dark" className="mt-2" onClick={csvUebernehmen}><Upload size={14} /> Positionen übernehmen</Btn>
            <span className="block text-[12px] text-[#86868B] mt-2">GAEB-Dateien (X83) werden noch nicht gelesen – bitte das LV aus Excel als CSV kopieren.</span>
          </details>
        </section>
        <section className="space-y-3">
          <SectionLabel>Anforderungen</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {ANFORDERUNGEN.map(([k, label]) => <Field key={k} label={label}><TextArea rows={2} value={f.anforderungen[k] || ''} onChange={setTeil('anforderungen', k)} /></Field>)}
          </div>
        </section>
        <section className="space-y-3">
          <SectionLabel>Intern</SectionLabel>
          <Field label="Interne Vermerke (nie für Bieter sichtbar)"><TextArea rows={2} value={f.intern} onChange={set('intern')} placeholder="z. B. Zielpreis, Rückfallfirma" /></Field>
        </section>
        <div className="flex justify-end gap-2"><Btn type="button" variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn><Btn type="submit" loading={busy}>{ausschreibung ? 'Speichern' : 'Als Entwurf anlegen'}</Btn></div>
      </form>
    </Sheet>
  );
}
