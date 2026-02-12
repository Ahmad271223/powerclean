import React from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { services, companyInfo } from '../data/services';
import { ArrowRight, CheckCircle, Phone, Mail, Clock, ArrowLeft } from 'lucide-react';
import * as Icons from 'lucide-react';

const ServiceDetailPage = () => {
  const { serviceId } = useParams();
  const service = services.find(s => s.id === serviceId);
  
  if (!service) {
    return <Navigate to="/leistungen" replace />;
  }

  const currentIndex = services.findIndex(s => s.id === serviceId);
  const prevService = currentIndex > 0 ? services[currentIndex - 1] : null;
  const nextService = currentIndex < services.length - 1 ? services[currentIndex + 1] : null;

  // Get icon component
  const IconComponent = Icons[service.icon] || Icons.Sparkles;

  return (
    <PageWrapper>
      {/* Hero */}
      <section className="relative min-h-[60vh] md:min-h-[50vh]" data-testid="service-detail-hero">
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${service.image})` }}
        >
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/50 to-black"></div>
        </div>
        
        <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 pt-28 md:pt-32 pb-32 md:pb-48">
          <Breadcrumb items={[
            { label: 'Leistungen', path: '/leistungen' },
            { label: service.name }
          ]} />
          
          <div className="flex items-center gap-4 mb-4 md:mb-6">
            <div className="w-12 h-12 md:w-16 md:h-16 bg-[#C41E3A] flex items-center justify-center">
              <IconComponent className="text-white" size={24} />
            </div>
          </div>
          
          <h1 className="text-3xl sm:text-4xl md:text-6xl lg:text-7xl text-white mb-4 md:mb-6">{service.name}</h1>
          <p className="text-base md:text-xl text-gray-300 max-w-2xl">{service.shortDesc}</p>
        </div>
      </section>

      {/* Content */}
      <section className="py-12 md:py-24 bg-white -mt-12 md:-mt-24 relative z-20" data-testid="service-detail-content">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-24">
            {/* Main Content */}
            <div className="lg:col-span-8">
              {/* Description */}
              <div className="mb-16">
                <h2 className="text-3xl md:text-4xl mb-6">Über diese Leistung</h2>
                <p className="text-gray-600 text-lg leading-relaxed">
                  {service.description}
                </p>
              </div>

              {/* Features */}
              <div className="mb-16">
                <h2 className="text-3xl md:text-4xl mb-8">Was wir bieten</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {service.features.map((feature, index) => (
                    <div 
                      key={index} 
                      className="flex items-start gap-3 p-4 bg-gray-50 border-l-4 border-[#C41E3A]"
                      data-testid={`feature-${index}`}
                    >
                      <CheckCircle className="text-[#C41E3A] flex-shrink-0 mt-0.5" size={20} />
                      <span className="text-gray-700">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Benefits */}
              <div className="mb-16">
                <h2 className="text-3xl md:text-4xl mb-8">Ihre Vorteile</h2>
                <div className="bg-[#0A0A0A] text-white p-8 lg:p-12">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {service.benefits.map((benefit, index) => (
                      <div key={index} className="flex items-center gap-3">
                        <div className="w-2 h-2 bg-[#C41E3A]"></div>
                        <span>{benefit}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* CTA */}
              <div className="bg-[#C41E3A] text-white p-8 lg:p-12">
                <h3 className="text-2xl md:text-3xl mb-4">Interesse an {service.name}?</h3>
                <p className="text-white/80 mb-6">
                  Kontaktieren Sie uns jetzt für ein unverbindliches Angebot. 
                  Wir melden uns innerhalb von 24 Stunden bei Ihnen.
                </p>
                <Link
                  to={`/anfrage?service=${service.id}`}
                  className="inline-flex items-center gap-2 bg-white text-[#C41E3A] px-8 py-4 font-bold uppercase tracking-wider hover:bg-gray-100 transition-colors"
                  data-testid="service-cta-button"
                >
                  Jetzt {service.name} anfragen
                  <ArrowRight size={18} />
                </Link>
              </div>
            </div>

            {/* Sidebar */}
            <div className="lg:col-span-4">
              <div className="sticky top-28 space-y-8">
                {/* Quick Contact */}
                <div className="bg-gray-50 p-6 border border-gray-200" data-testid="service-sidebar-contact">
                  <h3 className="text-xl font-bold mb-4" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Schnellkontakt
                  </h3>
                  <div className="space-y-4">
                    <a 
                      href={`tel:${companyInfo.phone}`}
                      className="flex items-center gap-3 text-gray-700 hover:text-[#C41E3A] transition-colors"
                    >
                      <Phone size={20} className="text-[#C41E3A]" />
                      <span>{companyInfo.phone}</span>
                    </a>
                    <a 
                      href={`mailto:${companyInfo.email}`}
                      className="flex items-center gap-3 text-gray-700 hover:text-[#C41E3A] transition-colors"
                    >
                      <Mail size={20} className="text-[#C41E3A]" />
                      <span>{companyInfo.email}</span>
                    </a>
                    <div className="flex items-center gap-3 text-gray-700">
                      <Clock size={20} className="text-[#C41E3A]" />
                      <span>Mo-Fr: 7:00 - 18:00</span>
                    </div>
                  </div>
                </div>

                {/* Quick Request */}
                <div className="bg-[#0A0A0A] text-white p-6" data-testid="service-sidebar-request">
                  <h3 className="text-xl font-bold mb-4" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Schnellanfrage
                  </h3>
                  <p className="text-gray-400 text-sm mb-4">
                    Jetzt unverbindlich anfragen und innerhalb von 24h ein Angebot erhalten.
                  </p>
                  <Link
                    to={`/anfrage?service=${service.id}`}
                    className="btn-primary w-full text-center py-4 block"
                    data-testid="sidebar-cta-button"
                  >
                    Anfrage starten
                  </Link>
                </div>

                {/* Why Us */}
                <div className="bg-gray-50 p-6 border border-gray-200">
                  <h3 className="text-xl font-bold mb-4" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    Warum wir?
                  </h3>
                  <ul className="space-y-3 text-sm text-gray-600">
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Über {new Date().getFullYear() - 2009} Jahre Erfahrung
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Geschultes Fachpersonal
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Modernste Ausrüstung
                    </li>
                    <li className="flex items-start gap-2">
                      <CheckCircle size={16} className="text-[#C41E3A] mt-0.5 flex-shrink-0" />
                      Vollversichert
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Navigation */}
      <section className="py-12 bg-gray-50 border-t border-gray-200" data-testid="service-navigation">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="flex justify-between items-center">
            {prevService ? (
              <Link
                to={`/leistungen/${prevService.id}`}
                className="flex items-center gap-2 text-gray-600 hover:text-[#C41E3A] transition-colors"
                data-testid="prev-service-link"
              >
                <ArrowLeft size={18} />
                <span className="text-sm uppercase tracking-wider">{prevService.name}</span>
              </Link>
            ) : (
              <div></div>
            )}
            {nextService && (
              <Link
                to={`/leistungen/${nextService.id}`}
                className="flex items-center gap-2 text-gray-600 hover:text-[#C41E3A] transition-colors"
                data-testid="next-service-link"
              >
                <span className="text-sm uppercase tracking-wider">{nextService.name}</span>
                <ArrowRight size={18} />
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* Other Services */}
      <section className="py-24 bg-white" data-testid="related-services">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <h2 className="text-3xl md:text-4xl mb-12 text-center">Weitere Leistungen</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {services.filter(s => s.id !== serviceId).slice(0, 3).map((s) => (
              <Link
                key={s.id}
                to={`/leistungen/${s.id}`}
                className="service-card group bg-white border border-gray-200 overflow-hidden block cursor-pointer relative z-10"
                data-testid={`related-service-${s.id}`}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                <div className="aspect-[16/10] overflow-hidden pointer-events-none">
                  <img
                    src={s.image}
                    alt={s.name}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                  />
                </div>
                <div className="p-6 pointer-events-none">
                  <h3 className="text-xl font-bold mb-2 group-hover:text-[#C41E3A] transition-colors" 
                      style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                    {s.name}
                  </h3>
                  <div className="flex items-center text-[#C41E3A] font-medium text-sm uppercase tracking-wider">
                    Mehr erfahren
                    <ArrowRight size={16} className="ml-2 group-hover:translate-x-2 transition-transform" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </PageWrapper>
  );
};

export default ServiceDetailPage;
