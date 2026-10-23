/** Rahmen der App: Kopfzeile, Navigation (Seitenleiste am Rechner, Tab-Leiste am Handy), Lizenz- und Offline-Hinweis. */
import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Timer, FolderKanban, Users, Contact, Receipt, CalendarOff, FileDown, Building2, ShieldCheck, LogOut, MoreHorizontal, Clock, X, AlertTriangle, BarChart3, WifiOff, Handshake, ClipboardList, Gavel } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { AppIcon, Sheet } from './ui';
import { initials } from '../lib/utils';
import { cn } from '../lib/utils';

const NAV_BUERO = [
  { to: '/', label: 'Übersicht', icon: LayoutDashboard, end: true },
  { to: '/projekte', label: 'Projekte', icon: FolderKanban },
  { to: '/zusammenarbeit', label: 'Zusammenarbeit', icon: Handshake },
  { to: '/ausschreibungen', label: 'Ausschreibungen', icon: Gavel },
  { to: '/aufgaben', label: 'Aufgaben', icon: ClipboardList },
  { to: '/einsatzplan', label: 'Einsatzplanung', icon: CalendarOff },
  { to: '/mitarbeiter', label: 'Mitarbeiter', icon: Users },
  { to: '/rechnungen', label: 'Rechnungen', icon: Receipt },
  { to: '/stempeluhr', label: 'Stempeluhr', icon: Timer },
  { to: '/auswertung', label: 'Auswertung', icon: BarChart3 },
  { to: '/kunden', label: 'Kunden', icon: Contact },
  { to: '/abwesenheiten', label: 'Abwesenheiten', icon: CalendarOff },
  { to: '/exporte', label: 'Exporte & Abschluss', icon: FileDown },
  { to: '/firma', label: 'Firma', icon: Building2 },
  { to: '/protokoll', label: 'Protokoll', icon: ShieldCheck },
];
/** Auftraggeber (GU, Bauherr): keine Rechnungen/Kunden im Menü, Projekte heißen Bauprojekte; „beides“ bekommt das volle Menü. */
const NAV_AUFTRAGGEBER = [
  { to: '/', label: 'Übersicht', icon: LayoutDashboard, end: true },
  { to: '/projekte', label: 'Bauprojekte', icon: FolderKanban },
  { to: '/ausschreibungen', label: 'Ausschreibungen', icon: Gavel },
  { to: '/zusammenarbeit', label: 'Zusammenarbeit', icon: Handshake },
  { to: '/aufgaben', label: 'Aufgaben', icon: ClipboardList },
  { to: '/einsatzplan', label: 'Einsatzplanung', icon: CalendarOff },
  { to: '/mitarbeiter', label: 'Mitarbeiter', icon: Users },
  { to: '/stempeluhr', label: 'Stempeluhr', icon: Timer },
  { to: '/auswertung', label: 'Auswertung', icon: BarChart3 },
  { to: '/abwesenheiten', label: 'Abwesenheiten', icon: CalendarOff },
  { to: '/exporte', label: 'Exporte & Abschluss', icon: FileDown },
  { to: '/firma', label: 'Firma', icon: Building2 },
  { to: '/protokoll', label: 'Protokoll', icon: ShieldCheck },
];
const NAV_MITARBEITER = [
  { to: '/', label: 'Stempeluhr', icon: Timer, end: true },
  { to: '/meine-zeiten', label: 'Meine Zeiten', icon: Clock },
  { to: '/einsatzplan', label: 'Meine Einsätze', icon: CalendarOff },
  { to: '/projekte', label: 'Projekte', icon: FolderKanban },
  { to: '/aufgaben', label: 'Aufgaben', icon: ClipboardList },
  { to: '/abwesenheiten', label: 'Abwesenheit', icon: CalendarOff },
  { to: '/profil', label: 'Profil', icon: Contact },
];

function PlanHinweis() {
  const { plan, isBuero, offline } = useAuth();
  if (offline) {
    return (
      <div className="mb-5 rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[14px] text-[#7A4100] flex items-start gap-3" role="status">
        <WifiOff size={18} className="shrink-0 mt-0.5" /><span>Kein Netz. Die Stempeluhr läuft offline weiter, alles andere zeigt den letzten bekannten Stand.</span>
      </div>
    );
  }
  if (!plan) return null;
  if (plan.status === 'test' && plan.tage_rest > 3 && !isBuero) return null;
  const rot = plan.status === 'abgelaufen' || plan.status === 'gesperrt';
  if (plan.status === 'aktiv' && plan.stufe !== 'teilnahme') return null;
  if ((plan.status === 'teilnahme' || plan.stufe === 'teilnahme') && !isBuero) return null;
  return (
    <div className={cn('mb-5 rounded-2xl px-4 py-3 text-[14px] flex items-start gap-3', rot ? 'bg-[#C41E3A]/10 border border-[#C41E3A]/30 text-[#8a1528]' : 'bg-white shadow-card text-[#1D1D1F]')} role="status">
      <AlertTriangle size={18} className="shrink-0 mt-0.5" />
      <span>{plan.hinweis}{isBuero && !rot ? ' Freischalten unter „Firma → Lizenz“.' : ''}</span>
    </div>
  );
}

export default function Layout({ children, title, subtitle, action, wide = false }) {
  const { user, firma, logout, isBuero } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mehr, setMehr] = useState(false);
  const nav = isBuero ? (firma?.art === 'auftraggeber' ? NAV_AUFTRAGGEBER : NAV_BUERO) : NAV_MITARBEITER;
  const tabs = nav.slice(0, 4);
  const rest = nav.slice(4);
  const restAktiv = rest.some((n) => location.pathname.startsWith(n.to) && n.to !== '/');

  const abmelden = () => { logout(); navigate('/login', { replace: true }); };

  const Eintrag = ({ n, onClick, klein }) => (
    <NavLink to={n.to} end={n.end} onClick={onClick} className={({ isActive }) => cn(
      klein ? 'flex flex-col items-center justify-center gap-0.5 flex-1 min-w-0 py-1.5 text-[11px] font-medium' : 'flex items-center gap-3 px-3.5 h-11 rounded-2xl text-[15px] font-medium transition-colors',
      isActive ? (klein ? 'text-[#C41E3A]' : 'bg-white shadow-card text-[#1D1D1F]') : (klein ? 'text-[#6E6E73]' : 'text-[#6E6E73] hover:bg-black/[0.04] hover:text-[#1D1D1F]'),
    )}>
      <n.icon size={klein ? 22 : 18} /> <span className="truncate">{n.label}</span>
    </NavLink>
  );

  return (
    <div className="ts-app lg:grid lg:grid-cols-[248px_1fr] lg:min-h-screen">
      <aside className="hidden lg:flex flex-col gap-1 p-4 safe-top border-r border-black/[0.06] sticky top-0 h-screen overflow-y-auto">
        <div className="flex items-center gap-3 px-2 py-3 mb-3">
          <AppIcon logo={firma?.logo} text={initials(firma?.name)} size={40} className="rounded-xl" />
          <div className="min-w-0">
            <div className="font-semibold text-[15px] leading-tight truncate">{firma?.name || 'Stundenzettel Pro'}</div>
            <div className="text-[12px] text-[#6E6E73] truncate">{user?.name} · {user?.rolle_name}</div>
          </div>
        </div>
        {nav.map((n) => <Eintrag key={n.to} n={n} />)}
        <div className="mt-auto pt-3">
          <button type="button" onClick={abmelden} className="flex items-center gap-3 px-3.5 h-11 rounded-2xl text-[15px] font-medium text-[#6E6E73] hover:bg-black/[0.04] w-full"><LogOut size={18} /> Abmelden</button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="lg:hidden sticky top-0 z-40 safe-top backdrop-blur-xl bg-[#F5F5F7]/80 border-b border-black/[0.06]">
          <div className="px-4 h-14 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <AppIcon logo={firma?.logo} text={initials(firma?.name)} size={32} className="rounded-lg" />
              <div className="min-w-0">
                <div className="font-semibold text-[14px] leading-tight truncate">{firma?.name}</div>
                <div className="text-[11px] text-[#6E6E73] truncate">{user?.name}</div>
              </div>
            </div>
            <button type="button" onClick={abmelden} className="w-9 h-9 rounded-full hover:bg-black/[0.05] flex items-center justify-center text-[#6E6E73]" aria-label="Abmelden"><LogOut size={18} /></button>
          </div>
        </header>

        <main className={cn('mit-tabbar mx-auto px-4 sm:px-6 py-5 sm:py-8', wide ? 'max-w-[1400px]' : 'max-w-6xl')}>
          <PlanHinweis />
          {(title || action) && (
            <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
              <div>
                {title && <h1 className="text-[26px] sm:text-[32px] leading-none">{title}</h1>}
                {subtitle && <p className="text-[14px] text-[#6E6E73] mt-1.5">{subtitle}</p>}
              </div>
              {action}
            </div>
          )}
          {children}
        </main>

        <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-xl border-t border-black/[0.06] safe-bottom">
          <div className="flex items-stretch px-1 h-[60px]">
            {tabs.map((n) => <Eintrag key={n.to} n={n} klein />)}
            {rest.length > 0 && (
              <button type="button" onClick={() => setMehr(true)} className={cn('flex flex-col items-center justify-center gap-0.5 flex-1 py-1.5 text-[11px] font-medium', restAktiv ? 'text-[#C41E3A]' : 'text-[#6E6E73]')}>
                <MoreHorizontal size={22} /> Mehr
              </button>
            )}
          </div>
        </nav>
        <Sheet open={mehr} onOpenChange={setMehr} title="Mehr">
          <div className="grid grid-cols-2 gap-2">
            {rest.map((n) => <Eintrag key={n.to} n={n} onClick={() => setMehr(false)} />)}
          </div>
        </Sheet>
      </div>
    </div>
  );
}

export function Ladeanzeige() {
  return <div className="py-24 flex justify-center text-[#A1A1A6]"><span className="w-7 h-7 rounded-full border-2 border-current border-t-transparent animate-spin" /></div>;
}

export function Hinweis({ children, icon: Icon = AlertTriangle, onClose }) {
  return (
    <div className="rounded-2xl bg-white shadow-card px-4 py-3 text-[14px] flex items-start gap-3">
      <Icon size={18} className="shrink-0 mt-0.5 text-[#B25E00]" />
      <span className="flex-1 min-w-0">{children}</span>
      {onClose && <button type="button" onClick={onClose} className="w-7 h-7 rounded-full hover:bg-black/[0.05] flex items-center justify-center text-[#86868B]" aria-label="Schließen"><X size={14} /></button>}
    </div>
  );
}

/** Hinweisliste zu einem Eintrag (ArbZG). */
export function Warnungen({ liste, klein = false }) {
  if (!liste?.length) return null;
  return (
    <span className={cn('inline-flex flex-wrap gap-1', klein ? 'mt-0.5' : 'mt-1')}>
      {liste.map((w) => <span key={w.code} title={w.text} className="inline-flex items-center gap-1 rounded-full bg-[#FFF4E5] text-[#B25E00] px-2 py-0.5 text-[11px] font-medium"><AlertTriangle size={11} /> {klein ? w.code.replace('_', ' ') : w.text}</span>)}
    </span>
  );
}
