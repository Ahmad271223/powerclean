/**
 * Push-Nachrichten in der App (iPhone: Apple, Android: Google/Firebase) – im Browser wirkungslos.
 * Nach der Anmeldung: Erlaubnis erfragen, Gerät beim Server melden. Antippen einer Nachricht öffnet den mitgeschickten Link
 * (z. B. /einsaetze?einsatz=…). Beim Abmelden wird das Gerät beim Server abgemeldet.
 */
import { api } from './api';
import { istNativ, plattform } from './native';

const TOKEN_KEY = 'szpro-push-token';
let gestartet = false;

const gemerkt = () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } };
const merken = (t) => { try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } };

/** Link aus einer Nachricht öffnen (HashRouter). Nur eigene Pfade, nie fremde Adressen. */
export function linkOeffnen(link) {
  if (typeof link !== 'string' || !link.startsWith('/') || link.startsWith('//')) return;
  window.location.hash = `#${link}`;
}

/** Nach der Anmeldung aufrufen. Fragt höchstens einmal je Sitzung nach der Erlaubnis. */
export async function pushStarten() {
  if (!istNativ() || gestartet) return;
  gestartet = true;
  let PushNotifications;
  try {
    ({ PushNotifications } = await import('@capacitor/push-notifications'));
  } catch { return; }
  try {
    await PushNotifications.removeAllListeners();
    await PushNotifications.addListener('registration', async ({ value }) => {
      if (!value) return;
      merken(value);
      try { await api.post('/api/geraete', { plattform: plattform() === 'ios' ? 'ios' : 'android', token: value, app_version: import.meta.env.VITE_APP_VERSION || '' }); }
      catch (err) { console.warn('Gerät nicht gemeldet', err); }
    });
    await PushNotifications.addListener('registrationError', (err) => console.warn('Push-Registrierung fehlgeschlagen', err));
    await PushNotifications.addListener('pushNotificationActionPerformed', ({ notification }) => linkOeffnen(notification?.data?.link));
    let erlaubnis = await PushNotifications.checkPermissions();
    if (erlaubnis.receive === 'prompt' || erlaubnis.receive === 'prompt-with-rationale') erlaubnis = await PushNotifications.requestPermissions();
    if (erlaubnis.receive !== 'granted') return;
    await PushNotifications.register();
  } catch (err) {
    console.warn('Push nicht verfügbar', err);   // z. B. Android ohne google-services.json
  }
}

/** Beim Abmelden: Gerät beim Server abmelden (solange das Anmelde-Token noch gilt). */
export function pushAbmelden() {
  const t = gemerkt();
  gestartet = false;
  if (!t) return;
  merken(null);
  api.post('/api/geraete/abmelden', { token: t }).catch(() => {});
}
