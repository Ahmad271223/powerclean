import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

// Entwicklung: Oberfläche auf 5175, API auf 8010 (DB_MODE=memory reicht zum Ausprobieren).
export default defineConfig({
  base: '/',
  server: { port: 5175, proxy: { '/api': { target: 'http://127.0.0.1:8010', changeOrigin: true } } },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon-180.png'],
      manifest: {
        name: 'Stundenzettel Pro',
        short_name: 'Stundenzettel',
        description: 'Zeiterfassung, Stundenzettel und Rechnungen für Teams – mit Stempeluhr, Personalakte und Lohnexport.',
        lang: 'de',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#F5F5F7',
        theme_color: '#F5F5F7',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico}'],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  build: { outDir: 'dist', chunkSizeWarningLimit: 2000 },
});
