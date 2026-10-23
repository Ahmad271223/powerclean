import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Loader2, CalendarDays, FolderKanban, ArrowLeft, ChevronRight, DatabaseBackup } from 'lucide-react';
import CompanyForm from '../components/CompanyForm';
import BackupDialog from '../components/BackupDialog';
import InstallBanner from '../components/InstallBanner';
import { StorageNotice } from '../components/Notices';
import { AppHeader, AppIcon, Btn, Card, IconBtn, PageHeading } from '../components/ui';
import { useStore } from '../lib/store';
import { initials, companyAddress } from '../lib/utils';

const LAST_KEY = 'ts-last-company';

/** App start: first-run setup, or choose the company (one company -> straight to its projects). */
export default function CompaniesPage() {
  const navigate = useNavigate();
  const { state, ready } = useStore();
  const [showNew, setShowNew] = useState(false);
  const [backup, setBackup] = useState(false);
  const companies = state.companies;

  useEffect(() => {
    if (ready && companies.length === 1 && !showNew) navigate(`/firma/${companies[0].id}`, { replace: true });
  }, [ready, companies, showNew, navigate]);

  const openCompany = (c) => {
    try { localStorage.setItem(LAST_KEY, c.id); } catch { /* ignore */ }
    navigate(`/firma/${c.id}`);
  };

  const firstRun = ready && companies.length === 0;
  const showSetup = firstRun || showNew;

  return (
    <div className="ts-app">
      <AppHeader
        left={(<><span className="w-9 h-9 rounded-xl bg-[#C41E3A] text-white flex items-center justify-center"><CalendarDays size={18} /></span><span className="font-semibold text-[17px]">Stundenzettel</span></>)}
        right={<IconBtn onClick={() => setBackup(true)} title="Datensicherung"><DatabaseBackup size={19} /></IconBtn>}
      />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <InstallBanner />
        <StorageNotice />
        {!ready ? (
          <div className="py-24 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={28} /></div>
        ) : showSetup ? (
          <Card className="p-6 sm:p-10 max-w-3xl mx-auto">
            {!firstRun && <button onClick={() => setShowNew(false)} className="text-[14px] text-[#6E6E73] flex items-center gap-1 mb-5"><ArrowLeft size={16} /> Zurück</button>}
            <h1 className="text-[32px] leading-none">{firstRun ? 'Willkommen' : 'Weitere Firma'}</h1>
            <p className="text-[15px] text-[#6E6E73] mt-2 mb-8">
              {firstRun
                ? 'Richte einmal deine Firma ein. Logo und Firmendaten erscheinen danach automatisch auf allen Stundenzetteln und Rechnungen. Alles bleibt auf diesem Gerät.'
                : 'Jede Firma hat eigene Projekte, Einstellungen und eine eigene Rechnungsnummernfolge.'}
            </p>
            <CompanyForm company={null} submitLabel={firstRun ? 'Los geht’s' : 'Firma anlegen'} onCancel={firstRun ? undefined : () => setShowNew(false)} onSaved={(c) => { setShowNew(false); openCompany(c); }} />
            {firstRun && (
              <p className="text-[13px] text-[#86868B] mt-6 text-center">Du hast schon eine Sicherung? <button onClick={() => setBackup(true)} className="text-[#C41E3A] font-medium">Wiederherstellen</button></p>
            )}
          </Card>
        ) : (
          <>
            <PageHeading title="Meine Firmen" subtitle="Erst die Firma, dann das Projekt." action={<Btn onClick={() => setShowNew(true)}><Plus size={18} /> Neue Firma</Btn>} className="mb-8" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {companies.map((c) => {
                const n = state.projects.filter((p) => p.company_id === c.id).length;
                return (
                  <Card key={c.id} role="button" tabIndex={0} onClick={() => openCompany(c)} onKeyDown={(e) => { if (e.key === 'Enter') openCompany(c); }} className="p-5 flex items-center gap-4 cursor-pointer transition-all hover:shadow-card-hover active:scale-[0.99]">
                    <AppIcon logo={c.logo} text={initials(c.name)} size={64} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[17px] font-semibold truncate">{c.name}</div>
                      <div className="text-[13px] text-[#6E6E73] truncate">{companyAddress(c) || c.owner || '–'}</div>
                      <div className="text-[12px] text-[#86868B] mt-1 flex items-center gap-1"><FolderKanban size={12} /> {n} Projekte</div>
                    </div>
                    <ChevronRight size={20} className="text-[#C7C7CC]" />
                  </Card>
                );
              })}
            </div>
          </>
        )}
      </main>
      <BackupDialog open={backup} onOpenChange={setBackup} />
    </div>
  );
}
