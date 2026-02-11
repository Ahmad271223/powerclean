import React from 'react';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { companyInfo } from '../data/services';

const AGBPage = () => {
  return (
    <PageWrapper>
      <section className="bg-[#0A0A0A] text-white py-24" data-testid="agb-hero">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <Breadcrumb items={[{ label: 'AGB' }]} />
          <h1 className="text-5xl md:text-6xl">Allgemeine Geschäftsbedingungen</h1>
        </div>
      </section>

      <section className="py-24 bg-white" data-testid="agb-content">
        <div className="max-w-3xl mx-auto px-6 lg:px-12 prose prose-lg">
          <h2>§ 1 Geltungsbereich</h2>
          <p>
            Diese Allgemeinen Geschäftsbedingungen (AGB) gelten für alle Verträge, die zwischen 
            PowerCleanService, {companyInfo.owner}, {companyInfo.street}, {companyInfo.city} 
            (nachfolgend "Auftragnehmer") und dem Auftraggeber (nachfolgend "Kunde") 
            geschlossen werden.
          </p>

          <h2>§ 2 Vertragsgegenstand</h2>
          <p>
            Der Auftragnehmer erbringt Reinigungsdienstleistungen und verwandte 
            Gebäudedienstleistungen. Art und Umfang der Leistungen ergeben sich aus dem 
            jeweiligen Einzelvertrag bzw. Angebot.
          </p>

          <h2>§ 3 Angebote und Vertragsschluss</h2>
          <p>
            Angebote des Auftragnehmers sind freibleibend und unverbindlich. Ein Vertrag 
            kommt erst durch die schriftliche Auftragsbestätigung des Auftragnehmers oder 
            durch Beginn der Leistungserbringung zustande.
          </p>

          <h2>§ 4 Preise und Zahlungsbedingungen</h2>
          <p>
            (1) Die vereinbarten Preise verstehen sich netto zuzüglich der gesetzlichen 
            Mehrwertsteuer.<br />
            (2) Rechnungen sind innerhalb von 14 Tagen nach Rechnungsdatum ohne Abzug 
            zahlbar.<br />
            (3) Bei Zahlungsverzug werden Verzugszinsen in Höhe von 5 Prozentpunkten über 
            dem Basiszinssatz berechnet.
          </p>

          <h2>§ 5 Leistungserbringung</h2>
          <p>
            (1) Der Auftragnehmer führt die Arbeiten nach den anerkannten Regeln des 
            Gebäudereiniger-Handwerks aus.<br />
            (2) Der Kunde stellt dem Auftragnehmer kostenfrei Wasser, Strom und 
            Abstellmöglichkeiten zur Verfügung.<br />
            (3) Der Zugang zu den zu reinigenden Räumlichkeiten ist durch den Kunden 
            sicherzustellen.
          </p>

          <h2>§ 6 Pflichten des Kunden</h2>
          <p>
            (1) Der Kunde ist verpflichtet, den Auftragnehmer über besondere Gefahrenquellen 
            und Risiken zu informieren.<br />
            (2) Wertgegenstände sind vom Kunden vor Beginn der Reinigungsarbeiten in 
            Sicherheit zu bringen.
          </p>

          <h2>§ 7 Haftung</h2>
          <p>
            (1) Der Auftragnehmer haftet für Schäden, die durch sein Verschulden oder das 
            seiner Erfüllungsgehilfen verursacht werden.<br />
            (2) Bei leichter Fahrlässigkeit ist die Haftung auf den vertragstypischen, 
            vorhersehbaren Schaden begrenzt.<br />
            (3) Die Haftung für Schäden an nicht gesicherten Wertgegenständen ist 
            ausgeschlossen.
          </p>

          <h2>§ 8 Versicherung</h2>
          <p>
            Der Auftragnehmer verfügt über eine Betriebshaftpflichtversicherung, die 
            Personen-, Sach- und Vermögensschäden abdeckt.
          </p>

          <h2>§ 9 Kündigung</h2>
          <p>
            (1) Bei Verträgen mit unbestimmter Laufzeit kann von beiden Seiten mit einer 
            Frist von 4 Wochen zum Monatsende gekündigt werden.<br />
            (2) Das Recht zur außerordentlichen Kündigung aus wichtigem Grund bleibt 
            unberührt.
          </p>

          <h2>§ 10 Schlussbestimmungen</h2>
          <p>
            (1) Es gilt deutsches Recht.<br />
            (2) Gerichtsstand ist Hannover, soweit gesetzlich zulässig.<br />
            (3) Sollten einzelne Bestimmungen unwirksam sein, bleibt die Wirksamkeit der 
            übrigen Bestimmungen unberührt.
          </p>

          <p className="text-sm text-gray-500 mt-12">
            Stand: Januar {new Date().getFullYear()}
          </p>
        </div>
      </section>
    </PageWrapper>
  );
};

export default AGBPage;
