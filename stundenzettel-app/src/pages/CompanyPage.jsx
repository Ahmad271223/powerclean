import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Plus, Pencil, Loader2, FolderKanban, Receipt, FileStack, RotateCcw, ArrowLeftRight, Settings, ChevronRight,
  DatabaseBackup, Download, Search, Archive, X,
} from 'lucide-react';
import ProjectDialog from '../components/ProjectDialog';
import CompanyDialog from '../components/CompanyDialog';
import BackupDialog from '../components/BackupDialog';
import { StorageNotice, BackupNotice } from '../components/Notices';
import InstallBanner from '../components/InstallBanner';
import { AppHeader, AppIcon, Btn, Card, Empty, IconBtn, Segmented, Select, TextInput } from '../components/ui';
import { useStore, companyProjects, companyInvoices, deleteInvoice, projectEntries, findProject, ensureEntries, updateInvoiceTotals } from '../lib/store';
import { computeInvoice, invoicePdf, monthPdf, preloadLogo } from '../lib/pdf';
import { fmtDecimalHours, fmtEur, fmtDate, fromKey, MONTHS_DE, monthLastDay, toKey, monthWeeks, addDays } from '../lib/dates';
import { initials, companyAddress, deliverPdf } from '../lib/utils';

const activityKey = (p) => String(p.last_activity_at || p.created_at || '');

/** Home of one company: "Meine Projekte" (searchable, archive) and "Rechnungen", plus settings and backup. */
export default function CompanyPage() {
  const { companyId } = useParams();
  const navigate = useNavigate();
  const { state, ready } = useStore();
  const [tab, setTab] = useState('projekte');
  const [search, setSearch] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [invoiceYear, setInvoiceYear] = useState('all');
  const [projectDialog, setProjectDialog] = useState(false);
  const [editProject, setEditProject] = useState(null);
  const [companyDialog, setCompanyDialog] = useState(false);
  const [backup, setBackup] = useState(false);
  const [busy, setBusy] = useState('');

  const company = state.companies.find((c) => c.id === companyId) || null;
  useEffect(() => { if (ready && !company) navigate('/', { replace: true }); }, [ready, company, navigate]);
  useEffect(() => { if (company) preloadLogo(company); }, [company]);

  const allProjects = useMemo(() => (company ? companyProjects(companyId) : []), [company, companyId, state.projects]); // eslint-disable-line react-hooks/exhaustive-deps
  const archivedCount = allProjects.filter((p) => p.archived).length;
  const activeCount = allProjects.length - archivedCount;
  const q = search.trim().toLowerCase();
  const projects = useMemo(() => allProjects
    .filter((p) => (showArchived ? p.archived : !p.archived))
    .filter((p) => !q || p.name.toLowerCase().includes(q) || (p.customer_name || '').toLowerCase().includes(q))
    .sort((a, b) => activityKey(b).localeCompare(activityKey(a)) || a.name.localeCompare(b.name, 'de')), [allProjects, showArchived, q]);

  const invoicesAll = useMemo(() => (company ? companyInvoices(companyId) : []), [company, companyId, state.invoices]); // eslint-disable-line react-hooks/exhaustive-deps
  const invoiceYears = useMemo(() => [...new Set(invoicesAll.map((i) => i.year))].sort((a, b) => b - a), [invoicesAll]);
  const invoices = invoiceYear === 'all' ? invoicesAll : invoicesAll.filter((i) => i.year === Number(invoiceYear));
  const totalGross = invoices.reduce((s, i) => s + (Number(i.gross) || 0), 0);

  if (!ready || !company) return <div className="ts-app py-24 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={28} /></div>;

  const openNew = () => { setEditProject(null); setProjectDialog(true); };
  const openEdit = (e, project) => { e.stopPropagation(); setEditProject(project); setProjectDialog(true); };

  /** Regenerate a PDF for an invoice (loads the project's entries first). */
  const regenerate = async (inv, kind, mode) => {
    const key = `${kind}-${inv.id}`;
    setBusy(key);
    try {
      const project = findProject(inv.project_id);
      if (!project) throw new Error('Projekt nicht gefunden');
      await ensureEntries(project.id);
      const m0 = inv.month - 1;
      const first = toKey(new Date(inv.year, m0, 1));
      const last = toKey(monthLastDay(inv.year, m0));
      const monthE = projectEntries(project.id, first, last);
      const calc = computeInvoice(project, company, inv.year, m0, monthE);
      const current = updateInvoiceTotals(inv.id, calc) || inv;
      let result;
      if (kind === 'month') {
        const weeks = monthWeeks(inv.year, m0);
        result = monthPdf(project, company, inv.year, m0, projectEntries(project.id, toKey(weeks[0]), toKey(addDays(weeks[weeks.length - 1], 6))), current);
      } else {
        result = invoicePdf(project, company, inv.year, m0, monthE, current);
      }
      await deliverPdf(result, mode);
    } catch (err) {
      console.error(err);
      toast.error(err.message || 'PDF konnte nicht erstellt werden');
    } finally { setBusy(''); }
  };

  const resetInvoice = (inv) => {
    if (!window.confirm(`Rechnungsnummer ${inv.number} zurücksetzen? Beim nächsten PDF wird eine neue Nummer mit aktuellem Datum vergeben.`)) return;
    deleteInvoice(inv.id);
    toast.success('Rechnungsnummer zurückgesetzt');
  };

  return (
    <div className="ts-app">
      <AppHeader
        left={(
          <>
            <AppIcon logo={company.logo} text={initials(company.name)} size={40} className="rounded-xl" />
            <div className="min-w-0">
              <div className="font-semibold text-[16px] leading-tight truncate">{company.name}</div>
              <div className="text-[12px] text-[#6E6E73] truncate">{companyAddress(company) || company.owner}</div>
            </div>
          </>
        )}
        right={(
          <>
            {state.companies.length > 1 && <IconBtn onClick={() => navigate('/')} title="Firma wechseln"><ArrowLeftRight size={18} /></IconBtn>}
            <IconBtn onClick={() => setBackup(true)} title="Datensicherung"><DatabaseBackup size={18} /></IconBtn>
            <Btn variant="soft" size="sm" onClick={() => setCompanyDialog(true)}><Settings size={16} /> <span className="hidden sm:inline">Firma</span></Btn>
          </>
        )}
      />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <InstallBanner />
        <StorageNotice />
        <BackupNotice onBackup={() => setBackup(true)} />

        <div className="flex justify-center mb-7">
          <Segmented value={tab} onChange={setTab} options={[{ value: 'projekte', label: 'Meine Projekte', icon: FolderKanban }, { value: 'rechnungen', label: 'Rechnungen', icon: Receipt }]} />
        </div>

        {tab === 'projekte' && (
          <>
            <div className="flex items-end justify-between gap-4 mb-4">
              <div>
                <h1 className="text-[28px] sm:text-[34px] leading-none">{showArchived ? 'Archiv' : 'Meine Projekte'}</h1>
                <p className="text-[14px] text-[#6E6E73] mt-1.5">
                  {showArchived ? `${archivedCount} archivierte Projekte` : 'Projekt antippen, Tag wählen, Zeit eintragen. Fertig.'}
                </p>
              </div>
              <Btn onClick={openNew}><Plus size={18} /> <span className="hidden sm:inline">Neues Projekt</span><span className="sm:hidden">Neu</span></Btn>
            </div>

            {(allProjects.length > 3 || archivedCount > 0) && (
              <div className="flex flex-wrap items-center gap-2 mb-5">
                <div className="relative flex-1 min-w-[200px]">
                  <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#86868B]" />
                  <TextInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Projekt oder Kunde suchen" className="pl-10 bg-white shadow-card border-0" />
                  {search && <button type="button" onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/[0.06] flex items-center justify-center" aria-label="Suche löschen"><X size={13} /></button>}
                </div>
                {archivedCount > 0 && (
                  <Btn variant={showArchived ? 'dark' : 'soft'} size="sm" onClick={() => setShowArchived((v) => !v)}>
                    <Archive size={15} /> {showArchived ? `Aktive (${activeCount})` : `Archiv (${archivedCount})`}
                  </Btn>
                )}
              </div>
            )}

            {projects.length === 0 ? (
              <Card>
                {allProjects.length === 0
                  ? <Empty icon={FolderKanban} title="Noch keine Projekte" text="Jedes Projekt bekommt seinen eigenen Kalender." action={<Btn onClick={openNew}><Plus size={18} /> Erstes Projekt anlegen</Btn>} />
                  : <Empty icon={Search} title="Nichts gefunden" text={showArchived ? 'Keine archivierten Projekte passen zur Suche.' : 'Kein aktives Projekt passt zur Suche.'} />}
              </Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {projects.map((p) => (
                  <Card key={p.id} role="button" tabIndex={0} onClick={() => navigate(`/projekt/${p.id}`)} onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/projekt/${p.id}`); }} className="group p-5 flex items-center gap-4 cursor-pointer transition-all hover:shadow-card-hover active:scale-[0.99]">
                    <AppIcon color={p.color} text={initials(p.name)} size={60} className={p.archived ? 'opacity-50 grayscale' : ''} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[17px] font-semibold truncate">{p.name}</div>
                      <div className="text-[13px] text-[#6E6E73] truncate">{p.customer_name || 'Kein Auftraggeber'}</div>
                      <div className="text-[12px] text-[#86868B] mt-1">
                        {fmtDecimalHours(p.total_minutes)} Std. · {p.entry_count} Einträge
                        {p.last_activity_at ? ` · zuletzt ${fmtDate(fromKey(p.last_activity_at))}` : ''}
                      </div>
                    </div>
                    <IconBtn size={32} onClick={(e) => openEdit(e, p)} title="Projekt bearbeiten" className="text-[#86868B]"><Pencil size={15} /></IconBtn>
                    <ChevronRight size={20} className="text-[#C7C7CC] -ml-1" />
                  </Card>
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'rechnungen' && (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
              <div>
                <h1 className="text-[28px] sm:text-[34px] leading-none">Rechnungen</h1>
                <p className="text-[14px] text-[#6E6E73] mt-1.5">Alle Monatsrechnungen dieser Firma. Neue Rechnungen entstehen im Kalender eines Projekts.</p>
              </div>
              <div className="flex items-center gap-3">
                {invoiceYears.length > 1 && (
                  <Select value={invoiceYear} onChange={(e) => setInvoiceYear(e.target.value)}>
                    <option value="all">Alle Jahre</option>
                    {invoiceYears.map((y) => <option key={y} value={y}>{y}</option>)}
                  </Select>
                )}
                {invoices.length > 0 && (
                  <div className="text-right shrink-0">
                    <div className="text-[12px] text-[#6E6E73]">Summe brutto ({invoices.length})</div>
                    <div className="text-[24px] font-bold tracking-tight text-[#C41E3A] leading-none">{fmtEur(totalGross)}</div>
                  </div>
                )}
              </div>
            </div>
            {invoices.length === 0 ? (
              <Card><Empty icon={Receipt} title="Noch keine Rechnungen" text="Öffne ein Projekt und erstelle über „Monats-PDF“ oder „Rechnung“ die erste Rechnung." /></Card>
            ) : (
              <div className="space-y-3">
                {invoices.map((inv) => {
                  const project = findProject(inv.project_id);
                  return (
                    <Card key={inv.id} className="p-4 sm:p-5 flex flex-wrap items-center gap-3">
                      <div className="flex-1 min-w-[200px]">
                        <div className="text-[15px] font-semibold">{inv.number} <span className="text-[#86868B] font-normal text-[13px]">· {fmtDate(fromKey(inv.invoice_date))}</span></div>
                        <div className="text-[13px] text-[#6E6E73] truncate">{project?.name || 'Projekt gelöscht'}{project?.customer_name ? ` · ${project.customer_name}` : ''} · {MONTHS_DE[inv.month - 1]} {inv.year}</div>
                        <div className="text-[12px] text-[#86868B] mt-0.5">{inv.total_minutes != null ? `${fmtDecimalHours(inv.total_minutes)} Std. · netto ${fmtEur(inv.net || 0)}` : 'Beträge beim nächsten PDF'}</div>
                      </div>
                      <div className="text-[18px] font-bold tracking-tight">{inv.gross != null ? fmtEur(inv.gross) : '–'}</div>
                      <div className="flex items-center gap-1">
                        <Btn size="sm" onClick={() => regenerate(inv, 'invoice')} loading={busy === `invoice-${inv.id}`} disabled={!project}><Receipt size={15} /> Rechnung</Btn>
                        <IconBtn size={34} variant="soft" onClick={() => regenerate(inv, 'month')} disabled={!project || busy === `month-${inv.id}`} title="Monats-PDF (Stundenzettel + Rechnung)"><FileStack size={15} /></IconBtn>
                        <IconBtn size={34} variant="soft" onClick={() => regenerate(inv, 'invoice', 'download')} disabled={!project} title="Rechnung herunterladen"><Download size={15} /></IconBtn>
                        <IconBtn size={34} onClick={() => resetInvoice(inv)} title="Rechnungsnummer zurücksetzen" className="text-[#A1A1A6]"><RotateCcw size={14} /></IconBtn>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      <ProjectDialog open={projectDialog} onOpenChange={setProjectDialog} project={editProject} companyId={companyId} defaultRate={company.default_hourly_rate || 0} onSaved={() => {}} onDeleted={() => {}} />
      <CompanyDialog open={companyDialog} onOpenChange={setCompanyDialog} company={company} onSaved={() => {}} onDeleted={() => navigate('/', { replace: true })} />
      <BackupDialog open={backup} onOpenChange={setBackup} />
    </div>
  );
}
