import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import {
  LogOut, Plus, Pencil, Loader2, FolderKanban, Receipt, FileStack, RotateCcw, ArrowLeftRight, Settings, ChevronRight,
} from 'lucide-react';
import TsLogin from '../components/stundenzettel/TsLogin';
import ProjectDialog from '../components/stundenzettel/ProjectDialog';
import CompanyDialog from '../components/stundenzettel/CompanyDialog';
import { AppHeader, AppIcon, Btn, Card, Empty, IconBtn, Segmented } from '../components/stundenzettel/ui';
import {
  api, getToken, clearToken, fetchPdf, fmtDecimalHours, fmtEur, fmtDate, fromKey, initials, companyAddress, MONTHS_DE, LAST_COMPANY_KEY,
} from '@/lib/ts';

/**
 * Home of ONE company: "Meine Projekte" (tiles) and "Rechnungen", plus the company settings sheet.
 */
export default function FirmaPage() {
  const { companyId } = useParams();
  const navigate = useNavigate();
  const [authed, setAuthed] = useState(!!getToken());
  const [company, setCompany] = useState(null);
  const [companyCount, setCompanyCount] = useState(1);
  const [projects, setProjects] = useState([]);
  const [invoices, setInvoices] = useState(null);
  const [tab, setTab] = useState('projekte');
  const [loading, setLoading] = useState(true);
  const [projectDialog, setProjectDialog] = useState(false);
  const [editProject, setEditProject] = useState(null);
  const [companyDialog, setCompanyDialog] = useState(false);
  const [pdfBusy, setPdfBusy] = useState('');

  const logout = useCallback(() => { clearToken(); setAuthed(false); }, []);

  const handleError = useCallback((error, message) => {
    if (error.response?.status === 401) { logout(); return; }
    if (error.response?.status === 404) { toast.error('Firma nicht gefunden'); navigate('/stundenzettel'); return; }
    console.error(error);
    toast.error(message);
  }, [logout, navigate]);

  const loadCompany = useCallback(async () => {
    try {
      const [c, all] = await Promise.all([api.get(`/ts/companies/${companyId}`), api.get('/ts/companies')]);
      setCompany(c.data);
      setCompanyCount((all.data.companies || []).length);
      try { localStorage.setItem(LAST_COMPANY_KEY, companyId); } catch { /* ignore */ }
    } catch (error) { handleError(error, 'Firma konnte nicht geladen werden'); }
  }, [companyId, handleError]);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/ts/companies/${companyId}/projects`);
      setProjects(res.data.projects || []);
    } catch (error) { handleError(error, 'Projekte konnten nicht geladen werden'); } finally { setLoading(false); }
  }, [companyId, handleError]);

  const loadInvoices = useCallback(async () => {
    try {
      const res = await api.get(`/ts/companies/${companyId}/invoices`);
      setInvoices(res.data.invoices || []);
    } catch (error) { handleError(error, 'Rechnungen konnten nicht geladen werden'); }
  }, [companyId, handleError]);

  useEffect(() => { if (authed) { loadCompany(); loadProjects(); } }, [authed, loadCompany, loadProjects]);
  useEffect(() => { if (authed && tab === 'rechnungen') loadInvoices(); }, [authed, tab, loadInvoices]);

  if (!authed) {
    return (<><Toaster position="top-center" richColors /><TsLogin onLogin={() => setAuthed(true)} /></>);
  }

  const openNew = () => { setEditProject(null); setProjectDialog(true); };
  const openEdit = (e, project) => { e.stopPropagation(); setEditProject(project); setProjectDialog(true); };

  const pdf = async (key, path, params) => {
    setPdfBusy(key);
    try { await fetchPdf(path, params); } catch (error) { handleError(error, 'PDF konnte nicht erstellt werden'); } finally { setPdfBusy(''); }
  };

  const resetInvoice = async (inv) => {
    if (!window.confirm(`Rechnungsnummer ${inv.number} zurücksetzen? Beim nächsten PDF wird eine neue Nummer mit aktuellem Datum vergeben.`)) return;
    try {
      await api.delete(`/ts/invoices/${inv.id}`);
      toast.success('Rechnungsnummer zurückgesetzt');
      loadInvoices();
    } catch (error) { handleError(error, 'Fehler beim Zurücksetzen'); }
  };

  const totalGross = (invoices || []).reduce((s, i) => s + (i.gross || 0), 0);

  return (
    <div className="ts-app min-h-screen" data-testid="ts-company-home">
      <Toaster position="top-center" richColors />
      <AppHeader
        left={(
          <>
            <AppIcon logo={company?.logo} text={initials(company?.name)} size={40} className="rounded-xl" />
            <div className="min-w-0">
              <div className="font-semibold text-[16px] leading-tight truncate">{company?.name || '…'}</div>
              <div className="text-[12px] text-[#6E6E73] truncate">{company ? (companyAddress(company) || company.owner) : ''}</div>
            </div>
          </>
        )}
        right={(
          <>
            {companyCount > 1 && (
              <Btn variant="ghost" size="sm" onClick={() => navigate('/stundenzettel')} data-testid="ts-switch-company"><ArrowLeftRight size={16} /> <span className="hidden md:inline">Firma wechseln</span></Btn>
            )}
            <Btn variant="soft" size="sm" onClick={() => setCompanyDialog(true)} data-testid="ts-company-settings"><Settings size={16} /> <span className="hidden sm:inline">Firmeneinstellungen</span></Btn>
            <IconBtn onClick={logout} title="Abmelden"><LogOut size={18} /></IconBtn>
          </>
        )}
      />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex justify-center mb-8">
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: 'projekte', label: 'Meine Projekte', icon: FolderKanban, testId: 'ts-tab-projekte' },
              { value: 'rechnungen', label: 'Rechnungen', icon: Receipt, testId: 'ts-tab-rechnungen' },
            ]}
          />
        </div>

        {tab === 'projekte' && (
          <>
            <div className="flex items-end justify-between gap-4 mb-5">
              <div>
                <h1 className="text-[28px] sm:text-[34px] leading-none">Meine Projekte</h1>
                <p className="text-[14px] text-[#6E6E73] mt-1.5">Projekt antippen, Tag wählen, Zeit eintragen. Fertig.</p>
              </div>
              <Btn onClick={openNew} data-testid="ts-new-project"><Plus size={18} /> <span className="hidden sm:inline">Neues Projekt</span><span className="sm:hidden">Neu</span></Btn>
            </div>

            {loading && projects.length === 0 ? (
              <div className="py-24 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={28} /></div>
            ) : projects.length === 0 ? (
              <Card>
                <Empty icon={FolderKanban} title="Noch keine Projekte" text="Jedes Projekt bekommt seinen eigenen Kalender von 2025 bis 2030." action={<Btn onClick={openNew}><Plus size={18} /> Erstes Projekt anlegen</Btn>} />
              </Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="ts-project-grid">
                {projects.map((p) => (
                  <Card
                    key={p.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/stundenzettel/projekt/${p.id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/stundenzettel/projekt/${p.id}`); }}
                    className="group p-5 flex items-center gap-4 cursor-pointer transition-all hover:shadow-card-hover hover:-translate-y-0.5 active:scale-[0.99]"
                    data-testid={`ts-project-${p.id}`}
                  >
                    <AppIcon color={p.color} text={initials(p.name)} size={60} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[17px] font-semibold truncate">{p.name}</div>
                      <div className="text-[13px] text-[#6E6E73] truncate">{p.customer_name || 'Kein Auftraggeber'}</div>
                      <div className="text-[12px] text-[#86868B] mt-1">{fmtDecimalHours(p.total_minutes || 0)} Std. · {p.entry_count || 0} Einträge</div>
                    </div>
                    <IconBtn size={32} onClick={(e) => openEdit(e, p)} title="Projekt bearbeiten" className="text-[#86868B] sm:opacity-0 sm:group-hover:opacity-100 focus:opacity-100"><Pencil size={15} /></IconBtn>
                    <ChevronRight size={20} className="text-[#C7C7CC] -ml-1" />
                  </Card>
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'rechnungen' && (
          <>
            <div className="flex items-end justify-between gap-4 mb-5">
              <div>
                <h1 className="text-[28px] sm:text-[34px] leading-none">Rechnungen</h1>
                <p className="text-[14px] text-[#6E6E73] mt-1.5">Alle Monatsrechnungen dieser Firma. Neue Rechnungen entstehen im Kalender eines Projekts.</p>
              </div>
              {invoices && invoices.length > 0 && (
                <div className="text-right shrink-0">
                  <div className="text-[12px] text-[#6E6E73]">Summe brutto</div>
                  <div className="text-[24px] font-bold tracking-tight text-[#C41E3A] leading-none">{fmtEur(totalGross)}</div>
                </div>
              )}
            </div>

            {invoices === null ? (
              <div className="py-24 flex justify-center text-[#A1A1A6]"><Loader2 className="animate-spin" size={28} /></div>
            ) : invoices.length === 0 ? (
              <Card><Empty icon={Receipt} title="Noch keine Rechnungen" text="Öffne ein Projekt und erstelle über „Monats-PDF“ oder „Rechnung“ die erste Rechnung." /></Card>
            ) : (
              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-[14px] min-w-[760px]" data-testid="ts-invoice-table">
                    <thead>
                      <tr className="text-[12px] text-[#86868B] uppercase tracking-wider">
                        <th className="text-left font-medium px-5 py-3">Nr.</th>
                        <th className="text-left font-medium px-4 py-3">Datum</th>
                        <th className="text-left font-medium px-4 py-3">Projekt</th>
                        <th className="text-left font-medium px-4 py-3">Monat</th>
                        <th className="text-right font-medium px-4 py-3">Std.</th>
                        <th className="text-right font-medium px-4 py-3">Netto</th>
                        <th className="text-right font-medium px-4 py-3">Brutto</th>
                        <th className="px-3 py-3" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-black/[0.06]">
                      {invoices.map((inv) => (
                        <tr key={inv.id} className="hover:bg-black/[0.02]">
                          <td className="px-5 py-3.5 font-semibold whitespace-nowrap">{inv.number}</td>
                          <td className="px-4 py-3.5 whitespace-nowrap">{fmtDate(fromKey(inv.invoice_date))}</td>
                          <td className="px-4 py-3.5">
                            <div className="font-medium">{inv.project_name}</div>
                            <div className="text-[12px] text-[#86868B]">{inv.customer_name || '–'}</div>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">{MONTHS_DE[inv.month - 1]} {inv.year}</td>
                          <td className="px-4 py-3.5 text-right">{fmtDecimalHours(inv.total_minutes || 0)}</td>
                          <td className="px-4 py-3.5 text-right">{fmtEur(inv.net || 0)}</td>
                          <td className="px-4 py-3.5 text-right font-semibold">{fmtEur(inv.gross || 0)}</td>
                          <td className="px-3 py-3.5 whitespace-nowrap text-right">
                            <IconBtn size={32} variant="danger" onClick={() => pdf(`inv-${inv.id}`, `/ts/projects/${inv.project_id}/pdf/invoice`, { year: inv.year, month: inv.month })} disabled={pdfBusy === `inv-${inv.id}`} title="Rechnung öffnen">
                              {pdfBusy === `inv-${inv.id}` ? <Loader2 size={15} className="animate-spin" /> : <Receipt size={15} />}
                            </IconBtn>
                            <IconBtn size={32} onClick={() => pdf(`month-${inv.id}`, `/ts/projects/${inv.project_id}/pdf/month`, { year: inv.year, month: inv.month })} disabled={pdfBusy === `month-${inv.id}`} title="Monats-PDF (Stundenzettel + Rechnung)">
                              {pdfBusy === `month-${inv.id}` ? <Loader2 size={15} className="animate-spin" /> : <FileStack size={15} />}
                            </IconBtn>
                            <IconBtn size={32} onClick={() => resetInvoice(inv)} title="Rechnungsnummer zurücksetzen" className="text-[#A1A1A6]"><RotateCcw size={14} /></IconBtn>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </>
        )}
      </main>

      <ProjectDialog open={projectDialog} onOpenChange={setProjectDialog} project={editProject} companyId={companyId} defaultRate={company?.default_hourly_rate || 0} onSaved={loadProjects} onDeleted={loadProjects} />
      <CompanyDialog open={companyDialog} onOpenChange={setCompanyDialog} company={company} onSaved={(c) => setCompany(c)} onDeleted={() => navigate('/stundenzettel', { replace: true })} />
    </div>
  );
}
