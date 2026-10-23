import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

export default defineConfig({
  base: './',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon-180.png'],
      manifest: {
        name: 'Stundenzettel',
        short_name: 'Stundenzettel',
        description: 'Arbeitszeiten, Stundenzettel und Rechnungen – komplett offline auf dem Gerät.',
        lang: 'de',
        start_url: './',
        scope: './',
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
      },
    }),
  ],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  build: { outDir: 'dist', chunkSizeWarningLimit: 2000 },
});
