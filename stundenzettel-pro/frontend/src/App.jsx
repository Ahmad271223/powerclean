import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { AuthProvider, useAuth } from './lib/auth';
import { Btn, Card } from './components/ui';
import { LoginPage, RegisterPage, EinladungPage } from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import StempeluhrPage from './pages/StempeluhrPage';
import ProjektePage from './pages/ProjektePage';
import ProjektPage from './pages/ProjektPage';
import KundenPage from './pages/KundenPage';
import MitarbeiterPage from './pages/MitarbeiterPage';
import MitarbeiterDetailPage from './pages/MitarbeiterDetailPage';
import AbwesenheitenPage from './pages/AbwesenheitenPage';
import RechnungenPage from './pages/RechnungenPage';
import ExportePage from './pages/ExportePage';
import FirmaPage from './pages/FirmaPage';
import ProtokollPage from './pages/ProtokollPage';
import MeineZeitenPage from './pages/MeineZeitenPage';
import ProfilPage from './pages/ProfilPage';
import AuswertungPage from './pages/AuswertungPage';

function CrashScreen({ error }) {
  return (
    <div className="ts-app min-h-screen flex items-center justify-center p-6">
      <Card className="max-w-md w-full p-8 text-center">
        <span className="mx-auto w-14 h-14 rounded-2xl bg-[#C41E3A]/10 text-[#C41E3A] flex items-center justify-center"><AlertTriangle size={26} /></span>
        <h1 className="text-[24px] mt-5">Da ist etwas schiefgelaufen</h1>
        <p className="text-[14px] text-[#6E6E73] mt-2">Die Anzeige konnte nicht geladen werden. Deine Daten liegen sicher auf dem Server.</p>
        <Btn className="mt-6" onClick={() => window.location.reload()}><RefreshCw size={17} /> Neu laden</Btn>
        <pre className="mt-5 text-left text-[11px] text-[#86868B] whitespace-pre-wrap break-words max-h-32 overflow-auto">{String(error?.message || error)}</pre>
      </Card>
    </div>
  );
}

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('UI-Fehler', error, info); }
  render() { return this.state.error ? <CrashScreen error={this.state.error} /> : this.props.children; }
}

const Spinner = () => <div className="ts-app min-h-screen flex items-center justify-center text-[#A1A1A6]"><span className="w-7 h-7 rounded-full border-2 border-current border-t-transparent animate-spin" /></div>;

function Geschuetzt({ buero = false, children }) {
  const { ready, user, isBuero } = useAuth();
  if (!ready) return <Spinner />;
  if (!user) {
    try { sessionStorage.setItem('szpro-ziel', window.location.hash.replace(/^#/, '') || '/'); } catch { /* ignore */ }
    return <Navigate to="/login" replace />;
  }
  if (buero && !isBuero) return <Navigate to="/" replace />;
  return children;
}

function Oeffentlich({ children }) {
  const { ready, user } = useAuth();
  if (!ready) return <Spinner />;
  if (user) {
    let ziel = '/';
    try { ziel = sessionStorage.getItem('szpro-ziel') || '/'; sessionStorage.removeItem('szpro-ziel'); } catch { /* ignore */ }
    return <Navigate to={ziel.startsWith('/login') || ziel.startsWith('/registrieren') ? '/' : ziel} replace />;
  }
  return children;
}

function Start() {
  const { isBuero } = useAuth();
  return isBuero ? <DashboardPage /> : <StempeluhrPage />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <HashRouter>
          <Toaster position="top-center" richColors closeButton={false} />
          <Routes>
            <Route path="/login" element={<Oeffentlich><LoginPage /></Oeffentlich>} />
            <Route path="/registrieren" element={<Oeffentlich><RegisterPage /></Oeffentlich>} />
            <Route path="/einladung/:token" element={<EinladungPage />} />
            <Route path="/" element={<Geschuetzt><Start /></Geschuetzt>} />
            <Route path="/stempeluhr" element={<Geschuetzt><StempeluhrPage /></Geschuetzt>} />
            <Route path="/stempeln/:projectId" element={<Geschuetzt><StempeluhrPage /></Geschuetzt>} />
            <Route path="/meine-zeiten" element={<Geschuetzt><MeineZeitenPage /></Geschuetzt>} />
            <Route path="/profil" element={<Geschuetzt><ProfilPage /></Geschuetzt>} />
            <Route path="/projekte" element={<Geschuetzt><ProjektePage /></Geschuetzt>} />
            <Route path="/projekte/:projectId" element={<Geschuetzt><ProjektPage /></Geschuetzt>} />
            <Route path="/abwesenheiten" element={<Geschuetzt><AbwesenheitenPage /></Geschuetzt>} />
            <Route path="/kunden" element={<Geschuetzt buero><KundenPage /></Geschuetzt>} />
            <Route path="/mitarbeiter" element={<Geschuetzt buero><MitarbeiterPage /></Geschuetzt>} />
            <Route path="/mitarbeiter/:userId" element={<Geschuetzt buero><MitarbeiterDetailPage /></Geschuetzt>} />
            <Route path="/rechnungen" element={<Geschuetzt buero><RechnungenPage /></Geschuetzt>} />
            <Route path="/auswertung" element={<Geschuetzt buero><AuswertungPage /></Geschuetzt>} />
            <Route path="/exporte" element={<Geschuetzt buero><ExportePage /></Geschuetzt>} />
            <Route path="/firma" element={<Geschuetzt buero><FirmaPage /></Geschuetzt>} />
            <Route path="/protokoll" element={<Geschuetzt buero><ProtokollPage /></Geschuetzt>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </HashRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
