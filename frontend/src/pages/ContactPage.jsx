import React from 'react';
import { Link } from 'react-router-dom';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { companyInfo } from '../data/services';
import { Phone, Mail, MapPin, Clock, MessageCircle, ArrowRight } from 'lucide-react';

const ContactPage = () => {
  return (
    <PageWrapper>
      {/* Hero */}
      <section className="bg-[#0A0A0A] text-white py-24" data-testid="contact-hero">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <Breadcrumb items={[{ label: 'Kontakt' }]} />
          <h1 className="text-5xl md:text-6xl mb-6">Kontakt</h1>
          <p className="text-xl text-gray-400 max-w-2xl">
            Wir sind für Sie da. Kontaktieren Sie uns für Fragen, Angebote oder eine unverbindliche Beratung.
          </p>
        </div>
      </section>

      {/* Contact Info */}
      <section className="py-24 bg-white" data-testid="contact-info">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
            {/* Contact Details */}
            <div>
              <h2 className="text-3xl md:text-4xl mb-8">So erreichen Sie uns</h2>
              
              <div className="space-y-8">
                {/* Phone */}
                <div className="flex items-start gap-6">
                  <div className="w-14 h-14 bg-[#C41E3A] flex items-center justify-center flex-shrink-0">
                    <Phone className="text-white" size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                      Telefon
                    </h3>
                    <a 
                      href={`tel:${companyInfo.phone}`}
                      className="text-2xl text-gray-700 hover:text-[#C41E3A] transition-colors"
                      data-testid="contact-phone"
                    >
                      {companyInfo.phone}
                    </a>
                    <p className="text-gray-500 mt-1">Rufen Sie uns direkt an</p>
                  </div>
                </div>

                {/* Email */}
                <div className="flex items-start gap-6">
                  <div className="w-14 h-14 bg-[#C41E3A] flex items-center justify-center flex-shrink-0">
                    <Mail className="text-white" size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                      E-Mail
                    </h3>
                    <a 
                      href={`mailto:${companyInfo.email}`}
                      className="text-2xl text-gray-700 hover:text-[#C41E3A] transition-colors"
                      data-testid="contact-email"
                    >
                      {companyInfo.email}
                    </a>
                    <p className="text-gray-500 mt-1">Schreiben Sie uns jederzeit</p>
                  </div>
                </div>

                {/* WhatsApp */}
                <div className="flex items-start gap-6">
                  <div className="w-14 h-14 bg-[#25D366] flex items-center justify-center flex-shrink-0">
                    <MessageCircle className="text-white" size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                      WhatsApp
                    </h3>
                    <a 
                      href={`https://wa.me/49${companyInfo.phone.replace(/\s/g, '').replace(/^0/, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-2xl text-gray-700 hover:text-[#25D366] transition-colors"
                      data-testid="contact-whatsapp"
                    >
                      Jetzt chatten
                    </a>
                    <p className="text-gray-500 mt-1">Schnelle Antworten per WhatsApp</p>
                  </div>
                </div>

                {/* Address */}
                <div className="flex items-start gap-6">
                  <div className="w-14 h-14 bg-[#C41E3A] flex items-center justify-center flex-shrink-0">
                    <MapPin className="text-white" size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                      Adresse
                    </h3>
                    <address className="not-italic text-gray-700 text-lg">
                      <p>{companyInfo.owner}</p>
                      <p>{companyInfo.street}</p>
                      <p>{companyInfo.city}</p>
                    </address>
                  </div>
                </div>

                {/* Opening Hours */}
                <div className="flex items-start gap-6">
                  <div className="w-14 h-14 bg-[#C41E3A] flex items-center justify-center flex-shrink-0">
                    <Clock className="text-white" size={24} />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                      Erreichbarkeit
                    </h3>
                    <div className="text-gray-700">
                      <p className="text-lg">Montag - Freitag: 7:00 - 18:00</p>
                      <p className="text-lg">Samstag: Nach Vereinbarung</p>
                      <p className="text-lg">Sonntag: Geschlossen</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Map & Quick Request */}
            <div className="space-y-8">
              {/* Map */}
              <div className="bg-gray-100 aspect-[4/3] relative overflow-hidden" data-testid="contact-map">
                <iframe
                  src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2434.5073474684144!2d9.738!3d52.424!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zNTLCsDI1JzI2LjQiTiA5wrA0NCcxNi44IkU!5e0!3m2!1sde!2sde!4v1234567890"
                  width="100%"
                  height="100%"
                  style={{ border: 0 }}
                  allowFullScreen=""
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                  title="Standort PowerCleanService"
                  className="absolute inset-0"
                ></iframe>
              </div>

              {/* Quick Request CTA */}
              <div className="bg-[#0A0A0A] text-white p-8" data-testid="contact-cta">
                <h3 className="text-2xl mb-4">Direkt anfragen?</h3>
                <p className="text-gray-400 mb-6">
                  Nutzen Sie unser Anfrageformular für ein schnelles und unverbindliches Angebot.
                </p>
                <Link
                  to="/anfrage"
                  className="btn-primary inline-flex items-center gap-2 px-8 py-4"
                  data-testid="contact-cta-button"
                >
                  Zum Anfrageformular
                  <ArrowRight size={18} />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-24 bg-gray-50" data-testid="contact-faq">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <h2 className="text-3xl md:text-4xl mb-12 text-center">Häufige Fragen</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div className="bg-white p-6 border border-gray-200">
              <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                Wie schnell erhalte ich ein Angebot?
              </h3>
              <p className="text-gray-600">
                In der Regel melden wir uns innerhalb von 24 Stunden mit einem individuellen Angebot bei Ihnen.
              </p>
            </div>
            <div className="bg-white p-6 border border-gray-200">
              <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                Sind Sie versichert?
              </h3>
              <p className="text-gray-600">
                Ja, wir sind vollständig betriebs- und haftpflichtversichert. Ihre Sicherheit hat bei uns höchste Priorität.
              </p>
            </div>
            <div className="bg-white p-6 border border-gray-200">
              <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                Arbeiten Sie auch am Wochenende?
              </h3>
              <p className="text-gray-600">
                Samstags sind wir nach Vereinbarung im Einsatz. Für Notfälle sind wir auch außerhalb der Geschäftszeiten erreichbar.
              </p>
            </div>
            <div className="bg-white p-6 border border-gray-200">
              <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                In welchem Gebiet sind Sie tätig?
              </h3>
              <p className="text-gray-600">
                Wir sind hauptsächlich in Hannover und Umgebung tätig. Bei größeren Projekten kommen wir auch gerne zu Ihnen.
              </p>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
};

export default ContactPage;
