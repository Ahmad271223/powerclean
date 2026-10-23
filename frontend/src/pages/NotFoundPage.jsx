import React from 'react';
import { Link } from 'react-router-dom';
import { PageWrapper } from '../components/Layout';
import { services } from '../data/services';
import { ArrowRight } from 'lucide-react';

const NotFoundPage = () => {
  return (
    <PageWrapper>
      <section className="py-24 lg:py-32 bg-white" data-testid="not-found">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <div className="text-[#C41E3A] text-sm uppercase tracking-widest font-medium mb-4">Fehler 404</div>
          <h1 className="text-5xl md:text-6xl mb-6">Seite nicht gefunden</h1>
          <p className="text-gray-600 text-lg mb-10">
            Die aufgerufene Seite existiert nicht oder wurde verschoben. Vielleicht hilft Ihnen eine unserer Leistungen weiter:
          </p>
          <div className="flex flex-wrap justify-center gap-3 mb-10">
            {services.slice(0, 6).map((s) => (
              <Link
                key={s.id}
                to={`/leistungen/${s.id}`}
                className="bg-gray-100 px-4 py-2 text-sm font-medium hover:bg-[#C41E3A] hover:text-white transition-colors"
              >
                {s.name}
              </Link>
            ))}
          </div>
          <Link to="/" className="btn-primary inline-flex items-center gap-2 px-8 py-4">
            Zur Startseite
            <ArrowRight size={18} />
          </Link>
        </div>
      </section>
    </PageWrapper>
  );
};

export default NotFoundPage;
