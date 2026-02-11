import React from 'react';
import { Link } from 'react-router-dom';
import { PageWrapper } from '../components/Layout';
import { services, clientLogos, companyInfo } from '../data/services';
import { ArrowRight, CheckCircle, Award, Users, Calendar, Shield } from 'lucide-react';

const HomePage = () => {
  return (
    <PageWrapper>
      {/* Hero Section */}
      <section className="relative min-h-[90vh] flex items-center" data-testid="hero-section">
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: 'url(https://images.unsplash.com/photo-1555238920-7a6bea18473b?w=1600&q=80)'
          }}
        >
          <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/60 to-transparent"></div>
        </div>
        
        <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 py-24">
          <div className="max-w-3xl">
            <h1 className="text-5xl md:text-7xl lg:text-8xl text-white mb-6 animate-fade-in-up">
              <span className="block">Glanz.</span>
              <span className="block">Hygiene.</span>
              <span className="block text-[#C41E3A]">Power.</span>
            </h1>
            <p className="text-xl md:text-2xl text-gray-300 mb-8 max-w-xl animate-fade-in-up animation-delay-200">
              Professionelle Reinigung für Gewerbe & Industrie. Seit {companyInfo.since} Ihr zuverlässiger Partner in Hannover.
            </p>
            <div className="flex flex-wrap gap-4 animate-fade-in-up animation-delay-300">
              <Link
                to="/anfrage"
                className="btn-primary px-8 py-4 text-lg flex items-center gap-2"
                data-testid="hero-cta-primary"
              >
                Jetzt Angebot anfragen
                <ArrowRight size={20} />
              </Link>
              <Link
                to="/leistungen"
                className="btn-secondary bg-white/10 border-white text-white hover:bg-white hover:text-black px-8 py-4 text-lg"
                data-testid="hero-cta-secondary"
              >
                Leistungen ansehen
              </Link>
            </div>
          </div>

          {/* Service Tags */}
          <div className="mt-16 flex flex-wrap gap-3 animate-fade-in-up animation-delay-400">
            {services.map((service) => (
              <Link
                key={service.id}
                to={`/leistungen/${service.id}`}
                className="bg-white/10 backdrop-blur-sm text-white px-4 py-2 text-sm font-medium hover:bg-white hover:text-black transition-all"
                data-testid={`hero-service-tag-${service.id}`}
              >
                {service.name}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Trust Indicators */}
      <section className="bg-[#0A0A0A] text-white py-12" data-testid="trust-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <div className="text-4xl md:text-5xl font-bold text-[#C41E3A] mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                {new Date().getFullYear() - 2009}+
              </div>
              <div className="text-gray-400 text-sm uppercase tracking-wider">Jahre Erfahrung</div>
            </div>
            <div>
              <div className="text-4xl md:text-5xl font-bold text-[#C41E3A] mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                500+
              </div>
              <div className="text-gray-400 text-sm uppercase tracking-wider">Zufriedene Kunden</div>
            </div>
            <div>
              <div className="text-4xl md:text-5xl font-bold text-[#C41E3A] mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                14
              </div>
              <div className="text-gray-400 text-sm uppercase tracking-wider">Dienstleistungen</div>
            </div>
            <div>
              <div className="text-4xl md:text-5xl font-bold text-[#C41E3A] mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                24/7
              </div>
              <div className="text-gray-400 text-sm uppercase tracking-wider">Erreichbarkeit</div>
            </div>
          </div>
        </div>
      </section>

      {/* Client Logos */}
      <section className="py-16 bg-gray-50" data-testid="clients-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <h2 className="text-2xl md:text-3xl text-center mb-12 text-gray-900">
            Langjährige zufriedene Kunden
          </h2>
          <div className="flex flex-wrap justify-center items-center gap-12 md:gap-16">
            {clientLogos.map((logo) => (
              <div 
                key={logo.name} 
                className="transition-all hover:scale-105"
                data-testid={`client-logo-${logo.name.toLowerCase().replace(/\s/g, '-')}`}
              >
                <img 
                  src={logo.url} 
                  alt={logo.name} 
                  className="h-12 md:h-16 w-auto object-contain"
                  onError={(e) => {
                    e.target.style.display = 'none';
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Services Overview */}
      <section className="py-24 bg-white" data-testid="services-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl mb-4">Unsere Leistungen</h2>
            <p className="text-gray-600 text-lg max-w-2xl mx-auto">
              Professionelle Reinigung und Facility Services für jeden Bedarf
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {services.slice(0, 9).map((service, index) => (
              <Link
                key={service.id}
                to={`/leistungen/${service.id}`}
                className="service-card group relative bg-white border border-gray-200 overflow-hidden"
                style={{ animationDelay: `${index * 0.1}s` }}
                data-testid={`service-card-${service.id}`}
              >
                <div className="aspect-[4/3] overflow-hidden">
                  <img
                    src={service.image}
                    alt={service.name}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                  />
                </div>
                <div className="p-6">
                  <h3 className="text-xl font-bold mb-2 group-hover:text-[#C41E3A] transition-colors" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    {service.name}
                  </h3>
                  <p className="text-gray-600 text-sm line-clamp-2">
                    {service.shortDesc}
                  </p>
                  <div className="mt-4 flex items-center text-[#C41E3A] font-medium text-sm uppercase tracking-wider">
                    Mehr erfahren
                    <ArrowRight size={16} className="ml-2 group-hover:translate-x-2 transition-transform" />
                  </div>
                </div>
              </Link>
            ))}
          </div>

          <div className="text-center mt-12">
            <Link
              to="/leistungen"
              className="btn-secondary inline-flex items-center gap-2 px-8 py-4"
              data-testid="services-view-all"
            >
              Alle {services.length} Leistungen ansehen
              <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="py-24 bg-gray-50" data-testid="about-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-4xl md:text-5xl mb-6">Über uns</h2>
              <p className="text-gray-600 text-lg mb-6">
                PowerCleanService steht seit {companyInfo.since} für Qualität und Verlässlichkeit. 
                In einer Zeit, in der viele Unternehmen nach der Wirtschaftskrise um ihre Existenz 
                kämpfen mussten, haben wir uns erfolgreich am Markt behauptet – und sind seitdem 
                kontinuierlich gewachsen.
              </p>
              <p className="text-gray-600 text-lg mb-8">
                Auch die Herausforderung der Corona-Pandemie im Jahr 2020 konnte uns nicht bremsen. 
                Wir sind wirtschaftlich stabil geblieben und haben bewiesen, dass wir auch in 
                schwierigen Zeiten für unsere Kunden da sind.
              </p>
              
              <div className="grid grid-cols-2 gap-6">
                <div className="flex items-start gap-3">
                  <Award className="text-[#C41E3A] flex-shrink-0 mt-1" size={24} />
                  <div>
                    <h4 className="font-bold text-gray-900">Qualität</h4>
                    <p className="text-sm text-gray-600">Höchste Standards bei jedem Auftrag</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Users className="text-[#C41E3A] flex-shrink-0 mt-1" size={24} />
                  <div>
                    <h4 className="font-bold text-gray-900">Erfahrung</h4>
                    <p className="text-sm text-gray-600">Geschultes Fachpersonal</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Calendar className="text-[#C41E3A] flex-shrink-0 mt-1" size={24} />
                  <div>
                    <h4 className="font-bold text-gray-900">Flexibilität</h4>
                    <p className="text-sm text-gray-600">Termine nach Ihrem Bedarf</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Shield className="text-[#C41E3A] flex-shrink-0 mt-1" size={24} />
                  <div>
                    <h4 className="font-bold text-gray-900">Versichert</h4>
                    <p className="text-sm text-gray-600">Vollständig abgesichert</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="relative">
              <img
                src="https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800&q=80"
                alt="Professionelle Reinigung"
                className="w-full aspect-[4/3] object-cover"
              />
              <div className="absolute -bottom-8 -left-8 bg-[#C41E3A] text-white p-8">
                <div className="text-5xl font-bold mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                  Seit {companyInfo.since}
                </div>
                <div className="text-lg">Deutsches Handwerk</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Why Us Section */}
      <section className="py-24 bg-[#0A0A0A] text-white" data-testid="why-us-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl mb-4">Warum PowerCleanService?</h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              Was uns von anderen unterscheidet
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-white/5 p-8 border-l-4 border-[#C41E3A]">
              <h3 className="text-2xl mb-4">Transparente Prozesse</h3>
              <p className="text-gray-400">
                Klare Kommunikation, unverbindliche Angebote und schneller Rückruf. 
                Sie wissen immer, woran Sie sind.
              </p>
            </div>
            <div className="bg-white/5 p-8 border-l-4 border-[#C41E3A]">
              <h3 className="text-2xl mb-4">Deutsches Handwerk</h3>
              <p className="text-gray-400">
                Seit {companyInfo.since} stehen wir für Qualität "Made in Germany". 
                Zuverlässigkeit ist unser Markenzeichen.
              </p>
            </div>
            <div className="bg-white/5 p-8 border-l-4 border-[#C41E3A]">
              <h3 className="text-2xl mb-4">Versichert & Zertifiziert</h3>
              <p className="text-gray-400">
                Vollständig versichert und mit allen notwendigen Zertifizierungen. 
                Ihr Objekt ist bei uns in sicheren Händen.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 bg-[#C41E3A] text-white" data-testid="cta-section">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 text-center">
          <h2 className="text-4xl md:text-5xl mb-6">Bereit für strahlende Sauberkeit?</h2>
          <p className="text-xl text-white/80 mb-8 max-w-2xl mx-auto">
            Kontaktieren Sie uns jetzt für ein unverbindliches Angebot. Wir melden uns innerhalb von 24 Stunden bei Ihnen.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              to="/anfrage"
              className="bg-white text-[#C41E3A] px-8 py-4 text-lg font-bold uppercase tracking-wider hover:bg-gray-100 transition-colors"
              data-testid="cta-primary"
            >
              Jetzt Anfragen
            </Link>
            <a
              href={`tel:${companyInfo.phone}`}
              className="border-2 border-white text-white px-8 py-4 text-lg font-bold uppercase tracking-wider hover:bg-white hover:text-[#C41E3A] transition-colors"
              data-testid="cta-phone"
            >
              {companyInfo.phone}
            </a>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
};

export default HomePage;
