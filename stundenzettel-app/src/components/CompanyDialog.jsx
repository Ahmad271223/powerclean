import React from 'react';
import { Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { deleteCompany } from '../lib/store';
import CompanyForm from './CompanyForm';
import { Sheet, Btn } from './ui';

/** "Firmeneinstellungen": edit (or delete) an existing company. */
export default function CompanyDialog({ open, onOpenChange, company, onSaved, onDeleted }) {
  const remove = () => {
    if (!company) return;
    const typed = window.prompt(`Firma "${company.name}" mit ALLEN Projekten, Arbeitszeiten und Rechnungen löschen?\nZur Bestätigung den Firmennamen eingeben:`);
    if (typed === null) return;
    if (typed.trim() !== company.name.trim()) { toast.error('Firmenname stimmt nicht überein, nichts gelöscht'); return; }
    deleteCompany(company.id);
    toast.success('Firma gelöscht');
    onOpenChange(false);
    onDeleted?.(company);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Firmeneinstellungen" subtitle="Gilt für alle Projekte, Stundenzettel und Rechnungen dieser Firma." width="sm:max-w-2xl">
      {open && <CompanyForm company={company} onSaved={(c) => { onSaved(c); onOpenChange(false); }} onCancel={() => onOpenChange(false)} />}
      {company && (
        <div className="mt-8 pt-5 border-t border-black/[0.06]">
          <Btn variant="danger" size="sm" onClick={remove} data-testid="company-delete"><Trash2 size={15} /> Firma und alle Daten löschen</Btn>
        </div>
      )}
    </Sheet>
  );
}
