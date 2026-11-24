// Prüft die Lizenzliste der App (src/lib/lizenzen.js) gegen package.json und node_modules:
// jede Laufzeit-Abhängigkeit muss aufgeführt sein, die Lizenz muss stimmen und erlaubt sein, und im ganzen Abhängigkeitsbaum
// darf keine GPL/AGPL/LGPL-Lizenz ohne freie Alternative stehen.   Aufruf: npm run lizenzen
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { BAUSTEINE, ERLAUBT } from '../src/lib/lizenzen.js';

const wurzel = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(fs.readFileSync(path.join(wurzel, 'package.json'), 'utf8'));
const fehler = [];
const liste = new Map(BAUSTEINE.filter((b) => b.paket).map((b) => [b.paket, b]));

for (const [name, quelle] of Object.entries(pkg.dependencies || {})) {
  if (String(quelle).startsWith('file:')) continue;   // eigener Code im Repo (z. B. plugins/sprache)
  const b = liste.get(name);
  const datei = path.join(wurzel, 'node_modules', name, 'package.json');
  const lizenz = fs.existsSync(datei) ? JSON.parse(fs.readFileSync(datei, 'utf8')).license : '(nicht installiert)';
  if (!b) fehler.push(`${name} (${lizenz}) fehlt in src/lib/lizenzen.js`);
  else if (b.lizenz !== lizenz) fehler.push(`${name}: Liste sagt ${b.lizenz}, Paket sagt ${lizenz}`);
  if (!ERLAUBT.includes(lizenz)) fehler.push(`${name}: Lizenz ${lizenz} ist nicht erlaubt`);
}

// Ganzer Baum: Copyleft nur, wenn eine freie Alternative angeboten wird („MPL-2.0 OR Apache-2.0“)
const copyleft = /\b(A?GPL|LGPL|SSPL|EUPL)\b/i;
function lauf(dir) {
  if (!fs.existsSync(dir)) return;
  for (const n of fs.readdirSync(dir)) {
    if (n.startsWith('.')) continue;
    const p = path.join(dir, n);
    if (n.startsWith('@')) { lauf(p); continue; }
    const f = path.join(p, 'package.json');
    if (fs.existsSync(f)) {
      try {
        const j = JSON.parse(fs.readFileSync(f, 'utf8'));
        const l = typeof j.license === 'string' ? j.license : JSON.stringify(j.license || j.licenses || '');
        const frei = l.split(/\s+OR\s+/i).some((t) => ERLAUBT.includes(t.replace(/[()]/g, '').trim()));
        if (copyleft.test(l) && !frei && !(pkg.devDependencies || {})[j.name]) fehler.push(`${j.name}@${j.version}: ${l}`);
      } catch { /* ungültige package.json ignorieren */ }
    }
    lauf(path.join(p, 'node_modules'));
  }
}
lauf(path.join(wurzel, 'node_modules'));

if (fehler.length) {
  console.error('Lizenzprüfung fehlgeschlagen:\n- ' + fehler.join('\n- '));
  process.exit(1);
}
console.log(`Lizenzprüfung bestanden: ${Object.keys(pkg.dependencies).length} Abhängigkeiten aufgeführt, keine Copyleft-Lizenz.`);
