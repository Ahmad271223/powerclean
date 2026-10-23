import React, { useEffect, useState } from 'react';
import { Check, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { PROJECT_COLORS } from '../lib/utils';
import { addProject, updateProject, deleteProject } from '../lib/store';
import { Sheet, Btn, Field, TextInput, TextArea, SectionLabel, Toggle, Chip } from './ui';

const EMPTY = { name: '', customer_name: '', customer_address: '', employee_name: '', hourly_rate: '', color: PROJECT_COLORS[0], notes: '', archived: false, default_workers: 1 };

/** Create / edit a project. `project` = null -> create inside `companyId`. */
export default function ProjectDialog({ open, onOpenChange, project, companyId, defaultRate = 0, onSaved, onDeleted }) {
  const [form, setForm] = useState(EMPTY);

  useEffect(() => {
    if (open) setForm(project ? { ...EMPTY, ...project, hourly_rate: project.hourly_rate ? String(project.hourly_rate) : '' } : EMPTY);
  }, [open, project]);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const rateText = defaultRate ? String(defaultRate).replace('.', ',') : '';

  const submit = (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Bitte einen Projektnamen eingeben'); return; }
    const data = {
      name: form.name.trim(),
      customer_name: form.customer_name.trim(),
      customer_address: form.customer_address.trim(),
      employee_name: form.employee_name.trim(),
      hourly_rate: parseFloat(String(form.hourly_rate).replace(',', '.')) || 0,
      color: form.color,
      notes: form.notes || '',
      archived: !!form.archived,
      default_workers: Math.max(1, Math.min(99, parseInt(form.default_workers, 10) || 1)),
    };
    const saved = project ? updateProject(project.id, data) : addProject({ ...data, company_id: companyId });
    toast.success(project ? 'Projekt gespeichert' : 'Projekt angelegt');
    onSaved(saved);
    onOpenChange(false);
  };

  const remove = () => {
    if (!project) return;
    if (!window.confirm(`Projekt "${project.name}" mit allen Einträgen wirklich löschen?`)) return;
    deleteProject(project.id);
    toast.success('Projekt gelöscht');
    onOpenChange(false);
    onDeleted?.(project);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={project ? 'Projekt bearbeiten' : 'Neues Projekt'} subtitle="Erscheint auf den Stundenzetteln und der Monatsrechnung.">
      <form onSubmit={submit} className="space-y-6" data-testid="project-dialog">
        <div className="flex items-center gap-4">
          <span className="w-16 h-16 rounded-[18px] shrink-0 flex items-center justify-center text-white text-2xl font-bold" style={{ background: `linear-gradient(145deg, ${form.color}, ${form.color}CC)` }}>
            {(form.name.trim()[0] || '?').toUpperCase()}
          </span>
          <Field label="Projekt / Objekt" className="flex-1">
            <TextInput value={form.name} onChange={set('name')} placeholder="z. B. Baustelle Nord" required data-testid="project-name" />
          </Field>
        </div>

        <div className="flex flex-wrap gap-2.5">
          {PROJECT_COLORS.map((c) => (
            <button key={c} type="button" onClick={() => setForm({ ...form, color: c })} className="w-8 h-8 rounded-full flex items-center justify-center transition-transform active:scale-90" style={{ backgroundColor: c, boxShadow: form.color === c ? `0 0 0 2px #fff, 0 0 0 4px ${c}` : 'none' }} aria-label={`Farbe ${c}`}>
              {form.color === c && <Check size={15} className="text-white" />}
            </button>
          ))}
        </div>

        <section className="space-y-3">
          <SectionLabel>Auftraggeber</SectionLabel>
          <Field label="Kunde / Firma"><TextInput value={form.customer_name} onChange={set('customer_name')} placeholder="Firma oder Name" data-testid="project-customer" /></Field>
          <Field label="Rechnungsadresse"><TextArea value={form.customer_address} onChange={set('customer_address')} rows={2} placeholder={'Straße Nr.\nPLZ Ort'} /></Field>
        </section>

        <section className="space-y-3">
          <SectionLabel>Abrechnung</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Mitarbeiter"><TextInput value={form.employee_name} onChange={set('employee_name')} placeholder="Name auf dem Stundenzettel" /></Field>
            <Field label="Stundensatz (€ netto)" hint={rateText ? `Leer = Firmenstandard ${rateText} €` : undefined}>
              <TextInput type="number" step="0.01" min="0" inputMode="decimal" value={form.hourly_rate} onChange={set('hourly_rate')} placeholder={rateText || 'z. B. 32,50'} />
            </Field>
          </div>
          <div>
            <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">Mitarbeiter pro Einsatz (Standard)</span>
            <div className="flex flex-wrap items-center gap-2">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <Chip key={n} active={Number(form.default_workers) === n} onClick={() => setForm({ ...form, default_workers: n })}>{n}</Chip>
              ))}
              <TextInput type="number" min="1" max="99" inputMode="numeric" value={form.default_workers} onChange={set('default_workers')} className="w-20 h-9 text-center" aria-label="Mitarbeiter" />
            </div>
            <span className="block text-[12px] text-[#86868B] mt-1.5">Wird bei jedem Tageseintrag vorausgefüllt und kann dort pro Tag geändert werden. Stunden zählen pro Mitarbeiter.</span>
          </div>
        </section>

        {project && (
          <div className="rounded-2xl bg-[#F5F5F7] px-4">
            <Toggle checked={!!form.archived} onChange={(v) => setForm({ ...form, archived: v })} label="Projekt archivieren" hint="Wird in der Projektliste ausgeblendet, alle Daten und PDFs bleiben erhalten." />
          </div>
        )}

        <div className="flex items-center justify-between gap-3 pt-1">
          {project ? <Btn type="button" variant="danger" size="sm" onClick={remove}><Trash2 size={15} /> Löschen</Btn> : <span />}
          <div className="flex gap-2">
            <Btn type="button" variant="soft" onClick={() => onOpenChange(false)}>Abbrechen</Btn>
            <Btn type="submit" data-testid="project-save">Speichern</Btn>
          </div>
        </div>
      </form>
    </Sheet>
  );
}
