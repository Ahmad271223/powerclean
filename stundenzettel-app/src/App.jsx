import React, { useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AlertTriangle, RefreshCw, DatabaseBackup } from 'lucide-react';
import { loadState, exportBackup } from './lib/store';
import { downloadBlob } from './lib/utils';
import { Btn, Card } from './components/ui';
import CompaniesPage from './pages/CompaniesPage';
import CompanyPage from './pages/CompanyPage';
import CalendarPage from './pages/CalendarPage';

/** Emergency screen: the UI crashed, but the data can still be exported. */
function CrashScreen({ error }) {
  const backup = async () => {
    try {
      downloadBlob(new Blob([await exportBackup()], { type: 'application/json' }), `Stundenzettel-Notfallsicherung_${new Date().toISOString().slice(0, 10)}.json`);
    } catch (err) {
      window.alert(`Sicherung fehlgeschlagen: ${err?.message || err}`);
    }
  };
  return (
    <div className="ts-app min-h-screen flex items-center justify-center p-6">
      <Card className="max-w-md w-full p-8 text-center">
        <span className="mx-auto w-14 h-14 rounded-2xl bg-[#C41E3A]/10 text-[#C41E3A] flex items-center justify-center"><AlertTriangle size={26} /></span>
        <h1 className="text-[24px] mt-5">Da ist etwas schiefgelaufen</h1>
        <p className="text-[14px] text-[#6E6E73] mt-2">Die Anzeige konnte nicht geladen werden. Deine Daten sind davon nicht betroffen. Lade die App neu oder sichere zuerst deine Daten.</p>
        <div className="flex flex-col gap-2 mt-6">
          <Btn onClick={() => window.location.reload()}><RefreshCw size={17} /> App neu laden</Btn>
          <Btn variant="soft" onClick={backup}><DatabaseBackup size={17} /> Daten sichern</Btn>
        </div>
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

export default function App() {
  useEffect(() => { loadState().catch((err) => console.error('Laden fehlgeschlagen', err)); }, []);
  return (
    <ErrorBoundary>
      <HashRouter>
        <Toaster position="top-center" richColors closeButton={false} />
        <Routes>
          <Route path="/" element={<CompaniesPage />} />
          <Route path="/firma/:companyId" element={<CompanyPage />} />
          <Route path="/projekt/:projectId" element={<CalendarPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  );
}
