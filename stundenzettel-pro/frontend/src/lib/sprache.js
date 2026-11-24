/**
 * Spracheingabe über den nativen Baustein „Sprache“ (plugins/sprache): iPhone WhisperKit (Rückfall Apple auf dem Gerät), Android
 * Spracherkennung auf dem Gerät. Die Aufnahme bleibt immer auf dem Gerät und wird nicht gespeichert.
 * Im Browser gibt es bewusst keine Spracheingabe (Browser-Spracherkennung schickt die Aufnahme an Dritte) – dort wird getippt.
 */
import { registerPlugin } from '@capacitor/core';
import { istNativ } from './native';

const Sprache = registerPlugin('Sprache');

export const spracheMoeglich = () => istNativ();

export async function sprachStatus() {
  if (!istNativ()) return { plattform: 'web', modellGeladen: false };
  return Sprache.status();
}

/** Modell laden (iPhone: einmalig Download mit Fortschritt 0…1). */
export async function modellLaden(onFortschritt) {
  const abo = onFortschritt ? await Sprache.addListener('fortschritt', ({ anteil }) => onFortschritt(Math.max(0, Math.min(1, Number(anteil) || 0)))) : null;
  try { return await Sprache.modellLaden(); } finally { abo?.remove(); }
}

export const aufnahmeStarten = () => Sprache.aufnahmeStarten();
export const aufnahmeBeenden = () => Sprache.aufnahmeBeenden();   // → { text, engine }
export const aufnahmeAbbrechen = () => Sprache.aufnahmeAbbrechen().catch(() => {});

/** Satz auf dem Gerät zerlegen (iPhone mit Apple-KI). Gibt { felder, quelle } oder null – dann zerlegt der Server. */
export async function geraetZerlegen(text) {
  if (!istNativ()) return null;
  try { return await Sprache.zerlegen({ text }); } catch { return null; }
}

/** Fehlermeldung des Bausteins als Klartext (Capacitor liefert sie in err.message). */
export const sprachFehler = (err) => (err && err.message) || 'Spracheingabe nicht möglich.';
