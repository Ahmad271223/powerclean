import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';

export const CookieBanner = () => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem('cookieConsent');
    if (!consent) {
      // Kurze Verzögerung für bessere UX
      setTimeout(() => setIsVisible(true), 500);
    }
  }, []);

  const acceptCookies = () => {
    localStorage.setItem('cookieConsent', 'accepted');
    setIsVisible(false);
  };

  const declineCookies = () => {
    localStorage.setItem('cookieConsent', 'declined');
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <div 
      className="fixed bottom-0 left-0 right-0 z-[100] bg-white border-t border-gray-200 shadow-lg p-4 md:p-6"
      data-testid="cookie-banner"
    >
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex-1 pr-4">
            <h3 className="font-bold text-lg mb-2" style={{ fontFamily: 'Barlow Condensed, sans-serif', textTransform: 'uppercase' }}>
              Cookie-Einstellungen
            </h3>
            <p className="text-sm text-gray-600">
              Wir verwenden Cookies, um Ihnen die bestmögliche Erfahrung auf unserer Website zu bieten. 
              Weitere Informationen finden Sie in unserer{' '}
              <Link to="/datenschutz" className="text-[#C41E3A] hover:underline">
                Datenschutzerklärung
              </Link>.
            </p>
          </div>
          
          <div className="flex flex-wrap gap-3">
            <button
              onClick={declineCookies}
              className="px-6 py-3 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors uppercase tracking-wider"
              data-testid="cookie-decline"
            >
              Ablehnen
            </button>
            <button
              onClick={acceptCookies}
              className="px-6 py-3 text-sm font-medium text-white bg-[#C41E3A] hover:bg-[#A01830] transition-colors uppercase tracking-wider"
              data-testid="cookie-accept"
            >
              Alle akzeptieren
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CookieBanner;
