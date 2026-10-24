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

## Preise und Lizenzmodell (Stand 23.10.2026, `backend/preise.py`)

Zwei Kundentypen, eine Plattform:

| Wer | Was | Preis (netto, je Monat) |
|---|---|---|
| Auftraggeber (GU, Bauherr) | je **aktivem GU-Projekt** – beliebig viele Gewerke, Ausschreibungen, Projektleiter, beteiligte Firmen; Entwürfe kostenlos; Aktivierung mit der ersten Veröffentlichung oder Einladung, Beenden durch den Inhaber | **50,99 €** |
| Ausführender Betrieb | **Firmenabo** – Mitarbeiter, Stempeluhr, Stundenzettel, Rechnungen/E-Rechnung, Lohnvorbereitung, eigene Projekte, Schnittstellen | **4,99 €** je Firma + **3,99 €** je weiterem Nutzer |
| Eingeladener Betrieb | **kostenlose Projektteilnahme** – Ausschreibungen finden, Angebote abgeben, Rückfragen, Mitarbeit in GU-Projekten (Aufgaben, Fotos, Zeiten, Berichte) | 0 € |

Im Code erzwungen: nur Auftraggeber-Konten (`firmen.art` = auftraggeber/beides) schreiben formal aus; nach der Testphase (14 Tage) fällt eine
Firma auf die kostenlose Projektteilnahme zurück (`plan.stufe` = teilnahme) – Mitarbeiter einladen, eigene Projekte, Zeiten und Stempeluhr auf
eigenen Projekten, Rechnungen, Lohn und Schnittstellen antworten dann mit 402 und Preis; verknüpfte GU-Projekte, Ausschreibungen und Angebote laufen weiter. Freischalten: `POST /api/admin/plan` mit `stufe: firma`;
Abrechnungsgrundlage für den Anbieter: `GET /api/admin/abos` (Firmenabos, aktive GU-Projekte, Monatssumme). Zahlungsdienst (Karte/Lastschrift)
ist noch nicht angebunden; Enterprise-Verträge für sehr große Projekte gesondert.

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

Lizenz: `firmen.plan` = test (14 Tage) | aktiv | gesperrt, Stufe firma (Firmenabo) | teilnahme (kostenlos). Nach der Testphase ohne Firmenabo: Lesen, Exportieren,
Ausschreibungen, Angebote und verknüpfte GU-Projekte gehen weiter, Firmenfunktionen geben 402 (siehe „Preise und Lizenzmodell“).

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

## Fotos am Arbeitstag und in der PDF

Fotos (Vorher/Nachher, Schäden, Leistungsnachweis) hängen am Arbeitstag: Im Projektkalender zeigt der Tag ein Kamera-Zeichen
mit Anzahl, Antippen öffnet den Tag mit Zeiten und Fotos; dort lassen sich Fotos aufnehmen oder hochladen (Datum des Tages,
optionale Notiz), eigene Fotos löschen, Büro alle. In der Projektakte wird beim Hochladen der Arbeitstag mitgegeben.
Vor jedem Wochen-, Monats- oder Rechnungs-PDF fragt die App, ob Fotos mit sollen: alle sind vorausgewählt, einzelne lassen
sich abwählen. Die gewählten Fotos kommen als Anhang „Fotodokumentation“ ans Ende (Datum, Uhrzeit, Name, Notiz, sechs je Seite).
Technik: `GET /api/dokumente/{id}/bild?max=…` liefert ein verkleinertes JPEG (EXIF-Drehung, HEIC mit `pillow-heif`),
`GET /api/projekte/{id}/monat` und `GET /api/rechnungen/{id}/daten` enthalten `fotos`, `PUT /api/dokumente/{id}` ändert Tag und Notiz.

## Baustellenplattform: mehrere Firmen an einem Projekt (Branch `plattform`)

Ein Auftraggeber (z. B. Generalunternehmer) führt das Projekt, lädt Subunternehmer über das Firmenverzeichnis oder per E-Mail-Link ein,
trägt mehrere Projektleiter ein und plant Aufgaben je Tag und Firma. Die Partnerfirma nimmt an, bekommt ein verknüpftes eigenes
Projekt (Stempeluhr, Stundenzettel, Rechnung an den Auftraggeber wie gewohnt), teilt Aufgaben ihren Leuten zu, meldet Status und Fotos
und gibt Wochen-Nachweise ausdrücklich frei. Lohndaten, Konten, Personalakten und Rechnungen bleiben immer in der eigenen Firma.
Firmenarten: Auftraggeber (GU/Bauherr) und ausführende Betriebe sind getrennte Kontoarten mit eigenem Menü, eigener Startseite und eigener
Ausschreibungsansicht (Registrierung oder Firma → Firmendaten; „beides“ möglich). Dazu Baustellenalltag (Phase 5): Lieferungen je Tag (zuständige Firma bestätigt, meldet Verspätung und Eintreffen, Lieferschein-Foto),
Mängel mit Firma, Frist, Priorität, Kommentaren und Fotos (Behebung melden, Abnahme nur durch die Leitung), Bautagesberichte mit
Vorbelegung aus Aufgaben/Lieferungen/Anwesenheit, Einreichen, Freigabe und PDF, Meilensteine, geteilte Projektdokumente mit Freigabe
für alle Firmen, Plattform-Kalender (Markierungen in den Tageszellen, Liste im Tagesdialog).
Oberfläche: „Zusammenarbeit“ (Büro), Projekt-Reiter Firmen / Aufgaben / Lieferungen / Mängel / Berichte / Dokumente / Anwesenheit / Nachweise
bzw. Freigaben, Seite „Aufgaben“ für alle.
Architektur, Rechtemodell, Datenmodell, Migration und offene Punkte: **`PLATTFORM.md`**.

## Ausschreibungen, Angebote und Vergabe (Branch `ausschreibungen`)

Auftraggeber legen je Gewerk Ausschreibungen im Projekt an (Beschreibung, Termine, Anforderungen, Kaufmännisches, Leistungsverzeichnis mit
Positionen, Unterlagen), speichern sie als Entwurf und veröffentlichen sie plattformweit, nur für eingeladene Firmen oder beides. Registrierte
Firmen finden passende Ausschreibungen unter „Ausschreibungen → Entdecken“ (Filter Gewerk, Ort, Abrechnungsart, Frist), werden nach Gewerk und
Region benachrichtigt, stellen Rückfragen und geben Angebote ab (Pauschal, Einzelpreise je Position mit automatischen Summen oder Stunden, mit
Anhängen, Versionen, Rücknahme). Die Projektleitung vergleicht (Preis, Termin, Vollständigkeit, Bewertung 0–5 je Kriterium), stellt Rückfragen
oder lehnt ab und schlägt eine Vergabe vor: interne Freigabe (Vier-Augen-Prinzip), Mitteilung mit Vertragsdokumenten, verbindliche Annahme
nur durch den Inhaber der Firma mit Bestätigungssatz. Erst dann wird die Firma automatisch beteiligt und bekommt ihr verknüpftes Projekt
(Mitarbeiter, Aufgaben, Zeiten, Fotos, Berichte, Stundenzettel, Rechnung – alles wie bisher). Bieter sehen nie Angebote anderer Firmen;
Entwürfe und interne Vermerke bleiben vertraulich; Fristen werden serverseitig geprüft. Projekte tragen optional Bauvorhaben-Daten;
Dokumente haben Ordner und Versionen; Speicher- und Upload-Grenzen je Firma. Details: **`PLATTFORM.md`, Abschnitt 8**.

## E-Rechnung (XRechnung / ZUGFeRD)

Jede Rechnung lässt sich unter Rechnungen → „E-Rechnung“ als **XRechnung 3.0** (reines XML, Pflicht bei Bund, Ländern,
Kommunen) oder als **ZUGFeRD 2.x / Factur-X, Profil EN 16931** (PDF/A-3 mit eingebetteter `factur-x.xml`, für Firmenkunden)
herunterladen. Vorher zeigt die App in Klartext, was noch fehlt (Leitweg-ID des Kunden, IBAN, Anschrift, E-Mail …).
Pflicht zur Ausstellung: ab 2027 bei über 800.000 € Vorjahresumsatz, ab 2028 für alle (Kleinbeträge bis 250 € ausgenommen).
Technik: `backend/erechnung.py` (UN/CEFACT-CII-XML, Prüfung, serverseitiges Rechnungs-PDF mit eingebetteter Schrift),
`backend/pdfbasis.py` (PDF/A-3 mit XMP, Factur-X-Erweiterungsschema, sRGB-OutputIntent). § 13b-Rechnungen tragen Kategorie AE
(VATEX-EU-AE), Kleinunternehmer Kategorie E. Die XML wird in den Tests gegen das EN-16931-Schema geprüft.
Kundendaten dafür: Leitweg-ID, Kundennummer, USt-IdNr., Land (Kunde bearbeiten → E-Rechnung).

## Lohnvorbereitung für Steuerberater / DATEV (keine Lohnabrechnung)

Die App rechnet bewusst keinen Lohn (Steuer- und SV-Regeln ändern sich jährlich). Sie stellt alles zusammen, was das Lohnbüro
braucht, unter Exporte → Lohnvorbereitung: je Mitarbeiter und Monat Stunden gesamt, Nacht (20–6 Uhr), Sonntag, Feiertag,
Überstunden (Saldo), Urlaubs-, Krank- und sonstige Tage, Resturlaub – als CSV, als **LODAS-Importdatei** (Lohnarten-Nummern und
Berater-/Mandantennummer unter „DATEV-Einstellungen“, vom Steuerberater vorgegeben), als PDF zum Abzeichnen und einmalig als
Stammdaten-CSV. Personal-, Steuer- und SV-Daten pflegt das Büro unter Mitarbeiter → Lohndaten; Steuer-ID, SV-Nummer und IBAN
liegen verschlüsselt (`DATEN_SCHLUESSEL` in der `.env`, erzeugen mit
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), jeder Zugriff und Export steht im Protokoll.

## Play Store und App Store

Native Hülle mit Capacitor 8 in `frontend/android` und `frontend/ios`, Workflow `.github/workflows/stundenzettel-pro-mobile.yml`
baut signierte Store-Pakete (Android AAB, iOS IPA/TestFlight) ohne eigenen Mac. Kontolöschung, Datenschutz-/Impressumsseite,
Berechtigungstexte, Deep Links und Icons sind eingebaut. Schritt-für-Schritt-Anleitung, Store-Texte und Secrets: **`STORE.md`**.
Lokal: `npm run cap:sync` (baut mit `.env.app`), `npm run assets`, `npm run cap:android`.

## Tests

`cd stundenzettel-pro/backend && python -m pytest -q` – 59 Tests ohne Datenbank (mongomock): Grundlagen
(`test_pro_grundlagen_20261022.py`), Pro Plus (`test_pro_plus_20261022.py`: Feiertage, Konten, ArbZG, Sperren,
Leistungen/Zusatzpositionen, Budget/Auswertung, Webhooks, Vorarbeiter, Stempelung beenden, Lohnsummen), E-Rechnung und
Lohnvorbereitung (`test_erechnung_lohn_20261023.py`), Fotos (`test_fotos_20261023.py`), Plattform (`test_plattform_20261023.py`)
Baustellenalltag (`test_baustelle_20261023.py`), Ausschreibungen/Vergabe (`test_ausschreibung_20261023.py`, Beispielablauf GOLDBECK),
Go-live-Befunde (`test_golive_20261023.py`, `test_audit4_20261023.py`) und Berechtigungs-Negativtests (`test_rechte_20261023.py`).

## Bauabwicklung, Projektakte und Mitteilungen (23.10.2026)

- **Nachträge und Abnahmen** im Projekt unter „Nachträge & Abnahmen“: die beauftragte Firma reicht zusätzliche Leistungen mit Preis ein, die
  Projektleitung des Auftraggebers gibt frei oder lehnt begründet ab (Auftragswert ändert sich erst mit der Freigabe); Abnahmeprotokolle
  mit Ergebnis, Vorbehalten und offenen Mängeln, von der Firma bestätigt oder widersprochen. Beides als PDF.
- **Vollständige Projektakte (ZIP)** für jede Firma: Projekt → Akte → „Projektakte erstellen“; alle Archive unter Exporte → Projektarchive
  (Aufbewahrung 10 Jahre). Zeiten mit Stundennachweisen, Fotos nach Mitarbeiter und Tag, Dokumente, Rechnungen, Unterschriften, Angebote
  und Aufträge, Nachträge, Abnahmen, Bautagesberichte, Protokoll und E-Mail-Nachweise.
- **E-Mails mit Nachweis**: Einladungen, Einreichungsnachweise, Zuschlag/Absage, Nachträge, Abnahmen (SMTP in der `.env`, siehe BETRIEB.md);
  jede E-Mail steht unter Protokoll → E-Mail-Nachweise.
- **Drei Oberflächen, eine Plattform**: Handwerksbetrieb (Übersicht, Projekte, Stempeluhr, Rechnungen + Mehr), Auftraggeber (Startseite,
  Bauprojekte, Ausschreibungen, Mitteilungen, Aufgaben & Abnahmen, Projektleiter & Rechte, Projektabos, Archiv & Berichte) und Mitarbeiter
  (Stempeluhr mit „Mein Tag“, Meine Zeiten, Aufgaben, Mitteilungen). Startseiten zeigen zuerst, was zu entscheiden ist.
- **GU-Projektabo**: Kündigung zum Monatsende, bis dahin voll nutzbar; danach Lesen, Export und Projektakte. Geprüfte Firmen tragen
  ein Kennzeichen (Betreiber-Verifizierung).

## Rechte je Büro-Nutzer und Plantafel (24.10.2026, Branch `handwerker-plattform`)

- **Vergebbare Rechte** (`backend/auth.py`, `RECHTE`): Projekte, Personal, Lohn, Rechnungen, Plantafel, Kalkulation, Kostensätze. Der Inhaber
  hat alles; ein Büro-Konto bekommt beim Anlegen die Standardrechte (alles außer Kalkulation und Kostensätze) und der Inhaber kann einzelne
  Rechte entziehen oder vergeben (Mitarbeiter → Büro-Konto → Reiter „Rechte“, `PUT /api/mitarbeiter/{id}` mit `rechte`). Jede Route prüft
  ihr Recht (403 mit Klartext), die Navigation blendet Punkte ohne Recht aus.
- **Fotoschutz**: Projektfotos anderer Mitarbeiter sind für Kollegen ohne Personal-Recht anonym (kein Name, kein Dateiname, keine EXIF-Daten);
  Löschen nur durch den Hochladenden oder mit Personal-Recht.
- **GU-Freischaltung**: Ausschreibungen und Vergaben setzen eine Freischaltung durch den Betreiber voraus (`freischaltungen.gu`, in der
  Testphase automatisch); die Firmenart allein reicht nicht.
- **Plantafel** (`backend/routes/einsatzplan.py`, Seite „Plantafel“, Recht `plantafel`): Mitarbeiter × Tage (Tag/Woche/2 Wochen/Monat),
  Projekte auf Mitarbeiter ziehen, Einsätze verschieben oder kopieren (Alt oder Kopiermodus), Kolonnen (Teams in einem Zug einplanen),
  Nachtschichten über Mitternacht, Konflikte (Überschneidung, Abwesenheit, Feiertag) mit Rückfrage, Absagen mit Grund und Wiederherstellen,
  Rückgängig je Einsatz, Verlauf mit Name und Zeit. Mitarbeiter sehen unter „Einsätze“ und in der Stempeluhr („Mein Tag“) nur ihre eigenen
  Einsätze mit Adresse, Navigation, Tätigkeit und Hinweis; Planänderungen für heute/morgen werden gemeldet, am Vorabend kommt eine Erinnerung
  (Uhrzeit und E-Mail je Firma unter Firma → Benachrichtigungen).
- **Arbeitszeitabgleich und Freigabe**: Plan gegen Stempelung je Einsatz (passt, weicht ab, fehlt, offen); das Büro legt die anrechenbare
  Zeit mit Begründung fest (`POST /api/einsatzplan/{id}/freigabe`), der Zeiteintrag behält die Stempelung als `original`; Lohn, Exporte und
  Projektakte rechnen mit der freigegebenen Zeit. Projekt-Stundenzettel aus freigegebenen Zeiten als PDF (`GET /api/einsatzplan/stundenzettel.pdf`).

## Kundenangebote und Kalkulation (24.10.2026, Stufe C)

- **Angebote an Kunden** (Seite „Angebote“, Recht `angebote`, API `/api/kundenangebote`): Kundenanfrage → Entwurf → gesendet → angenommen → Auftrag.
  Editor mit Titeln/Gruppen, Leistungs-, Stunden-, Material- und Pauschalpositionen, Textzeilen, Alternativ- und Eventualpositionen (ausgewiesen,
  nicht summiert), Nachlass je Position, Zuschläge und Rabatt auf die Summe, Steuerregeln (Regelsteuersatz, § 19 Kleinunternehmer, § 13b je Kunde),
  Standardtexte und Gültigkeit aus Firma → Angebote, Vorlagen, Kopien, Positionen aus den Leistungen mit Stundensatz.
- **Senden**: PDF-Snapshot wird festgeschrieben (gesendete Angebote ändern sich nie mehr), E-Mail mit PDF-Anhang und Antwortlink; alternativ „ohne
  E-Mail übergeben“. Über den Antwortlink (`/#/angebot/<token>`) sieht der Kunde das Angebot, lädt das PDF und nimmt online an oder lehnt ab –
  die Firma bekommt Mitteilung und E-Mail. Annahme lässt sich auch von Hand erfassen (schriftlich, telefonisch, unterschrieben).
- **Versionen**: Änderungen nach dem Senden nur als neue Version (gleiche Nummer, Version 2 …); die alte bleibt als Nachweis. Angenommene Angebote
  ändern sich über Nachträge, nicht über Versionen. Nummernkreis `AN-JJJJ-0001` je Firma und Jahr (Präfix einstellbar, Nummern werden nie wiederverwendet).
- **Auftrag**: aus dem angenommenen Angebot entsteht ein Kundenprojekt (oder ein bestehendes wird verknüpft) mit Auftragswert, Positionen und
  Abrechnungsart (pauschal oder nach Stunden) – Projekt → „Angebot & Auftrag“. Angebote und Auftrag liegen in der Projektakte (`06_Angebote/`).
- **Interne Kalkulation** (Recht `kalkulation`; Kostensätze der Firma nur mit `kostensaetze`): je Position Stunden × interner Stundensatz, Material-Einkauf,
  Fremdleistungen, Geräte, Transport, Sonstiges, Gemeinkosten-, Risiko- und Gewinnzuschlag → Selbstkosten, Preisvorschlag (Assistent „Preis übernehmen“),
  Gewinn, **Aufschlag** (auf die Kosten), **Marge** (am Verkaufspreis) und **Deckungsbeitrag** (Verkauf minus direkte Kosten) – ausdrücklich getrennt.
  Unvollständig kalkulierte Angebote zeigen keinen irreführenden Gewinn. Nichts davon erreicht Kunden, Mitarbeiter oder GU-Partner.

## Go-live und Betrieb

Befunde der externen Audits, Maßnahmen und Abnahmeliste: **`GO-LIVE.md`**. Sicherung, Wiederherstellung, Geheimnisse und Startprüfung: **`BETRIEB.md`** (`backup.sh`).
Im Betrieb startet der Server nur mit gesetztem `JWT_SECRET` (mindestens 32 Zeichen).

Die Audit-Fixes liegen auf den Branches `plattform` → `ausschreibungen` → `go-live-fixes` (jeweils aufeinander aufbauend). Für eine erneute
Prüfung müssen sie gepusht und nach `main` übernommen werden:

```bash
git push -u origin plattform ausschreibungen go-live-fixes
git checkout main && git merge --ff-only go-live-fixes && git push origin main
```

## Offen / nächste Schritte

- Zahlung (Stripe oder Lemon Squeezy) statt Freischaltung von Hand; Stufe Pro/Plus im Code durchsetzen.
- Web-Push für Einladungen und Erinnerungen (E-Mail gibt es; heute zusätzlich: Link kopieren und per WhatsApp schicken).
- Lexware Office / sevdesk: Rechnungsliste übergeben (Webhooks sind der erste Schritt).
- Mehrsprachige Oberfläche für Mitarbeiter (Türkisch, Polnisch, Rumänisch, Arabisch).
- KI-Texte (Beschreibungen verbessern, Rechnungstexte) über die Claude-API, sobald ein Schlüssel hinterlegt wird.
