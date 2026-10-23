# PowerCleanService

Website + Admin-Bereich (FastAPI/MongoDB Backend, React/Vite Frontend).

## Stundenzettel-App (`/stundenzettel`)

Interne App für Arbeitszeiten, Stundenzettel und Monatsrechnungen. Login mit dem Admin-Konto.

- **Meine Firma**: Beim ersten Start wird die eigene Firma eingerichtet (Logo als PNG/JPG/SVG, Name,
  Inhaber, Anschrift, Kontakt, Steuernummer/USt-IdNr., IBAN, Standard-Stundensatz, USt. oder § 19).
  Mehrere Firmen sind möglich: dann erst Firma wählen, dann Projekt. Jede Firma hat eigene Projekte,
  Einstellungen und eine eigene Rechnungsnummernfolge. Logo und Firmendaten stehen oben auf allen PDFs.
- **Meine Projekte**: Firmenseite zeigt alle Projekte als Kacheln. Jedes Projekt hat eigene Daten
  (Auftraggeber, Rechnungsadresse, Mitarbeiter, Stundensatz, Farbe) und einen eigenen Kalender.
- **Rechnungsübersicht**: alle erstellten Monatsrechnungen der Firma mit Stunden, Netto und Brutto.
- **Kalender 2025–2030**: Tag anklicken → Anfang, Arbeitsende, Pause, Tätigkeit eintragen.
  Netto-Arbeitszeit wird automatisch berechnet, mehrere Einträge pro Tag möglich.
- **Stundenzettel (PDF) pro Kalenderwoche**: Spalten Datum · Tätigkeit · Anfang · Arbeitsende ·
  Netto Arbeitszeit · Unterschrift, alle 7 Tage aufgeführt, Summe und Unterschriftenzeilen.
- **Monats-PDF**: alle Stundenzettel der Wochen des Monats + Monatsübersicht + Rechnung in einer Datei.
  Rechnungsnummern werden fortlaufend vergeben (`RE-JJJJ-0001`) und pro Projekt/Monat gespeichert.

Backend-Code: `backend/timesheets.py` (Router `/api/ts/...`, PDF-Erzeugung mit reportlab).
Frontend: `frontend/src/pages/StundenzettelPage.jsx` (Firmenauswahl/Einrichtung), `frontend/src/pages/FirmaPage.jsx`
(Projekte + Rechnungsübersicht), `frontend/src/pages/ProjektKalenderPage.jsx`,
`frontend/src/components/stundenzettel/`, Helfer in `frontend/src/lib/ts.js`.

## Stundenzettel als eigenständige App (`stundenzettel-app/`)

Offline-Version der Stundenzettel-App fürs Handy: läuft ohne Server, speichert alles auf dem Gerät,
erzeugt die PDFs lokal. Installation über „Zum Home-Bildschirm“. Details, Build und Veröffentlichung
(z. B. unter `https://www.powercleanservice.de/app/`) siehe `stundenzettel-app/README.md`.

## Stundenzettel Pro – kostenpflichtige Server-Version (`stundenzettel-pro/`)

Eigenes Produkt für Firmen mit Mitarbeitern, getrennt von der kostenlosen App: Logins und Rollen (Inhaber,
Büro, Mitarbeiter), Stempeluhr am Handy mit optionalem Standort, Projekte mit Kundenstamm und § 13b,
Serien-Einträge, Kunden-Unterschrift auf dem Handy, Projektakte (Notizen, Fotos, Checklisten), Personalakte,
Abwesenheiten, Rechnungen mit Status, Lohnexport (CSV), Arbeitszeitnachweis nach § 17 MiLoG,
Sicherheitsprotokoll, lesende API mit Schlüssel, Import aus der kostenlosen App. Pro Plus: Feiertage, Sollstunden,
Stundenkonten, Urlaubskonten, Arbeitszeitgesetz-Prüfung mit Pausenabzug, Monatsabschluss, Leistungen mit Sätzen,
Zusatzpositionen, Budgets, Auswertung, Vorarbeiter-Rolle, Objekt-QR mit Offline-Stempeln, Webhooks. FastAPI + MongoDB im Docker,
Oberfläche mit dem Baukasten der kostenlosen App. Entwicklung ohne MongoDB: `python stundenzettel-pro/backend/dev.py`
(Port 8010). Alles Weitere in `stundenzettel-pro/README.md`.

## Lokal starten

```bash
# Backend (MongoDB muss laufen, Konfiguration in backend/.env – siehe backend/.env.example)
pip install -r backend/requirements.txt
python -m uvicorn server:app --app-dir backend --port 8000 --reload
```

```bash
# Frontend (frontend/.env mit VITE_BACKEND_URL=http://localhost:8000 – siehe frontend/.env.example)
npm --prefix frontend install
npm --prefix frontend start
```

Dann `http://localhost:5173/stundenzettel` öffnen. Ein erstes Admin-Konto legt `POST /api/admin/setup` an.
