# Stundenzettel Pro – Server-Version (kostenpflichtig)

Die kostenlose App (`../stundenzettel-app`, GitHub Pages) bleibt unverändert: eine Person, ein Handy, keine Cloud.
**Stundenzettel Pro** ist das Produkt für Firmen mit Mitarbeitern: Logins für das Team, Stempeluhr am Handy,
Personalakte, Lohnexport, Sicherheitsprotokoll. Läuft auf einem eigenen Server (Docker), Daten liegen in Deutschland.

## Was drin ist (und was von clockin übernommen wurde)

Aus der Preisliste von clockin (Starter 3,79 €, Pro 6,64 €, Expert 9,49 € je Nutzer/Monat) wurde übernommen, was ein
Reinigungs- oder Handwerksbetrieb mit 1–30 Leuten wirklich braucht:

| clockin-Punkt | In Stundenzettel Pro | Umsetzung |
|---|---|---|
| Mobile und stationäre Zeiterfassung | ja | Stempeluhr am Handy (Start/Pause/Stop), Kalender im Büro, Serien-Einträge |
| GPS-Zeiterfassung | ja, freiwillig | Standort beim Ein-/Ausstempeln, sichtbar im Eintrag |
| DATEV-Export für Stundenlisten | als CSV | Lohnexport je Eintrag + Summen je Mitarbeiter (Personalnummer, Stunden, Urlaub, Krank); DATEV-Import über die Vorlage des Steuerberaters |
| Kalender & Abwesenheiten | ja | Urlaub/Krank beantragen, genehmigen, in Lohnsummen und Nachweis |
| Zeiterfassung für Projekte | ja | Projekte = Objekte mit Kunde, Einsatzort, festen Zeiten, zugewiesenen Mitarbeitern |
| Digitale Kundenverwaltung | ja | Kundenstamm mit Rechnungsadresse und § 13b-Kennzeichen (Subunternehmer-Rechnung ohne USt) |
| Digitale Personalakte | ja | Kategorien wie im clockin-Screenshot (Arbeitsvertrag, Zeugnisse, Abmahnungen, Urkunden, Sozialversicherung, Steuern …), Mitarbeiter liest die eigene Akte |
| Sicherheitsprotokoll | ja | Jede Änderung mit Nutzer, Zeit, vorher/nachher bei Zeiten; CSV-Export |
| Individuelle Rollen & Berechtigungen | 3 Rollen | Inhaber, Büro, Mitarbeiter (reicht für die Zielgruppe) |
| Digitale Projektakten mit Kommentaren | ja | Notizen, Fotos/Dateien, Kunden-Unterschriften je Woche |
| Checklisten & Formulare | Checklisten | Büro legt an, Mitarbeiter hakt ab (Name + Zeit) |
| Foto-, Skizzen- & Notizfunktion | ja | Fotos vom Handy direkt in die Projektakte |
| Digitale Unterschriften | ja | Objektleiter unterschreibt die Woche auf dem Handy, landet im Stundenzettel-PDF |
| Projektexport für Kunden | ja | Stundenzettel je Woche, Monatsmappe, Rechnung (PDF) |
| clockin API | ja | Lesende REST-API mit Schlüssel (`/api/v1/…`), Doku unter `/api/docs` |
| Lexware Office / sevdesk Anbindung | später | Rechnungen entstehen hier selbst; Export der Rechnungsliste geht, Direktanbindung bei Bedarf |
| Personio, SAP, Paychex, weclapp, Sage, Business Central, DENTAplus, Single Sign-On | nein | Konzern-Werkzeuge, kein Nutzen für 1–30 Mitarbeiter |

Dazu, was clockin nicht hat: **Rechnungen** direkt aus den Zeiten (fortlaufende Nummern, bezahlt/offen/storniert),
**Arbeitszeitnachweis nach § 17 MiLoG** je Mitarbeiter als PDF, **Import** der Sicherung aus der kostenlosen App und der
**Rückweg** (Export im Format der kostenlosen App).

## Pro Plus (22./23.10.2026, Vorbild Clockodo „Pro Plus“ 11,40 €/Nutzer)

| Clockodo-Punkt | Umsetzung |
|---|---|
| Bearbeitungssperre | Mitarbeiter ändern eigene Einträge nur N Tage zurück (Firma, Standard 7 = MiLoG-Frist); **Monatsabschluss** sperrt den Monat für alle (Exporte & Abschluss); bezahlte Rechnung sperrt den Projektmonat |
| Arbeitszeitvorschriften | `arbzg.py`: Hinweise (keine Sperre) bei > 10 h/Tag, Pause zu kurz (30/45 Min.), Ruhezeit < 11 h, Sonntagsarbeit; am Eintrag gespeichert (`warnungen`), Übersicht zählt Tage, Liste unter `GET /api/zeiten/warnungen` |
| Pausenabzug | Firma-Schalter `auto_pause`: gesetzliche Pause wird abgezogen, wenn weniger eingetragen (auch Stempeluhr), Eintrag trägt `pause_auto` |
| Sollstunden, Stundenkonten, Überstunden | `konten.py`: Soll aus Wochenstunden × Arbeitstagen abzüglich Feiertage und bezahlter Abwesenheiten; Monatsverlauf mit kumuliertem Saldo, Startsaldo/Kontostart je Mitarbeiter, Buchungen (Auszahlung, Freizeitausgleich, Korrektur); Büro-Übersicht aller Konten (Auswertung → Stundenkonten), Mitarbeiter sieht sein Konto im Profil |
| Urlaubskontingente, Feiertage, Urlaubskalender | Anspruch + Übertrag − genommen − geplant = Rest (Arbeitstage); `feiertage.py` je Bundesland (Firma), Feiertage im Kalender, in Serien übersprungen, im MiLoG-Nachweis; **Teamkalender** unter Abwesenheiten |
| Leistungen, Stundensätze | `services`: Leistung mit eigenem Satz (0 = Projektsatz), Auswahl beim Eintragen/Ausstempeln, Satz als Schnappschuss am Eintrag; Rechnung mit Positionen je Woche **und Leistung** |
| Pauschalen Material/Fahrtkosten | Zusatzpositionen an der offenen Rechnung (`PUT /api/rechnungen/{id}/extras`), auf dem PDF unter den Stunden |
| Budgets, Budget-Warnungen | Projekt: Stunden je Monat + Warnschwelle; Balken im Projekt, Liste auf der Übersicht |
| Auswertung Kunden-/Projektzeiten, Berichte PDF/CSV | `GET /api/auswertung` je Kunde/Projekt/Mitarbeiter/Leistung/Monat; Seite „Auswertung“ mit CSV und PDF |
| Zeiteinträge per Sprache | Mikrofon-Knopf (Web Speech API) bei Tätigkeit und beim Ausstempeln |
| Rollen, Teamstruktur | neue Rolle **Vorarbeiter**: auf seinen Projekten alle Zeiten sehen, für Kollegen eintragen, Serien und Checklisten anlegen |
| Terminal | statt Terminal ein **QR-Code je Objekt** (Projekt → QR): scannen öffnet `/#/stempeln/<projekt>` mit vorgewähltem Objekt |
| Mobile Apps mit Offline-Funktion | Stempeluhr läuft **ohne Netz** weiter (lokale Sitzung, Warteschlange, Nachtragen bei Netz als Quelle `stempel_offline`); Anmeldung bleibt offline gültig |
| Webhooks | `webhooks` je Firma (Inhaber): Ereignisse wie zeit.eingetragen, rechnung.angelegt … per POST mit HMAC-Signatur, Test-Knopf |
| Vergessen auszustempeln | Stempelungen > 10 h werden markiert; Büro beendet sie (`POST /api/stempel/{id}/beenden`), Vermerk am Eintrag |
| KI-Texte, MCP-Server, SSO, Zeitzonen/Währung, SLA | nicht gebaut: KI-Texte und MCP brauchen laufende API-Kosten, SSO/Zeitzonen/SLA sind Konzernthemen |

## Preisvorschlag

- **Pro**: 2,99 € je Nutzer und Monat, mindestens 9,99 € je Firma (3 Nutzer inklusive).
- **Pro Plus**: 4,99 € je Nutzer und Monat, mindestens 14,99 € (alles aus der Tabelle oben).
- Jahreszahlung mit zwei Monaten geschenkt. 14 Tage Test ohne Zahlungsdaten, in der Testphase ist alles frei.
- Freischaltung zunächst von Hand (siehe Betrieb; `plan.stufe` = pro|plus), Zahlung über Stripe/Lemon Squeezy, sobald die
  ersten zehn Firmen laufen. Die Stufe wird heute noch nicht im Code erzwungen (bewusst: erst verkaufen, dann sperren).

## Aufbau

```
stundenzettel-pro/
  backend/     FastAPI + MongoDB (Motor); DB_MODE=memory für Entwicklung/Tests ohne MongoDB
    routes/    auth, firma, mitarbeiter, kunden, projekte, zeiten (+Stempeluhr, Abwesenheiten), rechnungen,
               exporte, import_free (kostenlose App), api_v1 (Schlüssel), dashboard
    tests/     pytest, läuft ohne Datenbank (mongomock)
  frontend/    Vite + React (gleicher Baukasten wie die kostenlose App), PWA, HashRouter
  Dockerfile, docker-compose.yml, .env.example
```

Datenobjekte (Firma, Projekt, Eintrag, Rechnung) tragen die englischen Feldnamen der kostenlosen App, damit
PDF-Erzeugung, Stempel und Formulare wiederverwendet werden. Jede Sammlung trägt `firma_id` (Mandantentrennung),
alle Abfragen filtern darauf.

Rollen: **inhaber** (alles) › **buero** (alles außer Lizenz, API-Schlüssel) › **mitarbeiter** (Stempeluhr, eigene
Zeiten, zugewiesene Projekte mit Akte/Checklisten/Unterschrift, eigene Abwesenheiten, eigene Akte lesen).

Lizenz: `firmen.plan` = test (14 Tage) | aktiv | gesperrt. Abgelaufen = Lesen und Exportieren geht, Schreiben gibt 402.

## Entwicklung

```bash
# Backend ohne MongoDB (Daten nur im Speicher), API + gebaute Oberfläche auf http://localhost:8010
python stundenzettel-pro/backend/dev.py

# Testdaten in die laufende Instanz (Firma, Mitarbeiterin, Kunden, Projekte, Zeiten, Rechnungen)
python stundenzettel-pro/backend/testdaten.py

# Oberfläche mit Neuladen (Proxy auf 8010)
npm --prefix stundenzettel-pro/frontend install
npm --prefix stundenzettel-pro/frontend run dev        # http://localhost:5175

# Tests
cd stundenzettel-pro/backend && python -m pytest -q
# Build der Oberfläche
npm --prefix stundenzettel-pro/frontend run build
```

Im Desktop-App-Vorschau: Konfigurationen `pro-backend` (8010) und `pro-frontend` (5175).

## Betrieb (Hetzner/VPS, ein Container + MongoDB)

1. Server mit Docker; DNS `pro.deine-domain.de` auf die IP.
2. Repo-Ordner `stundenzettel-pro` kopieren, `.env.example` nach `.env`, `JWT_SECRET`, `ADMIN_TOKEN`, `BASE_URL`, `CORS_ORIGINS` setzen.
3. `docker compose up -d --build` – App lauscht auf `127.0.0.1:8010`.
4. Reverse-Proxy mit HTTPS davor, z. B. Caddy:
   ```
   pro.deine-domain.de {
       reverse_proxy 127.0.0.1:8010
   }
   ```
5. Sicherung: `docker compose exec mongo mongodump --archive > sicherung_$(date +%F).archive` (täglich per cron) plus das
   Volume `app-dateien` (Personal-/Projektakten).

Firma freischalten (bis die Zahlung automatisch läuft):

```bash
curl -X POST https://pro.deine-domain.de/api/admin/plan -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"email":"inhaber@kunde.de","status":"aktiv","nutzer_max":5,"gueltig_bis":"2027-10-31T00:00:00+00:00"}'
curl https://pro.deine-domain.de/api/admin/firmen -H "X-Admin-Token: $ADMIN_TOKEN"
```

## Tests

`cd stundenzettel-pro/backend && python -m pytest -q` – 22 Tests ohne Datenbank (mongomock): Grundlagen
(`test_pro_grundlagen_20261022.py`) und Pro Plus (`test_pro_plus_20261022.py`: Feiertage, Konten, ArbZG, Sperren,
Leistungen/Zusatzpositionen, Budget/Auswertung, Webhooks, Vorarbeiter, Stempelung beenden, Lohnsummen).

## Offen / nächste Schritte

- Zahlung (Stripe oder Lemon Squeezy) statt Freischaltung von Hand; Stufe Pro/Plus im Code durchsetzen.
- E-Mail-Versand der Einladungen und Erinnerungen per Web-Push (heute: Link kopieren und per WhatsApp schicken).
- E-Rechnung (XRechnung-XML) zur Rechnung, Pflicht für alle B2B-Rechnungen ab 2028.
- Lexware Office / sevdesk: Rechnungsliste übergeben (Webhooks sind der erste Schritt).
- Mehrsprachige Oberfläche für Mitarbeiter (Türkisch, Polnisch, Rumänisch, Arabisch).
- KI-Texte (Beschreibungen verbessern, Rechnungstexte) über die Claude-API, sobald ein Schlüssel hinterlegt wird.
