import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Phone, MessageCircle, Menu, X, ChevronRight } from 'lucide-react';
import { companyInfo } from '../data/services';

export const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();

  const navLinks = [
    { path: '/', label: 'Home' },
    { path: '/leistungen', label: 'Leistungen' },
    { path: '/anfrage', label: 'Anfrage' },
    { path: '/kontakt', label: 'Kontakt' }
  ];

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-100" data-testid="header">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <Link to="/" className="flex items-center" data-testid="logo-link">
            <span className="logo-power text-2xl md:text-3xl">Power</span>
            <span className="logo-clean text-2xl md:text-3xl">Clean-Service</span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-8" data-testid="desktop-nav">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`font-medium text-sm uppercase tracking-wider transition-colors ${
                  isActive(link.path)
                    ? 'text-[#C41E3A]'
                    : 'text-gray-700 hover:text-[#C41E3A]'
                }`}
                data-testid={`nav-link-${link.path.replace('/', '') || 'home'}`}
              >
                {link.label}
              </Link>
            ))}
            <Link
              to="/anfrage"
              className="btn-primary px-6 py-3 text-sm"
              data-testid="nav-cta-button"
            >
              Jetzt Anfragen
            </Link>
          </nav>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            data-testid="mobile-menu-button"
            aria-label="Menu"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Navigation */}
      {isMenuOpen && (
        <div className="md:hidden bg-white border-t border-gray-100" data-testid="mobile-nav">
          <nav className="flex flex-col py-4">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`px-6 py-4 font-medium text-sm uppercase tracking-wider ${
                  isActive(link.path)
                    ? 'text-[#C41E3A] bg-gray-50'
                    : 'text-gray-700'
                }`}
                onClick={() => setIsMenuOpen(false)}
                data-testid={`mobile-nav-link-${link.path.replace('/', '') || 'home'}`}
              >
                {link.label}
              </Link>
            ))}
            <div className="px-6 py-4">
              <Link
                to="/anfrage"
                className="btn-primary block text-center py-4"
                onClick={() => setIsMenuOpen(false)}
                data-testid="mobile-nav-cta-button"
              >
                Jetzt Anfragen
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
};

export const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-[#0A0A0A] text-white" data-testid="footer">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-16 lg:py-24">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12">
          {/* Company Info */}
          <div>
            <div className="flex items-center mb-6">
              <span className="logo-power text-2xl">Power</span>
              <span className="text-white font-bold text-2xl" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>Clean-Service</span>
            </div>
            <p className="text-gray-400 mb-2">Deutsches Handwerk seit {companyInfo.since}.</p>
            <p className="text-gray-400">Qualität, Zuverlässigkeit und Professionalität.</p>
          </div>

          {/* Contact */}
          <div>
            <h4 className="text-lg font-bold mb-6 text-white">Kontakt</h4>
            <address className="not-italic text-gray-400 space-y-2">
              <p>{companyInfo.owner}</p>
              <p>{companyInfo.street}</p>
              <p>{companyInfo.city}</p>
              <p className="pt-2">
                <a href={`tel:${companyInfo.phone}`} className="hover:text-[#C41E3A] transition-colors">
                  Tel.: {companyInfo.phone}
                </a>
              </p>
              <p>
                <a href={`mailto:${companyInfo.email}`} className="hover:text-[#C41E3A] transition-colors">
                  {companyInfo.email}
                </a>
              </p>
            </address>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="text-lg font-bold mb-6 text-white">Schnellzugriff</h4>
            <nav className="space-y-3">
              <Link to="/leistungen" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">Leistungen</Link>
              <Link to="/anfrage" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">Anfrage</Link>
              <Link to="/kontakt" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">Kontakt</Link>
              <Link to="/admin" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">Admin</Link>
            </nav>
          </div>

          {/* Legal */}
          <div>
            <h4 className="text-lg font-bold mb-6 text-white">Rechtliches</h4>
            <nav className="space-y-3">
              <Link to="/impressum" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">Impressum</Link>
              <Link to="/datenschutz" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">Datenschutz</Link>
              <Link to="/agb" className="block text-gray-400 hover:text-[#C41E3A] transition-colors">AGB</Link>
            </nav>
          </div>
        </div>

        <div className="border-t border-gray-800 mt-12 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-gray-500 text-sm">
            © {currentYear} PowerCleanService. Alle Rechte vorbehalten.
          </p>
          <div className="flex gap-4">
            <a
              href={`https://wa.me/49${companyInfo.phone.replace(/\s/g, '').replace(/^0/, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-[#25D366] transition-colors"
              data-testid="footer-whatsapp"
            >
              WhatsApp
            </a>
            <a
              href={`tel:${companyInfo.phone}`}
              className="text-gray-400 hover:text-[#C41E3A] transition-colors"
              data-testid="footer-phone"
            >
              Anrufen
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export const FloatingButtons = () => {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3" data-testid="floating-buttons">
      <a
        href={`tel:${companyInfo.phone}`}
        className="flex items-center gap-2 bg-white text-gray-900 px-4 py-3 rounded-full shadow-lg hover:shadow-xl transition-all border border-gray-200"
        data-testid="floating-call-button"
      >
        <Phone size={20} className="text-[#C41E3A]" />
        <span className="font-medium text-sm">Anrufen</span>
      </a>
      <a
        href={`https://wa.me/49${companyInfo.phone.replace(/\s/g, '').replace(/^0/, '')}`}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 bg-[#25D366] text-white px-4 py-3 rounded-full shadow-lg hover:shadow-xl transition-all hover:bg-[#20bd5a]"
        data-testid="floating-whatsapp-button"
      >
        <MessageCircle size={20} />
        <span className="font-medium text-sm">WhatsApp</span>
      </a>
    </div>
  );
};

export const PageWrapper = ({ children, className = "" }) => {
  return (
    <div className={`min-h-screen ${className}`}>
      <Header />
      <main className="pt-20">
        {children}
      </main>
      <Footer />
      <FloatingButtons />
    </div>
  );
};

export const Breadcrumb = ({ items }) => {
  return (
    <nav className="flex items-center gap-2 text-sm text-gray-500 mb-8" data-testid="breadcrumb">
      <Link to="/" className="hover:text-[#C41E3A] transition-colors">Home</Link>
      {items.map((item, index) => (
        <React.Fragment key={index}>
          <ChevronRight size={14} />
          {item.path ? (
            <Link to={item.path} className="hover:text-[#C41E3A] transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-gray-900">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};
