// Quellbilder für @capacitor/assets aus den PWA-Icons erzeugen (assets/icon-only.png 1024, Vorder-/Hintergrund, Splash 2732).
// Aufruf über `npm run assets`. Braucht nur Node (sharp kommt mit @capacitor/assets).
import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), '..');
const quelle = path.join(root, 'public', 'icon-512.png');
const maskable = path.join(root, 'public', 'icon-512-maskable.png');
const ziel = path.join(root, 'assets');
fs.mkdirSync(ziel, { recursive: true });

const hell = '#F5F5F7';
const dunkel = '#1D1D1F';

async function flaeche(groesse, farbe) {
  return sharp({ create: { width: groesse, height: groesse, channels: 4, background: farbe } }).png();
}

async function iconOnly() {
  const icon = await sharp(fs.existsSync(maskable) ? maskable : quelle).resize(1024, 1024, { fit: 'cover' }).png().toBuffer();
  await sharp(icon).toFile(path.join(ziel, 'icon-only.png'));
}

async function adaptive() {
  // Vordergrund: Icon auf 66 % der Fläche (Android schneidet den Rand ab), transparent
  const motiv = await sharp(quelle).resize(680, 680, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toBuffer();
  await sharp({ create: { width: 1024, height: 1024, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite([{ input: motiv, gravity: 'centre' }]).png().toFile(path.join(ziel, 'icon-foreground.png'));
  await (await flaeche(1024, hell)).toFile(path.join(ziel, 'icon-background.png'));
}

async function splash() {
  const motiv = await sharp(quelle).resize(560, 560, { fit: 'contain' }).png().toBuffer();
  for (const [name, farbe] of [['splash.png', hell], ['splash-dark.png', dunkel]]) {
    await (await flaeche(2732, farbe)).composite([{ input: motiv, gravity: 'centre' }]).png().toFile(path.join(ziel, name));
  }
}

await iconOnly();
await adaptive();
await splash();
console.log('Quellbilder erzeugt in', ziel, fs.readdirSync(ziel).join(', '));
