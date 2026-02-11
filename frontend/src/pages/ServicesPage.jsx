import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageWrapper, Breadcrumb } from '../components/Layout';
import { services } from '../data/services';
import { ArrowRight, Search } from 'lucide-react';
import { Input } from '../components/ui/input';

const ServicesPage = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const categories = [
    { id: 'all', name: 'Alle Leistungen' },
    { id: 'reinigung', name: 'Reinigung' },
    { id: 'pflege', name: 'Pflege & Wartung' },
    { id: 'management', name: 'Management' }
  ];

  const getCategoryForService = (serviceId) => {
    const managementServices = ['facility-management', 'hausmeisterdienste', 'baustellenueberwachung'];
    const pflegeServices = ['gruen-aussenflaechenpflege', 'dach-photovoltaikreinigung'];
    
    if (managementServices.includes(serviceId)) return 'management';
    if (pflegeServices.includes(serviceId)) return 'pflege';
    return 'reinigung';
  };

  const filteredServices = services.filter((service) => {
    const matchesSearch = service.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         service.shortDesc.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || getCategoryForService(service.id) === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <PageWrapper>
      {/* Hero */}
      <section className="bg-[#0A0A0A] text-white py-24 lg:py-32" data-testid="services-hero">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <Breadcrumb items={[{ label: 'Leistungen' }]} />
          <h1 className="text-5xl md:text-6xl lg:text-7xl mb-6">Unsere Leistungen</h1>
          <p className="text-xl text-gray-400 max-w-2xl">
            14 professionelle Dienstleistungen für Reinigung, Pflege und Facility Management. 
            Qualität seit 2009.
          </p>
        </div>
      </section>

      {/* Filter Bar */}
      <section className="bg-white border-b border-gray-200 py-6 sticky top-20 z-40" data-testid="services-filter">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            {/* Search */}
            <div className="relative w-full md:w-96">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
              <Input
                type="text"
                placeholder="Leistung suchen..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 h-12"
                data-testid="services-search-input"
              />
            </div>

            {/* Category Filter */}
            <div className="flex flex-wrap gap-2">
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-4 py-2 text-sm font-medium uppercase tracking-wider transition-colors ${
                    selectedCategory === cat.id
                      ? 'bg-[#C41E3A] text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  data-testid={`filter-${cat.id}`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Services Grid */}
      <section className="py-16 lg:py-24 bg-gray-50" data-testid="services-grid">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {filteredServices.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500 text-lg">Keine Leistungen gefunden.</p>
              <button
                onClick={() => { setSearchTerm(''); setSelectedCategory('all'); }}
                className="mt-4 text-[#C41E3A] font-medium"
              >
                Filter zurücksetzen
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {filteredServices.map((service, index) => (
                <Link
                  key={service.id}
                  to={`/leistungen/${service.id}`}
                  className="service-card group bg-white border border-gray-200 overflow-hidden animate-fade-in-up"
                  style={{ animationDelay: `${index * 0.05}s` }}
                  data-testid={`service-card-${service.id}`}
                >
                  <div className="aspect-[16/10] overflow-hidden">
                    <img
                      src={service.image}
                      alt={service.name}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    />
                  </div>
                  <div className="p-6">
                    <div className="text-xs uppercase tracking-widest text-[#C41E3A] font-medium mb-2">
                      {categories.find(c => c.id === getCategoryForService(service.id))?.name || 'Reinigung'}
                    </div>
                    <h3 className="text-2xl font-bold mb-3 group-hover:text-[#C41E3A] transition-colors" 
                        style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
                      {service.name}
                    </h3>
                    <p className="text-gray-600 mb-4 line-clamp-2">
                      {service.shortDesc}
                    </p>
                    <div className="flex items-center text-[#C41E3A] font-medium text-sm uppercase tracking-wider">
                      Mehr erfahren
                      <ArrowRight size={16} className="ml-2 group-hover:translate-x-2 transition-transform" />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 bg-[#0A0A0A] text-white" data-testid="services-cta">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 text-center">
          <h2 className="text-3xl md:text-4xl mb-4">Nicht sicher, welche Leistung Sie benötigen?</h2>
          <p className="text-gray-400 mb-8 max-w-xl mx-auto">
            Kontaktieren Sie uns für eine unverbindliche Beratung. Wir finden die passende Lösung für Sie.
          </p>
          <Link
            to="/anfrage"
            className="btn-primary inline-flex items-center gap-2 px-8 py-4"
            data-testid="services-cta-button"
          >
            Jetzt Anfragen
            <ArrowRight size={18} />
          </Link>
        </div>
      </section>
    </PageWrapper>
  );
};

export default ServicesPage;
