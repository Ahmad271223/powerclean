# Betrieb: Sicherung, Wiederherstellung, Geheimnisse

Stand 23.10.2026. Gilt für den Container-Betrieb aus dem README (ein App-Container + MongoDB).

## 1. Was gesichert werden muss

| Was | Wo | Wie |
|---|---|---|
| Datenbank (alle Firmen, Zeiten, Rechnungen, Unterschriften, Protokoll) | MongoDB `stundenzettel_pro` | `mongodump` |
| Dateien (Fotos, Dokumente, Angebotsanhänge) | Ordner `DATA_DIR/dateien/` (Standard `backend/daten/dateien`, im Container das gemountete Volume) | Ordner kopieren |
| Geheimnisse | `.env` (`JWT_SECRET`, `DATEN_SCHLUESSEL`, `ADMIN_TOKEN`) | getrennt und verschlüsselt aufbewahren – ohne `DATEN_SCHLUESSEL` sind Lohndaten (Steuer-ID, SV-Nummer, IBAN) nicht lesbar |

Datenbank und Dateien gehören zusammen: Dokumente in der Datenbank zeigen auf Dateien im Ordner. Beide immer aus demselben Zeitfenster sichern.

Zusätzlich aus der Oberfläche (Inhaber, „Exporte & Abschluss“): `sicherung.json` (alle Sammlungen, ohne Passwörter/Schlüssel) und
`dateien.zip` (alle Fotos und Dokumente). Beide enthalten Personaldaten: nur verschlüsselt ablegen, Zugriff beschränken; jeder Export
steht im Sicherheitsprotokoll.

## 2. Sicherung

Täglich (z. B. 02:00 Uhr per cron), Aufbewahrung 30 Tage, zusätzlich eine monatliche Kopie außer Haus:

```bash
./backup.sh /pfad/zum/sicherungsordner
```

Das Skript legt `stundenzettel-pro-JJJJ-MM-TT-HHMM.tar.gz` an (Datenbank-Dump + Dateien) und löscht Sicherungen, die älter als 30 Tage sind.
Ohne Docker: `mongodump --uri "$MONGO_URL" --db stundenzettel_pro --archive=db.archive --gzip` und den Ordner `dateien/` packen.

## 3. Wiederherstellung (mindestens vierteljährlich üben)

1. Neue leere Umgebung (zweiter Container oder Testserver) mit derselben `.env`.
2. Datenbank: `mongorestore --uri "$MONGO_URL" --archive=db.archive --gzip --drop`
3. Dateien: Archiv nach `DATA_DIR/dateien/` entpacken.
4. App starten, als Inhaber anmelden, prüfen: Projekte, letzte Zeiten, eine Rechnungs-PDF, ein Foto, Lohndaten eines Mitarbeiters (Entschlüsselung).
5. Ergebnis mit Datum im Betriebstagebuch festhalten.

Eine Sicherung, die nie zurückgespielt wurde, gilt als nicht vorhanden.

## 4. Geheimnisse und Startprüfung

Der Server startet im Betrieb (`DB_MODE` ≠ `memory`) nicht mehr mit Entwicklungswerten:

- `JWT_SECRET` muss gesetzt und mindestens 32 Zeichen lang sein, sonst bricht der Start ab (`UNSICHER_ERLAUBEN=1` übergeht das bewusst, nur für Notfälle).
- `DATEN_SCHLUESSEL` (Fernet) sollte gesetzt sein; fehlt er, wird gewarnt und ein aus `JWT_SECRET` abgeleiteter Schlüssel verwendet. Wird `JWT_SECRET` später geändert, sind dann die Lohndaten nicht mehr lesbar – deshalb `DATEN_SCHLUESSEL` eigenständig setzen und sichern.
- `ADMIN_TOKEN` leer = Betreiber-Route `/api/admin/plan` abgeschaltet.

Erzeugen: `python -c "import secrets; print(secrets.token_urlsafe(48))"` bzw. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

## 4b. Schnittstellen

- API-Schlüssel haben Rechte und ein Ablaufdatum (Standard 365 Tage); nur so viele Rechte wie nötig vergeben, abgelaufene Schlüssel
  werden mit 401 abgewiesen, gesperrte Firmen mit 403. Schlüssel aus früheren Versionen ohne Rechteliste haben Vollzugriff – bitte erneuern.
- Webhooks: nur öffentliche https-Ziele auf den Ports 80/443/8443 (`WEBHOOK_PORTS`), interne Netze sind gesperrt (SSRF-Schutz); `http`
  nur mit `WEBHOOK_HTTP_ERLAUBEN=1` für Tests. Lieferungen werden im Ausgang gespeichert und bei Fehlern wiederholt; Stand je Webhook
  in der Oberfläche (offen / fehlgeschlagen). Der Hintergrunddienst läuft im Betrieb automatisch (`WEBHOOK_DIENST=1` erzwingt ihn im Speichermodus).

## 4c. Abrechnung (bis ein Zahlungsdienst angebunden ist)

- Monatlich `GET /api/admin/abos` (Kopfzeile `X-Admin-Token`) abrufen: je Firma Firmenabo (4,99 € + 3,99 € je weiterem Nutzer), aktive
  GU-Projekte (50,99 € je Projekt) und Monatssumme; daraus die Rechnung des Anbieters stellen.
- Freischalten/Umstellen: `POST /api/admin/plan` mit `status: aktiv`, `stufe: firma` (Firmenabo) oder `stufe: teilnahme`, optional `gueltig_bis`.
- Nach der Testphase fällt eine Firma automatisch auf die kostenlose Projektteilnahme zurück (`TEILNAHME_KOSTENLOS=0` stellt die frühere
  Vollsperre wieder her).

## 4d. E-Mail-Versand (SMTP)

- In der `.env`: `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORT`, `SMTP_ABSENDER` (z. B. noreply@…), `SMTP_ABSENDER_NAME`,
  `SMTP_TLS` (starttls | ssl | none). Ohne `SMTP_HOST`/`SMTP_ABSENDER` werden E-Mails nur gespeichert (Status `nicht_konfiguriert`);
  der Server meldet das beim Start als Warnung.
- Zustellung mit Wiederholungen (1, 5, 15, 60, 240 Minuten) über den Hintergrunddienst; Stand je Firma unter Protokoll → E-Mail-Nachweise
  oder `GET /api/firma/emails`. Endgültig fehlgeschlagene E-Mails (`fehlgeschlagen`) in der Datenbank `email_ausgang` prüfen (SPF/DKIM der
  Absenderdomain einrichten, sonst landen Einladungen im Spam).
- Keine Massenmails: nur Einladungen, Einreichungsnachweise, Zuschlag/Absage, Auftragsannahme, Nachträge, Abnahmen.

## 4e. Firmen prüfen, Projektarchive, Mahnlauf

- Verifizierung: `POST /api/admin/verifizieren` mit `X-Admin-Token` und `{"email": "<Inhaber>", "verifiziert": true, "hinweis": "HRB … geprüft"}`
  (oder `firma_id`). Vorher Handelsregister/Gewerbeanmeldung und Ansprechpartner prüfen; `verifiziert: false` entzieht das Kennzeichen.
- Projektarchive liegen unter `DATA_DIR/projektakten/<firma_id>/` und gehören in die Sicherung (`backup.sh` sichert `DATA_DIR`).
  Aufbewahrung `AUFBEWAHRUNG_JAHRE` (Standard 10); Löschen vor Ablauf nur durch den Inhaber mit `erzwingen=true` (Protokoll).
- Mahnlauf ohne Zahlungsdienst: 1. Rechnung aus `/api/admin/abos`; 2. nach 14 Tagen `POST /api/admin/plan` mit `hinweis` („Rechnung … offen“);
  3. nach 30 Tagen `status: gesperrt` (Lesen und Export bleiben); nach Zahlung wieder `status: aktiv`.

## 4f. Einsatz-Erinnerungen (Plantafel)

- Der Dienst (`erinnerungen.py`) läuft im Server mit echter MongoDB automatisch; im Speicher-Modus nur mit `EINSATZ_DIENST=1`.
  Er prüft jede Minute, ob für eine Firma die Erinnerungszeit (Firma → Benachrichtigungen, Standard 18:00 Uhr) erreicht ist, und legt je
  Einsatz des Folgetags genau eine Benachrichtigung (und bei eingeschalteter E-Mail eine Nachricht im `email_ausgang`) an.
- Doppelte Erinnerungen verhindert die eindeutige `id` in `erinnerungen` (`einsatz-erinnerung-<einsatz>-v<version>`); nach einem Neustart
  wird nichts erneut verschickt. Verschobene Einsätze (neue Version) erzeugen eine neue Erinnerung – gewollt.
- Prüfung im Betrieb: `db.erinnerungen.find().sort({at:-1}).limit(5)` und `db.email_ausgang.find({art:"einsatz_erinnerung"})`.

## 4g. Kundenangebote

- Gesendete Angebote liegen als PDF-Snapshot unter `DATA_DIR/angebote/<firma_id>/<angebot>_v<version>.pdf`, E-Mail-Anhänge unter
  `DATA_DIR/email_anhaenge/<email_id>/`; beides gehört in die Sicherung (`backup.sh` sichert `DATA_DIR`). Fehlt ein Snapshot, erzeugt der Server das PDF
  aus den gespeicherten Daten neu.
- Der Antwortlink (`BASE_URL/#/angebot/<token>`) braucht keine Anmeldung; `BASE_URL` muss auf die öffentliche Adresse der Oberfläche zeigen.
  Der Token ist 32 Zeichen lang und zufällig; abgelaufene Angebote lassen sich darüber nicht mehr annehmen.
- Nummernkreis `firmen.angebotszaehler.{jahr}` zählt nie zurück (gelöschte Entwürfe hinterlassen Lücken – gewollt, wie bei Rechnungen).

## 4h. Eingangsrechnungen und Nachkalkulation

- Belege der Eingangsrechnungen liegen wie alle Dokumente unter `DATA_DIR` (Sammlung `documents`, scope `eingangsrechnung`) und gehören in die Sicherung.
- Die Nachkalkulation rechnet bei jedem Aufruf neu (keine gespeicherten Zwischenstände); die Übersicht `/api/nachkalkulation` und die Startseiten-Kachel
  gehen über alle aktiven Projekte mit Auftragswert – bei sehr vielen Projekten lohnt ein Zwischenspeicher (offen).
- Kostenmodell je Firma unter Firma → Angebote → Kalkulationssätze: interner Stundensatz (Rückfall), Lohnnebenkosten in Prozent (Aufschlag auf Stundenlohn
  oder Monatsgehalt aus den Lohndaten). Ohne Lohndaten und ohne Firmensatz werden Stunden als „ohne Lohnsatz“ ausgewiesen, nie geraten.

## 4i. Rechnungsprozesse und Mahnwesen

- Mahn-PDFs liegen unter `DATA_DIR/mahnungen/<firma_id>/<rechnung>_m<stufe>.pdf`, E-Mail-Anhänge unter `DATA_DIR/email_anhaenge/`; beides sichern.
- Nichts mahnt automatisch: die Startseite zeigt fällige Mahnschritte, das Büro löst jede Stufe aus. Fristen/Gebühren/Texte unter Mahnwesen → Regeln
  (`firmen.mahnwesen`); Gebühren nur, wenn AGB oder Gesetz sie erlauben.
- Nummernkreis: Abschläge, Schluss-, Storno- und Gutschriftsbelege zählen im selben Kreis wie Monatsrechnungen (RE-JJJJ-0001 …); ausgestellte Belege
  werden nie gelöscht oder nachberechnet – Korrekturen laufen über Storno und neuen Beleg.
- Bestehende MongoDB-Installationen: der neue Index `invoices.mahnwesen` wird beim Start angelegt; der alte eindeutige Index bleibt gültig, weil
  Nicht-Monatsrechnungen `month = -seq` tragen.

## 4j. Aufmaß und Importe

- Aufmaß-Fotos sind Dokumente (scope `aufmass`) unter `DATA_DIR`; Aufmaßblätter werden bei Bedarf erzeugt (kein Snapshot).
- Importe laufen synchron mit Vorschau; Dateigrenzen: Positionen 20 MB/1000 Positionen, Artikel 10 MB. Excel braucht `openpyxl` (requirements.txt).
- GAEB: Dateien von Auftraggebern, die der Import ablehnt, bitte aufbewahren und als Beispiel für die Erweiterung einreichen (Meldung nennt den Grund).

## 4k. Nachrichten, Projektakten im Hintergrund, Module

- Feature-Flags über die Umgebung: `FEATURE_CHAT`, `FEATURE_BERICHTSVORLAGEN`, `FEATURE_PROJEKTAKTE_ASYNC`, `FEATURE_KI`, `FEATURE_LAGER` (`1|0`). Ohne Angabe gelten die
  Standardwerte aus `features.py` (Chat und Vorlagen an, Hintergrund-Projektakten mit Datenbank an, KI und Lager aus). Stand: `GET /api/features` oder „Firma → Module“.
- Der Nachrichten-Dienst (`nachrichten.dienst`) läuft im Serverprozess und prüft jede Minute; E-Mails erscheinen im E-Mail-Ausgang (art „Neue Nachricht“). Bei mehreren
  Serverprozessen nur einen mit Diensten starten (siehe 4b) – sonst doppelte Ankündigungen.
- Chat-Anhänge liegen wie alle Dokumente unter `DATA_DIR/dateien/<firma>` (scope `chat`) und zählen zum Speicherkontingent der hochladenden Firma.
- Projektakten im Hintergrund: Status `laeuft` bleibt nach einem Serverneustart stehen – die Akte dann einfach neu erstellen (Datensatz kann der Inhaber löschen).
  Prüfsummen: `manifest.json` in der ZIP; Nachweis mit `sha256sum` gegen die entpackten Dateien.

## 4l. KI-Entwürfe (optional)

- Einschalten: `FEATURE_KI=1`, `ANTHROPIC_API_KEY=…` (nur in der `.env`, nie im Repo), optional `KI_MODELL` (Standard claude-opus-5-5), `pip install anthropic`.
  Stand prüfen: `GET /api/ki/status` (zeigt nie den Schlüssel). Kosten entstehen je Anfrage beim Anbieter; Länge der Eingabe ist auf 20 000 Zeichen begrenzt.
- Datenschutz: Der eingegebene Text wird an den Anbieter übertragen – Vertrag zur Auftragsverarbeitung abschließen, Nutzer anweisen, keine Personaldaten einzugeben.
  Das Protokoll speichert nur Längen, Modell und Dauer.

## 5. Mehrbenutzer- und Lastprobe vor dem Go-live

- Vier Testkonten (Inhaber, Büro, Vorarbeiter, Mitarbeiter) in einer Testfirma, Abnahmeliste in `GO-LIVE.md` durchgehen.
- Zwei Geräte gleichzeitig mit demselben Mitarbeiter: einstempeln auf Gerät A, Anzeige auf Gerät B prüfen, ausstempeln auf B.
- Backend-Neustart während laufender Stempelung (`docker compose restart app`): die Uhr muss danach weiterlaufen (Start liegt in der Datenbank).
- Lasttest: `tests/` laufen ohne Datenbank; ein einfacher Lasttest gegen die Testinstanz (z. B. 50 parallele `GET /api/stempel/status`) mit `hey` oder `ab` vor der Freigabe.
