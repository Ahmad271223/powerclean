import React from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import Layout from '../components/Layout';
import { Card } from '../components/ui';
import { useAuth } from '../lib/auth';
import { BAUSTEINE } from '../lib/lizenzen';

const VERSION = import.meta.env.VITE_APP_VERSION || '1.0';

function Inhalt() {
  return (
    <div className="space-y-4">
      <Card className="p-4 text-[14px] space-y-1.5">
        <div className="font-semibold text-[16px]">Stundenzettel Pro</div>
        <div className="text-[#6E6E73]">Version {VERSION}</div>
        <p>Die Anmeldung liegt nur auf diesem Gerät. Die App enthält keine Zugangsschlüssel für Dienste Dritter – Schlüssel für Push-Nachrichten und KI liegen nur auf dem Server.</p>
        <p className="text-[#6E6E73]">Push-Nachrichten laufen auf dem iPhone über Apple, auf Android über Google (Firebase). Sie enthalten nur Projekt, Straße, Tage und Uhrzeit.</p>
        <p><a href="/datenschutz" className="text-[#C41E3A] font-medium">Datenschutz</a> · <a href="/impressum" className="text-[#C41E3A] font-medium">Impressum</a></p>
      </Card>
      <Card className="p-0 overflow-hidden">
        <div className="px-4 pt-4 pb-2 font-semibold text-[16px]">Fremde Bausteine</div>
        <p className="px-4 pb-3 text-[13px] text-[#6E6E73]">Alle unter freien Lizenzen ohne Copyleft (MIT, ISC, Apache 2.0, BSD). Den Lizenztext enthält jeweils das verlinkte Projekt.</p>
        <ul className="divide-y divide-black/[0.06]">
          {BAUSTEINE.map((b) => (
            <li key={b.name} className="px-4 py-2.5 text-[14px]">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{b.name}</span>
                <span className="text-[12px] font-semibold rounded-full px-2 py-0.5 bg-black/[0.06]">{b.lizenz}</span>
              </div>
              <div className="text-[12px] text-[#6E6E73]">{b.urheber}{b.hinweis ? ` · ${b.hinweis}` : ''}</div>
              <a href={b.adresse} target="_blank" rel="noreferrer" className="text-[12px] text-[#C41E3A] inline-flex items-center gap-1">{b.adresse.replace('https://', '')} <ExternalLink size={11} /></a>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

/** „Über / Lizenzen“ – angemeldet im normalen Rahmen, sonst als eigene Seite (z. B. aus der Anmeldung). */
export default function LizenzenPage() {
  const { user } = useAuth();
  if (user) return <Layout title="Über / Lizenzen"><Inhalt /></Layout>;
  return (
    <div className="min-h-screen bg-[#F5F5F7] p-4 max-w-2xl mx-auto">
      <Link to="/login" className="text-[14px] text-[#C41E3A] font-medium">← Zur Anmeldung</Link>
      <h1 className="text-[28px] font-bold my-3">Über / Lizenzen</h1>
      <Inhalt />
    </div>
  );
}
