import React from 'react';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { companyInfo } from '../data/services';

const DatenschutzPage = () => {
  return (
    <PageWrapper>
      <section className="bg-[#0A0A0A] text-white py-24" data-testid="datenschutz-hero">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <Breadcrumb items={[{ label: 'Datenschutz' }]} />
          <h1 className="text-5xl md:text-6xl">Datenschutzerklärung</h1>
        </div>
      </section>

      <section className="py-24 bg-white" data-testid="datenschutz-content">
        <div className="max-w-3xl mx-auto px-6 lg:px-12 prose prose-lg">
          <h2>1. Datenschutz auf einen Blick</h2>
          
          <h3>Allgemeine Hinweise</h3>
          <p>
            Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren 
            personenbezogenen Daten passiert, wenn Sie diese Website besuchen. Personenbezogene 
            Daten sind alle Daten, mit denen Sie persönlich identifiziert werden können.
          </p>

          <h3>Datenerfassung auf dieser Website</h3>
          <p>
            <strong>Wer ist verantwortlich für die Datenerfassung auf dieser Website?</strong><br />
            Die Datenverarbeitung auf dieser Website erfolgt durch den Websitebetreiber. 
            Dessen Kontaktdaten können Sie dem Impressum dieser Website entnehmen.
          </p>

          <h2>2. Hosting</h2>
          <p>
            Wir hosten die Inhalte unserer Website bei folgendem Anbieter:
          </p>
          <p>
            Die Inhalte unserer Website werden bei einem externen Hosting-Anbieter gehostet. 
            Die personenbezogenen Daten, die auf dieser Website erfasst werden, werden auf den 
            Servern des Hosters gespeichert.
          </p>

          <h2>3. Allgemeine Hinweise und Pflichtinformationen</h2>
          
          <h3>Datenschutz</h3>
          <p>
            Die Betreiber dieser Seiten nehmen den Schutz Ihrer persönlichen Daten sehr ernst. 
            Wir behandeln Ihre personenbezogenen Daten vertraulich und entsprechend der 
            gesetzlichen Datenschutzvorschriften sowie dieser Datenschutzerklärung.
          </p>

          <h3>Hinweis zur verantwortlichen Stelle</h3>
          <p>
            Die verantwortliche Stelle für die Datenverarbeitung auf dieser Website ist:
          </p>
          <p>
            PowerCleanService<br />
            {companyInfo.owner}<br />
            {companyInfo.street}<br />
            {companyInfo.city}<br /><br />
            Telefon: {companyInfo.phone}<br />
            E-Mail: {companyInfo.email}
          </p>

          <h2>4. Datenerfassung auf dieser Website</h2>
          
          <h3>Kontaktformular</h3>
          <p>
            Wenn Sie uns per Kontaktformular Anfragen zukommen lassen, werden Ihre Angaben 
            aus dem Anfrageformular inklusive der von Ihnen dort angegebenen Kontaktdaten 
            zwecks Bearbeitung der Anfrage und für den Fall von Anschlussfragen bei uns 
            gespeichert. Diese Daten geben wir nicht ohne Ihre Einwilligung weiter.
          </p>

          <h3>Anfrage per E-Mail oder Telefon</h3>
          <p>
            Wenn Sie uns per E-Mail oder Telefon kontaktieren, wird Ihre Anfrage inklusive 
            aller daraus hervorgehenden personenbezogenen Daten (Name, Anfrage) zum Zwecke 
            der Bearbeitung Ihres Anliegens bei uns gespeichert und verarbeitet.
          </p>

          <h2>5. Ihre Rechte</h2>
          <p>
            Sie haben jederzeit das Recht, unentgeltlich Auskunft über Herkunft, Empfänger 
            und Zweck Ihrer gespeicherten personenbezogenen Daten zu erhalten. Sie haben 
            außerdem ein Recht, die Berichtigung oder Löschung dieser Daten zu verlangen.
          </p>

          <h2>6. Analyse-Tools und Werbung</h2>
          <p>
            Diese Website verwendet keine Analyse-Tools oder Tracking-Technologien.
          </p>

          <h2>7. SSL- bzw. TLS-Verschlüsselung</h2>
          <p>
            Diese Seite nutzt aus Sicherheitsgründen und zum Schutz der Übertragung 
            vertraulicher Inhalte, wie zum Beispiel Anfragen, die Sie an uns als 
            Seitenbetreiber senden, eine SSL- bzw. TLS-Verschlüsselung.
          </p>
        </div>
      </section>
    </PageWrapper>
  );
};

export default DatenschutzPage;
