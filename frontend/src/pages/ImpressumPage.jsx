import React from 'react';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { companyInfo } from '../data/services';

const ImpressumPage = () => {
  return (
    <PageWrapper>
      <section className="bg-[#0A0A0A] text-white py-24" data-testid="impressum-hero">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <Breadcrumb items={[{ label: 'Impressum' }]} />
          <h1 className="text-5xl md:text-6xl">Impressum</h1>
        </div>
      </section>

      <section className="py-24 bg-white" data-testid="impressum-content">
        <div className="max-w-3xl mx-auto px-6 lg:px-12 prose prose-lg">
          <h2>Angaben gemäß § 5 TMG</h2>
          <p>
            <strong>PowerCleanService</strong><br />
            {companyInfo.owner}<br />
            {companyInfo.street}<br />
            {companyInfo.city}
          </p>

          <h2>Kontakt</h2>
          <p>
            Telefon: {companyInfo.phone}<br />
            E-Mail: {companyInfo.email}
          </p>

          <h2>Umsatzsteuer-ID</h2>
          <p>
            Umsatzsteuer-Identifikationsnummer gemäß §27 a Umsatzsteuergesetz:<br />
            DE XXXXXXXXX
          </p>

          <h2>Berufsbezeichnung und berufsrechtliche Regelungen</h2>
          <p>
            Berufsbezeichnung: Gebäudereiniger<br />
            Zuständige Kammer: Handwerkskammer Hannover<br />
            Verliehen in: Deutschland
          </p>

          <h2>Streitschlichtung</h2>
          <p>
            Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit: 
            <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener noreferrer">
              https://ec.europa.eu/consumers/odr
            </a>
          </p>
          <p>
            Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer 
            Verbraucherschlichtungsstelle teilzunehmen.
          </p>

          <h2>Haftung für Inhalte</h2>
          <p>
            Als Diensteanbieter sind wir gemäß § 7 Abs.1 TMG für eigene Inhalte auf diesen Seiten 
            nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als 
            Diensteanbieter jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde 
            Informationen zu überwachen oder nach Umständen zu forschen, die auf eine rechtswidrige 
            Tätigkeit hinweisen.
          </p>

          <h2>Haftung für Links</h2>
          <p>
            Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen 
            Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. 
            Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder Betreiber 
            der Seiten verantwortlich.
          </p>

          <h2>Urheberrecht</h2>
          <p>
            Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen 
            dem deutschen Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art 
            der Verwertung außerhalb der Grenzen des Urheberrechtes bedürfen der schriftlichen 
            Zustimmung des jeweiligen Autors bzw. Erstellers.
          </p>
        </div>
      </section>
    </PageWrapper>
  );
};

export default ImpressumPage;
