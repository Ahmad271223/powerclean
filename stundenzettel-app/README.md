# Stundenzettel – eigenständige App (PWA)

Arbeitszeiten, Stundenzettel und Rechnungen **komplett offline auf dem Handy**.
Kein Server, kein Login, keine Datenbank: alle Daten liegen im Speicher des Geräts,
die PDFs werden direkt auf dem Gerät erzeugt und können per Teilen-Menü
(WhatsApp, E-Mail, Dateien, AirDrop …) weitergegeben werden.

## Was die App kann

- **Meine Firma**: Einrichtung beim ersten Start (Logo, Name, Inhaber, Anschrift, Kontakt,
  Steuernummer/USt-IdNr., IBAN, Standard-Stundensatz, USt. oder § 19). Mehrere Firmen möglich,
  jede mit eigener Rechnungsnummernfolge.
- **Firmenstempel & Unterschrift**: in den Firmeneinstellungen aus den Firmendaten erzeugt
  (sechs Designs, Stempelfarbe, leicht schräg, Abnutzung), Unterschrift per Finger/Stift direkt
  auf den Stempel. Erscheint groß auf jedem Stundenzettel (über „Unterschrift Mitarbeiter“) und
  auf jeder Rechnung (unter „Mit freundlichen Grüßen“), Größe einstellbar (50–150 %).
- **Meine Projekte**: Projekte als Kacheln mit Suche, sortiert nach letzter Aktivität. Abgeschlossene
  Projekte lassen sich archivieren (bleiben mit allen Daten erhalten). Kalender ab 2025 bis mindestens
  zehn Jahre in die Zukunft (wächst automatisch mit).
- **Kalender**: Tag antippen → Anfang, Arbeitsende, Pause, Tätigkeit. Schnellwahl für
  typische Zeiten, Pause-Chips, zuletzt benutzte Tätigkeiten.
- **Mitarbeiter-Anzahl**: Im Projekt wird eine Standard-Anzahl hinterlegt (z. B. 2), jeder Tageseintrag
  übernimmt sie und kann sie einzeln ändern. Stunden zählen pro Mitarbeiter (4 × 7:30 h = 30:00 h).
  Teil der Mannschaft mit anderer Zeit = zweite Zeile am selben Tag. Der Stundenzettel hat dafür die
  Spalte „Mitarb.“, Übersicht und Rechnung rechnen in Mitarbeiterstunden.
- **Stundenzettel pro Kalenderwoche** als PDF (Datum · Tätigkeit · Anfang · Arbeitsende ·
  Netto Arbeitszeit · Unterschrift).
- **Monats-PDF**: alle Wochen-Stundenzettel + Monatsübersicht + Rechnung in einer Datei.
- **Rechnungsübersicht** pro Firma.
- **Datensicherung**: Export/Import als Datei (z. B. in iCloud/Google Drive aufbewahren
  oder auf ein neues Handy übertragen). Die App erinnert nach 14 Tagen ohne Sicherung daran und
  bietet bei einem Anzeigefehler eine Notfallsicherung an.

## Auf dem Handy installieren

Die App muss einmal von einer Webadresse geöffnet werden (siehe „Veröffentlichen“).
Danach läuft sie auch ohne Internet.

- **iPhone (Safari)**: Adresse öffnen → Teilen-Symbol → „Zum Home-Bildschirm“.
- **Android (Chrome)**: Adresse öffnen → Knopf „App installieren“ in der App (oder Menü ⋮ → „App installieren“).
- **Samsung Internet**: zeigt beim eigenen Installieren fälschlich „App für ältere Android-Version“
  (bekannter Samsung-Fehler, das Installationspaket des Samsung-Browsers zielt auf eine alte Android-Version).
  Die App erkennt den Samsung-Browser und bietet „In Chrome öffnen“ an; Alternative: Menü ≡ →
  „Seite hinzufügen zu“ → „Startbildschirm“.

Wichtig: Die Daten gehören zur installierten App. Vor einem Handywechsel in der App
„Datensicherung“ exportieren.

## Veröffentlicht unter

**https://ahmad271223.github.io/stundenzettel/** (GitHub Pages, eigenes Repository `Ahmad271223/stundenzettel`,
unabhängig von der PowerClean-Website). Diese Adresse an Kunden weitergeben; sie installieren die App
über „Zum Startbildschirm“ (siehe oben).

Neue Version veröffentlichen (nach Änderungen):

```bash
cd stundenzettel-app
npm run deploy
```

Installierte Apps holen sich das Update beim nächsten Öffnen automatisch.

## Veröffentlichen (eine statische Webadresse genügt)

```bash
cd stundenzettel-app
npm install
npm run build
```

Den Inhalt von `dist/` auf einen beliebigen statischen Webspace hochladen
(z. B. Netlify, GitHub Pages, der eigene Webspace). HTTPS ist Pflicht, sonst
funktioniert die Installation auf dem Handy nicht.

Alternativ wird die App zusammen mit der PowerClean-Website unter `/app/` veröffentlicht:

```bash
cd stundenzettel-app
npm run build:website
```

Das schreibt den Build nach `frontend/public/app/`. Nach dem nächsten Deploy der Website
ist die App unter `https://www.powercleanservice.de/app/` erreichbar.

## Lokal entwickeln

```bash
cd stundenzettel-app
npm install
npm run dev
```

Dann `http://localhost:5174` öffnen (Port aus `.claude/launch.json`).

## Technik

React + Vite, Tailwind, Radix Dialog, jsPDF + autotable (PDF auf dem Gerät, synchron erzeugt,
damit das Teilen-Menü auf dem iPhone direkt aufgeht), Dexie/IndexedDB mit Tabellen und Indizes
(Einträge werden pro Projekt geladen, Projektstatistiken liegen am Projekt; Fallback localStorage),
vite-plugin-pwa (Service Worker, Offline, Manifest). Ausgelegt auf hunderte Projekte und viele Jahre.
Stempel-Zeichenlogik in `src/lib/stempel.js` (aus dem AutoSchnell-Projekt übernommen, um Stempelfarbe und
transparenten Hintergrund ergänzt), Unterschriftsfeld `src/components/SignaturePad.jsx`, Editor `StempelDialog.jsx`.
Logos werden im Browser auf max. 800×400 px verkleinert und als PNG gespeichert
(SVG wird dafür gerastert).
