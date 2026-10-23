import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { services } from './src/data/services.js';

const SITE_URL = 'https://powercleanservice.de';

// sitemap.xml beim Build aus den Leistungen erzeugen, damit neue Leistungsseiten automatisch drinstehen
function sitemap() {
    return {
        name: 'pcs-sitemap',
        apply: 'build',
        generateBundle() {
            const heute = new Date().toISOString().slice(0, 10);
            const seiten = [
                { pfad: '/', prio: '1.0', freq: 'weekly' },
                { pfad: '/leistungen', prio: '0.9', freq: 'weekly' },
                ...services.map((s) => ({ pfad: `/leistungen/${s.id}`, prio: '0.8', freq: 'monthly' })),
                { pfad: '/anfrage', prio: '0.7', freq: 'yearly' },
                { pfad: '/kontakt', prio: '0.7', freq: 'yearly' },
                { pfad: '/impressum', prio: '0.2', freq: 'yearly' },
                { pfad: '/datenschutz', prio: '0.2', freq: 'yearly' },
                { pfad: '/agb', prio: '0.2', freq: 'yearly' },
            ];
            const urls = seiten
                .map((s) => `  <url>\n    <loc>${SITE_URL}${s.pfad}</loc>\n    <lastmod>${heute}</lastmod>\n    <changefreq>${s.freq}</changefreq>\n    <priority>${s.prio}</priority>\n  </url>`)
                .join('\n');
            this.emitFile({
                type: 'asset',
                fileName: 'sitemap.xml',
                source: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
            });
        },
    };
}

export default defineConfig({
    plugins: [react(), sitemap()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    build: {
        outDir: 'build', // match existing CRA deployment publish directory
    },
});
