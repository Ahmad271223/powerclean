# Betrieb: Sicherung, Wiederherstellung, Geheimnisse

Stand 23.10.2026. Gilt für den Container-Betrieb aus dem README (ein App-Container + MongoDB).

## 1. Was gesichert werden muss

| Was | Wo | Wie |
|---|---|---|
| Datenbank (alle Firmen, Zeiten, Rechnungen, Unterschriften, Protokoll) | MongoDB `stundenzettel_pro` | `mongodump` |
| Dateien (Fotos, Dokumente, Angebotsanhänge) | Ordner `DATA_DIR/dateien/` (Standard `backend/daten/dateien`, im Container das gemountete Volume) | Ordner kopieren |
| Geheimnisse | `.env` (`JWT_SECRET`, `DATEN_SCHLUESSEL`, `ADMIN_TOKEN`) | getrennt und verschlüsselt aufbewahren – ohne `DATEN_SCHLUESSEL` sind Lohndaten (Steuer-ID, SV-Nummer, IBAN) nicht lesbar |

Datenbank und Dateien gehören zusammen: Dokumente in der Datenbank zeigen auf Dateien im Ordner. Beide immer aus demselben Zeitfenster sichern.

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

## 5. Mehrbenutzer- und Lastprobe vor dem Go-live

- Vier Testkonten (Inhaber, Büro, Vorarbeiter, Mitarbeiter) in einer Testfirma, Abnahmeliste in `GO-LIVE.md` durchgehen.
- Zwei Geräte gleichzeitig mit demselben Mitarbeiter: einstempeln auf Gerät A, Anzeige auf Gerät B prüfen, ausstempeln auf B.
- Backend-Neustart während laufender Stempelung (`docker compose restart app`): die Uhr muss danach weiterlaufen (Start liegt in der Datenbank).
- Lasttest: `tests/` laufen ohne Datenbank; ein einfacher Lasttest gegen die Testinstanz (z. B. 50 parallele `GET /api/stempel/status`) mit `hey` oder `ab` vor der Freigabe.
