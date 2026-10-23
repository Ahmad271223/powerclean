import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { services, companyInfo } from '../data/services';

// Titel, Beschreibung, Canonical, Open Graph und strukturierte Daten je Route.
// Die Website ist eine Single-Page-App, deshalb setzen wir die Tags beim Seitenwechsel.

export const SITE_URL = 'https://powercleanservice.de';
const SITE_NAME = 'PowerCleanService';
const DEFAULT_IMAGE = 'https://images.unsplash.com/photo-1555238920-7a6bea18473b?auto=format&fit=crop&w=1200&h=630&q=80';

const SEITEN = {
  '/': {
    title: 'Gebäudereinigung Hannover seit 2009 | PowerCleanService',
    description: 'PowerCleanService – Ihre Gebäudereinigung in Hannover: Unterhaltsreinigung, Büroreinigung, Baureinigung, Glas- und Industriereinigung. Unverbindliches Angebot in 24 h.',
  },
  '/leistungen': {
    title: 'Leistungen: Reinigung & Facility Services in Hannover | PowerCleanService',
    description: `${services.length} Leistungen aus einer Hand: Unterhalts-, Büro-, Bau-, Glas-, Fassaden- und Industriereinigung, Hausmeisterdienste und Facility Management in Hannover und Region.`,
    breadcrumb: [{ name: 'Leistungen', path: '/leistungen' }],
  },
  '/anfrage': {
    title: 'Reinigung anfragen – kostenloses Angebot | PowerCleanService Hannover',
    description: 'Fordern Sie jetzt Ihr unverbindliches Angebot für Gebäudereinigung in Hannover an. Wir melden uns innerhalb von 24 Stunden.',
    breadcrumb: [{ name: 'Anfrage', path: '/anfrage' }],
  },
  '/kontakt': {
    title: 'Kontakt | PowerCleanService Gebäudereinigung Hannover',
    description: `PowerCleanService, ${companyInfo.street}, ${companyInfo.city}. Telefon ${companyInfo.phone}, WhatsApp oder E-Mail – wir sind für Sie erreichbar.`,
    breadcrumb: [{ name: 'Kontakt', path: '/kontakt' }],
  },
  '/impressum': {
    title: 'Impressum | PowerCleanService',
    description: 'Impressum der PowerCleanService Gebäudereinigung in Hannover.',
    breadcrumb: [{ name: 'Impressum', path: '/impressum' }],
  },
  '/datenschutz': {
    title: 'Datenschutzerklärung | PowerCleanService',
    description: 'Informationen zum Datenschutz auf powercleanservice.de.',
    breadcrumb: [{ name: 'Datenschutz', path: '/datenschutz' }],
  },
  '/agb': {
    title: 'AGB | PowerCleanService',
    description: 'Allgemeine Geschäftsbedingungen der PowerCleanService Gebäudereinigung in Hannover.',
    breadcrumb: [{ name: 'AGB', path: '/agb' }],
  },
};

// Interne Bereiche (Verwaltung, Stundenzettel) gehören nicht in den Google-Index.
const NICHT_INDEXIEREN = ['/pcs-verwaltung-2024', '/stundenzettel'];

const kuerzen = (text, max = 158) => (text.length <= max ? text : `${text.slice(0, max - 1).replace(/\s+\S*$/, '')} …`);

function seiteFuer(pathname) {
  const pfad = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;

  if (NICHT_INDEXIEREN.some((p) => pfad === p || pfad.startsWith(`${p}/`))) {
    return { title: SITE_NAME, description: '', noindex: true, pfad };
  }

  const match = pfad.match(/^\/leistungen\/([^/]+)$/);
  if (match) {
    const service = services.find((s) => s.id === match[1]);
    if (!service) return { ...SEITEN['/leistungen'], pfad: '/leistungen' };
    return {
      pfad,
      title: `${service.name} in Hannover | PowerCleanService`,
      description: kuerzen(`${service.name} in Hannover und Region: ${service.shortDesc} ${service.description}`),
      image: service.image.replace('w=800', 'w=1200'),
      breadcrumb: [
        { name: 'Leistungen', path: '/leistungen' },
        { name: service.name, path: pfad },
      ],
      service,
    };
  }

  const seite = SEITEN[pfad];
  if (!seite) return { title: SITE_NAME, description: '', noindex: true, pfad };
  return { ...seite, pfad };
}

function setMeta(attr, key, content) {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!content) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function setCanonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!href) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

function setJsonLd(daten) {
  document.head.querySelectorAll('script[data-seo="route"]').forEach((el) => el.remove());
  daten.forEach((d) => {
    const el = document.createElement('script');
    el.type = 'application/ld+json';
    el.dataset.seo = 'route';
    el.textContent = JSON.stringify(d);
    document.head.appendChild(el);
  });
}

function strukturierteDaten(seite, url) {
  const daten = [];
  if (seite.breadcrumb) {
    daten.push({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [{ name: 'Startseite', path: '/' }, ...seite.breadcrumb].map((b, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: b.name,
        item: `${SITE_URL}${b.path === '/' ? '/' : b.path}`,
      })),
    });
  }
  if (seite.service) {
    daten.push({
      '@context': 'https://schema.org',
      '@type': 'Service',
      name: seite.service.name,
      serviceType: seite.service.name,
      description: seite.service.description,
      url,
      image: seite.image,
      areaServed: [
        { '@type': 'City', name: 'Hannover' },
        { '@type': 'AdministrativeArea', name: 'Region Hannover' },
      ],
      provider: { '@id': `${SITE_URL}/#organisation` },
    });
  }
  return daten;
}

export const RouteSeo = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    const seite = seiteFuer(pathname);
    const url = `${SITE_URL}${seite.pfad === '/' ? '/' : seite.pfad}`;

    document.title = seite.title;
    setMeta('name', 'description', seite.description);
    setMeta('name', 'robots', seite.noindex ? 'noindex, nofollow' : 'index, follow, max-image-preview:large');
    setCanonical(seite.noindex ? null : url);

    setMeta('property', 'og:title', seite.title);
    setMeta('property', 'og:description', seite.description);
    setMeta('property', 'og:url', url);
    setMeta('property', 'og:image', seite.image || DEFAULT_IMAGE);
    setMeta('name', 'twitter:title', seite.title);
    setMeta('name', 'twitter:description', seite.description);
    setMeta('name', 'twitter:image', seite.image || DEFAULT_IMAGE);

    setJsonLd(seite.noindex ? [] : strukturierteDaten(seite, url));
  }, [pathname]);

  return null;
};

export default RouteSeo;
