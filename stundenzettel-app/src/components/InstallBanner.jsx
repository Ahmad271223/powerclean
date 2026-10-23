import React, { useEffect, useState } from 'react';
import { Download, Smartphone, X, ExternalLink } from 'lucide-react';
import { Btn } from './ui';

/*
 * Install helper shown while the app runs in a normal browser tab.
 *  - Chrome / Edge (Android + Desktop): one-tap "App installieren" via beforeinstallprompt.
 *  - Samsung Internet: its own install path mints an app package that Android flags as
 *    "built for an older Android version" (a Samsung issue, not fixable from the web app).
 *    We therefore send the user to Chrome with a deep link, or to the plain home-screen shortcut.
 *  - iOS Safari: has no install API, show the Share → "Zum Home-Bildschirm" hint.
 */

const ua = typeof navigator !== 'undefined' ? navigator.userAgent : '';
const isStandalone = () => {
  try { return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true; } catch { return false; }
};
const isSamsungBrowser = /SamsungBrowser/i.test(ua);
const isIOS = /iPhone|iPad|iPod/i.test(ua);
const isAndroid = /Android/i.test(ua);
const chromeIntent = () =>
  `intent://${window.location.host}${window.location.pathname}${window.location.search}#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=${encodeURIComponent(window.location.href)};end`;

const HIDE_KEY = 'ts-install-hint-hidden';

export default function InstallBanner() {
  const [promptEvent, setPromptEvent] = useState(null);
  const [installed, setInstalled] = useState(isStandalone());
  const [hidden, setHidden] = useState(() => { try { return sessionStorage.getItem(HIDE_KEY) === '1'; } catch { return false; } });

  useEffect(() => {
    const onPrompt = (e) => { e.preventDefault(); setPromptEvent(e); };
    const onInstalled = () => setInstalled(true);
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  if (installed || hidden) return null;

  const dismiss = () => { setHidden(true); try { sessionStorage.setItem(HIDE_KEY, '1'); } catch { /* ignore */ } };
  const install = async () => {
    if (!promptEvent) return;
    promptEvent.prompt();
    try { const r = await promptEvent.userChoice; if (r?.outcome === 'accepted') setInstalled(true); } catch { /* ignore */ }
    setPromptEvent(null);
  };

  let title = 'Als App installieren';
  let text = null;
  let action = null;

  if (isSamsungBrowser) {
    title = 'Bitte mit Chrome installieren';
    text = 'Samsung Internet zeigt beim Installieren fälschlich eine Warnung wegen einer „älteren Android-Version“. In Chrome erscheint sie nicht.';
    action = (
      <a href={chromeIntent()} className="inline-flex items-center justify-center gap-2 h-11 px-5 rounded-full bg-[#C41E3A] text-white text-[15px] font-semibold whitespace-nowrap">
        <ExternalLink size={16} /> In Chrome öffnen
      </a>
    );
  } else if (promptEvent) {
    text = 'Dann startet die App vom Home-Bildschirm und funktioniert auch ohne Internet.';
    action = <Btn onClick={install}><Download size={16} /> App installieren</Btn>;
  } else if (isIOS) {
    text = 'Unten das Teilen-Symbol antippen und „Zum Home-Bildschirm“ wählen.';
  } else if (isAndroid) {
    text = 'Oben rechts ⋮ antippen und „App installieren“ bzw. „Zum Startbildschirm hinzufügen“ wählen.';
  } else {
    return null;
  }

  return (
    <div className="mb-5 rounded-2xl bg-white shadow-card px-4 py-3 text-[14px] flex flex-wrap items-center gap-3" data-testid="install-banner">
      <span className="w-9 h-9 rounded-xl bg-[#C41E3A]/10 text-[#C41E3A] flex items-center justify-center shrink-0"><Smartphone size={18} /></span>
      <span className="flex-1 min-w-[200px]">
        <span className="font-semibold">{title}</span>
        {text && <span className="text-[#6E6E73]"> {text}</span>}
        {isSamsungBrowser && <span className="block text-[12px] text-[#86868B] mt-0.5">Alternativ hier: Menü ≡ → „Seite hinzufügen zu“ → „Startbildschirm“.</span>}
      </span>
      {action}
      <button type="button" onClick={dismiss} className="w-8 h-8 rounded-full hover:bg-black/[0.05] flex items-center justify-center text-[#86868B]" aria-label="Hinweis ausblenden"><X size={15} /></button>
    </div>
  );
}
