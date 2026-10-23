import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { istNativ, nativStarten } from './lib/native';
import './index.css';

// Service Worker nur im Browser (PWA); in der nativen App liegt die Oberfläche schon im Paket.
if (!istNativ()) {
  import('virtual:pwa-register').then(({ registerSW }) => registerSW({ immediate: true })).catch(() => {});
} else {
  nativStarten();
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
