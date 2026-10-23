import React, { useEffect, useState } from 'react';
import { Check, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { PROJECT_COLORS } from '../lib/utils';
import { api } from '../lib/api';
import { Sheet, Btn, Field, TextInput, TextArea, SectionLabel, Toggle, Chip } from './ui';

const EMPTY = { name: '', customer_id: '', customer_name: '', customer_address: '', address: '', schedule: '', employee_ids: [], hourly_rate: '', color: PROJECT_COLORS[0], notes: '', archived: false, default_workers: 1, reverse_charge: false, budget_hours_month: '', budget_warn_percent: 80 };

/** Projekt anlegen / ändern: Kunde aus dem Kundenstamm, zugewiesene Mitarbeiter, § 13b, Einsatzzeiten. */
export default function ProjectDialog({ open, onOpenChange, project, defaultRate = 0, onSaved, onDeleted }) {
  const [form, setForm] = useState(EMPTY);
  const [kunden, setKunden] = useState([]);
  const [mitarbeiter, setMitarbeiter] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(project ? { ...EMPTY, ...project, customer_id: project.customer_id || '', hourly_rate: project.hourly_rate ? String(project.hourly_rate) : '', employee_ids: project.employee_ids || [], budget_hours_month: project.budget_hours_month ? String(project.budget_hours_month) : '', budget_warn_percent: project.budget_warn_percent || 80 } : EMPTY);
    Promise.all([api.get('/api/kunden'), api.get('/api/mitarbeiter')])
      .then(([k, m]) => { setKunden(k.kunden); setMitarbeiter(m.mitarbeiter.filter((x) => x.active !== false)); })
      .catch((err) => toast.error(err.message));
  }, [open, project]);

  const set = (key) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [key]: v })); };
  const rateText = defaultRate ? String(defaultRate).replace('.', ',') : '';
  const kundeWaehlen = (id) => {
    const k = kunden.find((x) => x.id === id);
    setForm((f) => ({ ...f, customer_id: id, customer_name: k ? k.name : f.customer_name, reverse_charge: k ? !!k.reverse_charge : f.reverse_charge }));
  };
  const toggleMa = (id) => setForm((f) => ({ ...f, employee_ids: f.employee_ids.includes(id) ? f.employee_ids.filter((x) => x !== id) : [...f.employee_ids, id] }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Bitte einen Projektnamen eingeben'); return; }
    const data = {
      name: form.name.trim(), customer_id: form.customer_id || null, customer_name: form.customer_name.trim(), customer_address: (form.customer_address || '').trim(),
      address: (form.address || '').trim(), schedule: (form.schedule || '').trim(), employee_ids: form.employee_ids,
      hourly_rate: parseFloat(String(form.hourly_rate).replace(',', '.')) || 0, color: form.color, notes: form.notes || '', archived: !!form.archived,
      default_workers: Math.max(1, Math.min(99, parseInt(form.default_workers, 10) || 1)), reverse_charge: !!form.reverse_charge,
      budget_hours_month: parseFloat(String(form.budget_hours_month).replace(',', '.')) || 0,
      budget_warn_percent: Math.max(1, Math.min(100, parseInt(form.budget_warn_percent, 10) || 80)),
    };
    setBusy(true);
    try {
      const r = project ? await api.put(`/api/projekte/${project.id}`, data) : await api.post('/api/projekte', data);
      toast.success(project ? 'Projekt gespeichert' : 'Projekt angelegt');
      onSaved?.(r.projekt);
      onOpenChange(false);
    } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };

  const remove = async () => {
    if (!project || !window.confirm(`Projekt "${project.name}" mit allen Einträgen wirklich löschen? (Archivieren ist meist besser.)`)) return;
    try { await api.del(`/api/projekte/${project.id}`); toast.success('Projekt gelöscht'); onOpenChange(false); onDeleted?.(project); }
    catch (err) { toast.error(err.message); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={project ? 'Projekt bearbeiten' : 'Neues Projekt'} subtitle="Erscheint auf den Stundenzetteln und der Monatsrechnung." width="sm:max-w-2xl">
      <form onSubmit={submit} className="space-y-6">
        <div className="flex items-center gap-4">
          <span className="w-16 h-16 rounded-[18px] shrink-0 flex items-center justify-center text-white text-2xl font-bold" style={{ background: `linear-gradient(145deg, ${form.color}, ${form.color}CC)` }}>{(form.name.trim()[0] || '?').toUpperCase()}</span>
          <Field label="Projekt / Objekt" className="flex-1"><TextInput value={form.name} onChange={set('name')} placeholder="z. B. Sparkasse Hauptstelle" required /></Field>
        </div>
        <div className="flex flex-wrap gap-2.5">
          {PROJECT_COLORS.map((c) => (
            <button key={c} type="button" onClick={() => setForm((f) => ({ ...f, color: c }))} className="w-8 h-8 rounded-full flex items-center justify-center transition-transform active:scale-90" style={{ backgroundColor: c, boxShadow: form.color === c ? `0 0 0 2px #fff, 0 0 0 4px ${c}` : 'none' }} aria-label={`Farbe ${c}`}>
              {form.color === c && <Check size={15} className="text-white" />}
            </button>
          ))}
        </div>

        <section className="space-y-3">
          <SectionLabel>Auftraggeber</SectionLabel>
          <Field label="Kunde aus dem Kundenstamm">
            <select value={form.customer_id} onChange={(e) => kundeWaehlen(e.target.value)} className="w-full h-11 rounded-xl bg-[#F5F5F7] px-3.5 text-[15px] outline-none">
              <option value="">– frei eintragen –</option>
              {kunden.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
            </select>
          </Field>
          {!form.customer_id && (
            <>
              <Field label="Kunde / Firma"><TextInput value={form.customer_name} onChange={set('customer_name')} placeholder="Firma oder Name" /></Field>
              <Field label="Rechnungsadresse"><TextArea value={form.customer_address} onChange={set('customer_address')} rows={2} placeholder={'Straße Nr.\nPLZ Ort'} /></Field>
            </>
          )}
          <div className="rounded-2xl bg-[#F5F5F7] px-4">
            <Toggle checked={!!form.reverse_charge} onChange={(v) => setForm((f) => ({ ...f, reverse_charge: v }))} label="Rechnung ohne Umsatzsteuer (§ 13b UStG)" hint="Für Auftraggeber, die selbst Gebäudereinigung erbringen (Subunternehmer-Rechnung)." />
          </div>
        </section>

        <section className="space-y-3">
          <SectionLabel>Einsatz</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Einsatzort (Adresse)"><TextInput value={form.address} onChange={set('address')} placeholder="Straße, Ort" /></Field>
            <Field label="Feste Zeiten (Info)"><TextInput value={form.schedule} onChange={set('schedule')} placeholder="z. B. Mo–Fr 06:00–09:00" /></Field>
          </div>
          <div>
            <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Zugewiesene Mitarbeiter</span>
            <div className="flex flex-wrap gap-2">
              {mitarbeiter.map((m) => <Chip key={m.id} active={form.employee_ids.includes(m.id)} onClick={() => toggleMa(m.id)}>{m.name}</Chip>)}
              {!mitarbeiter.length && <span className="text-[13px] text-[#86868B]">Noch keine Mitarbeiter eingeladen.</span>}
            </div>
            <span className="block text-[12px] text-[#86868B] mt-1.5">Niemand ausgewählt = alle Mitarbeiter sehen das Projekt und können darauf stempeln.</span>
          </div>
        </section>

        <section className="space-y-3">
          <SectionLabel>Abrechnung</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Stundensatz (€ netto)" hint={rateText ? `Leer = Firmenstandard ${rateText} €` : undefined}>
              <TextInput type="number" step="0.01" min="0" inputMode="decimal" value={form.hourly_rate} onChange={set('hourly_rate')} placeholder={rateText || 'z. B. 32,50'} />
            </Field>
            <Field label="Mitarbeiter je Einsatz (für Einträge ohne Person)">
              <TextInput type="number" min="1" max="99" inputMode="numeric" value={form.default_workers} onChange={set('default_workers')} />
            </Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Budget (Stunden je Monat)" hint="Leer = kein Budget. Vertragsstunden des Objekts.">
              <TextInput type="number" step="0.5" min="0" inputMode="decimal" value={form.budget_hours_month} onChange={set('budget_hours_month')} placeholder="z. B. 60" />
            </Field>
            <Field label="Warnung ab (%)"><TextInput type="number" min="1" max="100" inputMode="numeric" value={form.budget_warn_percent} onChange={set('budget_warn_percent')} /></Field>
          </div>
          <Field label="Notizen"><TextArea rows={2} value={form.notes} onChange={set('notes')} placeholder="Schlüssel, Besonderheiten, Ansprechpartner" /></Field>
        </section>

        {project && (
          <div className="rounded-2xl bg-[#F5F5F7] px-4">
            <Toggle checked={!!form.archived} onChange={(v) => setForm((f) => ({ ...f, archived: v }))} label="Projekt archivieren" hint="Wird ausgeblendet, alle Daten und PDFs bleiben erhalten." />
          </div>
        )}

        <div className="flex items-center justify-between gap-3 pt-1">
          {project ? <Btn type="button" variant="danger" size="sm" onClick={remove}><Trash2 size={15} /> Löschen</Btn> : <span />}
          <div className="flex gap-2">
            <Btn type="button" variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn>
            <Btn type="submit" loading={busy}>Speichern</Btn>
          </div>
        </div>
      </form>
    </Sheet>
  );
}
