/**
 * Native Hülle (Capacitor, Android/iOS): Deep Links (QR-Codes, Einladungen), Zurück-Taste, Statusleiste.
 * Im Browser sind alle Aufrufe wirkungslos.
 */
import { Capacitor } from '@capacitor/core';

export const istNativ = () => Capacitor.isNativePlatform();
export const plattform = () => Capacitor.getPlatform();   // 'web' | 'android' | 'ios'

/** Hash einer geöffneten Adresse übernehmen: https://server/#/stempeln/<id> → #/stempeln/<id>. */
function hashUebernehmen(url) {
  try {
    const u = new URL(url);
    const hash = u.hash && u.hash.length > 1 ? u.hash : (u.pathname && u.pathname !== '/' ? `#${u.pathname}` : '');
    if (hash) window.location.hash = hash;
  } catch { /* ungültige Adresse ignorieren */ }
}

export async function nativStarten() {
  if (!istNativ()) return;
  try {
    const { App } = await import('@capacitor/app');
    App.addListener('appUrlOpen', ({ url }) => hashUebernehmen(url));
    App.addListener('backButton', ({ canGoBack }) => { if (canGoBack) window.history.back(); else App.exitApp(); });
    const start = await App.getLaunchUrl();
    if (start?.url) hashUebernehmen(start.url);
  } catch (err) { console.warn('App-Plugin nicht verfügbar', err); }
  try {
    const { StatusBar, Style } = await import('@capacitor/status-bar');
    await StatusBar.setStyle({ style: Style.Light });
    if (plattform() === 'android') await StatusBar.setBackgroundColor({ color: '#F5F5F7' });
  } catch { /* Statusleiste optional */ }
  try {
    const { SplashScreen } = await import('@capacitor/splash-screen');
    await SplashScreen.hide();
  } catch { /* Splash optional */ }
}
