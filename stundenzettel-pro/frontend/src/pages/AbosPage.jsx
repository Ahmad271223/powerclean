import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { BadgeEuro } from 'lucide-react';
import Layout from '../components/Layout';
import AbosKarte, { PreisListe } from '../components/AbosKarte';
import { Card } from '../components/ui';

/** Projektabos (Auftraggeber): aktive GU-Projekte, Kündigung zum Monatsende, Preise, Abrechnungsgrundlage. */
export default function AbosPage() {
  const [abos, setAbos] = useState(null);
  return (
    <Layout title="Projektabos" subtitle="Je aktivem Bauprojekt 50,99 € netto im Monat – egal wie viele Gewerke, Ausschreibungen, Projektleiter und Firmen. Entwürfe kosten nichts.">
      <div className="max-w-3xl mx-auto space-y-5">
        <Card className="p-5 sm:p-8 space-y-5">
          <div className="flex items-center gap-2"><BadgeEuro size={18} /><h2 className="text-[17px]">Eure GU-Projekte</h2></div>
          <AbosKarte onLoaded={setAbos} />
          <p className="text-[13px] text-[#6E6E73]">Ein Projekt wird mit der ersten Veröffentlichung einer Ausschreibung, der Einladung von Bietern oder einer Firma kostenpflichtig – ab dann für diesen Kalendermonat. Nach einer Kündigung bleibt es bis zum Monatsende voll nutzbar; danach sind Lesen, Export und die vollständige Projektakte weiterhin möglich. Lizenz und Firmendaten findet ihr unter <Link to="/firma" className="text-[#C41E3A] font-medium">Firma</Link>.</p>
        </Card>
        <PreisListe preise={abos?.preise} />
      </div>
    </Layout>
  );
}
