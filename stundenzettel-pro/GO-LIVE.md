# Go-live-Prüfung Stundenzettel Pro – Befunde, Nachweise, offene Punkte

Stand 23.10.2026, Branch `go-live-fixes`. Grundlage: die beiden externen Audit-Runden (Quellcodeanalyse). Jeder Befund wurde zuerst
im Code nachvollzogen; „bestätigt“ heißt: der beschriebene Fehlerpfad war vorhanden. Für jeden behobenen Punkt gibt es einen
Reproduktionstest in `backend/tests/test_golive_20261023.py` (läuft ohne Datenbank), Rechte in `test_rechte_20261023.py`.

## 1. Befunde und Stand

| Nr | Bereich | Befund | Geprüft | Maßnahme | Nachweis |
|---|---|---|---|---|---|
| 1 | Stempelung > 24 h (P0) | Stempelung wurde gelöscht, bevor die Dauer geprüft wurde; der Eintrag ging verloren | bestätigt | Reihenfolge umgedreht: Eintrag zuerst speichern, dann Stempelung entfernen. Über 24 h wird nichts mehr verworfen: Eintrag auf 24 h begrenzt, `pruefen`-Markierung mit Hinweis, echte Zeitstempel bleiben am Eintrag | `test_01` |
| 2 | Offline-Warteschlange (P0) | Vom Server abgelehnte Offline-Einträge wurden still verworfen | bestätigt (`err.status === 0` war die einzige Ausnahme) | Einträge bleiben mit Fehlergrund und Versuchszähler in der Warteschlange, sichtbar mit „Erneut senden“/„Verwerfen“ (nur mit Rückfrage). Jeder Eintrag trägt eine `offline_id`; der Server legt ihn höchstens einmal an | `test_02`, StempeluhrPage |
| 3 | Timeranzeige (P1) | Anzeige = Serverminuten + Sekunden seit Abruf → springt bei Neuladen/Navigation | bestätigt | Server liefert `start_at`, Pausen, `sekunden` und `jetzt` (Server-Uhr); die Anzeige rechnet nur noch aus Zeitstempeln mit Server-Offset. Neuladen, Tabwechsel, Sperren ändern nichts | `test_01`, Browserprobe |
| 4 | Offline-Start nur im Browser (P1) | Offline gestartete Stempelung lag nur im localStorage, ohne Nutzerbezug, keine Übernahme bei Netz | bestätigt | Schlüssel je Nutzer; bei Netz wird die Stempelung mit echter Startzeit und Pausen an den Server übergeben (`start_at`, höchstens 24 h zurück, Plausibilität geprüft); läuft serverseitig weiter | `test_02` |
| 5 | Pausen sekundengenau (P1) | Anzeige mit Minutenwerten plus Sekunden | bestätigt (Anzeige) | Anzeige aus Zeitstempeln; gespeicherte Pausenminuten bleiben Minuten (Datenmodell) | `test_01` |
| 6 | Status offline = „00:00:00 / Start“ (P1) | Ohne Netz wurde ein leerer Status angezeigt | bestätigt | Letzter bekannter Server-Stand wird je Nutzer gespeichert und ohne Netz angezeigt | StempeluhrPage |
| 7 | Rechnung durch PDF (P1) | Monats-/Rechnungs-PDF legte ohne Rückfrage eine nummerierte Rechnung an | bestätigt (gewollt, aber ohne Rückfrage) | `anlegen` mit `nur_pruefen`; vor der ersten Nummer fragt die Oberfläche ausdrücklich | `test_05` |
| 8 | Geheimnisse (P0) | Entwicklungs-`JWT_SECRET` als Standard | bestätigt | Startprüfung im Betrieb: ohne echtes `JWT_SECRET` (≥ 32 Zeichen) bricht der Start ab; Warnungen für `DATEN_SCHLUESSEL`/`ADMIN_TOKEN`. Webhook-Geheimnis wird nur einmal angezeigt (war schon so); Protokoll enthält keine Lohndaten (war schon so) | `test_07`, BETRIEB.md |
| 9 | Projekt löschen (P0) | Laufende Stempelungen wurden mitgelöscht | bestätigt | Mit laufender Stempelung nie löschbar (409). Mit erfassten Zeiten nur Inhaber ausdrücklich (`?erzwingen=true`, Rückfrage in der Oberfläche), sonst archivieren | `test_03` |
| 10 | Unterschriften (P0) | Mitarbeiter konnten eine Wochenunterschrift ersetzen; alte wurde gelöscht | bestätigt | Vorhandene Unterschrift wird nie überschrieben: Mitarbeiter 409; Büro nur mit Begründung → neue Version, alte bleibt mit Grund/Zeit/Name. „Löschen“ zieht nur zurück. PDFs/Nachweise verwenden nur gültige Unterschriften | `test_04` |
| 11 | Offene Rechnungen (P1) | `anlegen` berechnete offene Rechnungen bei jedem Aufruf neu | bestätigt | Lebenszyklus Entwurf → ausgestellt (`festgeschrieben_at` beim ersten PDF/XML oder ausdrücklich): keine stille Neuberechnung, keine Positions-/Datumsänderung; Neuberechnung nur Inhaber mit Korrekturvermerk und alten Summen | `test_05` |
| 12 | Monatsabschluss (P1) | Abschluss trotz laufender Stempelungen | bestätigt | Laufende Stempelungen, die den Monat berühren, blockieren mit Namen (409); `erzwingen` möglich und protokolliert | `test_03` |
| 13 | Checklisten (P1) | Mitarbeiter konnten Punkte durch Weglassen entfernen | bestätigt | Mitarbeiter ändern nur den Erledigt-Status vorhandener Punkte | `test_06` |
| 14 | Upload-Reihenfolge (P1) | Datei wurde vor der Datumsprüfung gespeichert | bestätigt | Prüfung zuerst | `test_06` |
| 15 | Rechnungsnummern (P1) | Nach Zurücksetzen konnte eine Nummer erneut vergeben werden | bestätigt | Zähler je Firma und Jahr, der nie zurückzählt; ausgestellte Rechnungen lassen sich nicht zurücksetzen, nur stornieren | `test_05` |
| 16 | Abwesenheiten (P1) | Änderung genehmigter Anträge ohne Historie | bestätigt | Entscheidungs- und Änderungsverlauf am Antrag; Änderung entschiedener Anträge nur mit Grund | `test_06` |
| 17 | Rollen (P1) | Negativtests fehlten | offen → erledigt | Systematische Negativtests je Rolle und über Firmengrenzen | `test_rechte_20261023.py` |
| 18 | Betrieb (P1) | Backup/Restore/Mehrbenutzer ohne Nachweis | offen | Anleitung und Skript (`BETRIEB.md`, `backup.sh`); Wiederherstellungsprobe und Zwei-Geräte-Test muss vor dem Go-live auf dem echten Server durchgeführt und dokumentiert werden | manuell |
| 19 | Projekt ohne Zuweisung = alle sehen es | Standardverhalten | bestätigt, bewusst | Bleibt Standard für kleine Betriebe; für vertrauliche Projekte Mitarbeiter zuweisen oder Projektleitung eintragen (dann sehen es nur Zugewiesene). Hinweis steht im Projektdialog | – |
| 21 | Stempeluhr zeigte Projekte, auf die nicht gestempelt werden konnte | Bei der Browserprobe gefunden: Projektliste der Stempeluhr prüfte die Sichtbarkeit ohne `leiter_ids` (Plattform-Regel), das Einstempeln antwortete dann 404 | bestätigt (eigener Fehler aus Phase 4) | Sichtbarkeit überall mit vollständigen Projektdaten geprüft (Stempeluhr, Übersicht, Dokumentzugriff) | Browserprobe, `test_rechte` |
| 22 | Vorarbeiter buchen für beliebige Kollegen | Negativtest: Vorarbeiter konnten auf ihrem Projekt Zeiten für Personen eintragen, die dem Projekt nicht zugewiesen sind | bestätigt | Bei Projekten mit Zuweisung nur für zugewiesene Personen (403), Büro unverändert | `test_rechte_03` |
| 20 | Nachtarbeit / Zeitumstellung | zu testen | geprüft | Stempelung über Mitternacht liefert Datum des Starttags und korrekte Nettominuten; Zeitstempel werden mit Zeitzone gespeichert (`clock_start_at`/`clock_end_at`), Anzeige rechnet mit absoluten Zeitstempeln. Zeitumstellung: die Dauer aus absoluten Zeitstempeln ist korrekt; die HH:MM-Felder der Nacht der Umstellung sind Wanduhrzeiten (Hinweis in der Doku) | `test_01` |

## 1b. Prüfungsrunde 4 (23.10.2026) – 23 Befunde

Vorbemerkung: Der Auditor sieht auf GitHub nur `main` (f487941). Alle Fixes liegen auf den lokalen Branches `plattform` →
`ausschreibungen` → `go-live-fixes`; sie müssen gepusht und nach `main` übernommen werden, damit eine erneute Prüfung den
aktuellen Stand sieht (siehe README „Go-live und Betrieb“).

| Nr | Bereich | Befund | Geprüft | Maßnahme | Nachweis |
|---|---|---|---|---|---|
| 1 | Webhooks (P0) | SSRF: beliebige Adressen, auch interne, wurden angesprochen | bestätigt | `webhooks.url_pruefen` beim Anlegen (nur https, erlaubte Ports, keine Zugangsdaten, keine internen Namen/IP-Bereiche inkl. IPv6/IPv4-mapped/CGNAT) und `adressen_pruefen` vor jedem Senden (DNS auflösen, jede Adresse muss öffentlich sein); keine Weiterleitungen; Zeitlimit 8 s | `test_audit4_01` |
| 2 | API-Schlüssel (P1) | Ein Schlüssel las alles | bestätigt | Rechte je Schlüssel (`zeiten`, `projekte`, `kunden`, `mitarbeiter`, `abwesenheiten`, `rechnungen`), Standard nur Zeiten+Projekte; jede Route verlangt ihr Recht (403); alte Schlüssel ohne Rechteliste behalten Vollzugriff bis zur Erneuerung (in der Oberfläche markiert) | `test_audit4_02` |
| 3 | Import Rechnungsnummern (P1) | Bei Nummernkonflikt wurde nur `seq` geändert, die sichtbare Nummer blieb doppelt | bestätigt | Rechnung mit bereits vergebener Nummer oder bereits abgerechnetem Monat wird übersprungen (gezählt); Nummernkreis wird auf die höchste importierte Nummer nachgezogen; importierte Rechnungen gelten als ausgestellt | `test_audit4_03` |
| 4 | Leistungen (P1) | Umbenennen änderte den Namen auf allen alten Einträgen | bestätigt | Einträge behalten Name und Satz als Momentaufnahme; neuer Name gilt künftig | `test_audit4_04` |
| 5 | CSV (P1) | Formel-Einschleusung in Tätigkeiten/Namen | bestätigt | `csvsicher`: Zellen, die mit = + - @ oder Steuerzeichen beginnen, bekommen ein Hochkomma (Zahlen unverändert) – in allen CSV-Exporten (Zeiten, Lohn, Abwesenheiten, Protokoll, Lohnvorbereitung, LV) | `test_audit4_04` |
| 6/7 | Projektdaten (P1) | Mitarbeiter bekamen Stundensätze, Budgets, Notizen, Kundendaten | bestätigt | `projekt_fuer_nutzer`: Mitarbeiter ohne vertrauliche Felder, Projektleitung zusätzlich Stundenbudget; Monat liefert Rechnung und Leistungssätze nur dem Büro | `test_audit4_04` |
| 8/9/10 | Datensicherung (P1) | Unvollständig (keine Stundenkonten, Abschlüsse, Leistungen …), Dateien fehlen, Personaldaten ungeschützt | bestätigt | `sicherung.json` v2 mit allen Sammlungen inkl. Plattform; `dateien.zip` für Fotos/Dokumente; Hinweis auf Personaldaten in Datei und Oberfläche, Export im Protokoll; Aufbewahrung in `BETRIEB.md` | `test_audit4_05` |
| 11/12/13 | Import (P1) | Teilimport möglich, keine stabile Kennung, keine Modellprüfung | bestätigt | Erst prüfen, dann schreiben; Projekte über `ProjektIn`; Kennung je Eintrag auch ohne Quell-ID (Hash) → Wiederholung legt nichts doppelt an; bei Schreibfehlern werden alle Datensätze des Imports entfernt (500, nichts übernommen) | `test_audit4_03` |
| 14/15 | API-Schlüssel (P1) | Keine Sperr- und Ablaufprüfung | bestätigt | Gesperrte Firma → 403; `gueltig_bis` (1–730 Tage, Standard 365) → 401 nach Ablauf | `test_audit4_02` |
| 16/17 | Webhooks (P1) | Nur Hintergrundaufgabe, kein Retry, Verlust bei Neustart | bestätigt | Ausgang `webhook_ausgang`: jedes Ereignis wird gespeichert, sofort zugestellt, bei Fehlern mit 1/5/15/60/240 Minuten Abstand wiederholt (Hintergrunddienst, läuft nach Neustart weiter), danach „fehlgeschlagen“ und sichtbar | `test_audit4_01` |
| 18 | Stundensatz 0 (P1) | 0 wurde durch den Firmenstandard ersetzt | bestätigt (gewollt für „leer“) | Schalter „Kostenlos“ am Projekt: 0 € bleibt 0 € | `test_audit4_05` |
| 19 | Mitarbeiter-IDs (P1) | Unbekannte IDs wurden entfernt – leere Liste = für alle sichtbar | bestätigt | Unbekannte IDs → 400, nichts wird stillschweigend geleert | `test_audit4_05` |
| 20 | Projektlöschung (P1) | Verlust historischer Daten | schon in Runde 3 | Laufende Stempelung: nie; mit Zeiten nur Inhaber ausdrücklich; Archivieren ist der Normalfall | `test_golive_03` |
| 21/22 | Listen (P2) | Feste Grenzen ohne Hinweis | bestätigt | Rechnungen und Zeiten mit `limit`/`offset`, `hat_mehr` und `gesamt`; Oberfläche zeigt den Hinweis | `test_audit4_05` |
| 23 | Dashboard (P2) | Berechnung in einer Anfrage | zutreffend, kein Fehler | Bekannte Grenze: für sehr große Firmen vor dem Go-live Lasttest (BETRIEB.md); Indizes vorhanden | manuell |

## 1c. Lizenz- und Abrechnungsmodell (23.10.2026)

Umgesetzt und mit `tests/test_abo_20261023.py` abgedeckt: nur Auftraggeber-Konten schreiben formal aus (403 für Betriebe), GU-Projektabo
50,99 €/Monat je aktivem Projekt (Aktivierung bei Veröffentlichung oder Einladung, einmal je Projekt, Beenden durch den Inhaber, Zeiträume
bleiben erhalten), Firmenabo 4,99 € + 3,99 € je weiterem Nutzer, kostenlose Projektteilnahme nach der Testphase (Firmenfunktionen 402),
öffentliche Preisliste `GET /api/preise`, Abrechnungsgrundlage `GET /api/admin/abos`. Mitarbeiter sehen das Abo-Feld nicht.

Offen (bewusst): kein Zahlungsdienst, keine automatischen Rechnungen oder Mahnungen, kein Enterprise-Vertrag im Code; die Monatsrechnung
stellt der Anbieter von Hand aus `/api/admin/abos` (siehe `BETRIEB.md` 4c). Die Nutzeranzahl zählt aktive Konten am Abruftag, nicht tagesgenau.

## 1d. Prüfung „Plattform-Kern“ (23.10.2026)

| Befund (extern) | Geprüft | Ergebnis |
|---|---|---|
| `routes/mitarbeiter.py` löscht beim Deaktivieren laufende Stempelungen | bestätigt (`stempel.delete_many`) | behoben: `stempelungen_abschliessen` legt den Eintrag an (Vermerk „Konto deaktiviert …“, `beendet_durch`, Protokoll `stempel.stop` mit `grund`) |
| `routes/auth_routes.py` löscht bei Kontolöschung laufende Stempelungen | bestätigt | behoben: gleiche Abschluss-Funktion; die Zeit bleibt beim Arbeitgeber |
| Lizenzprüfung nur über den Firmenplan | bestätigt, bereits in Runde 1c getrennt (`firmenabo_noetig` vs. kostenlose Teilnahme) | Test `test_abo_20261023.py::test_02` |

Neu umgesetzt und getestet (`tests/test_kern_20261023.py`, 7 Tests): GU-Abo mit Kündigung zum Monatsende und erneuter Aktivierung,
E-Mail-Ausgang mit Nachweisen und Wiederholung, Nachträge mit Freigabe, Abnahmen mit Bestätigung, ZIP-Projektakte für beide Seiten
(Inhalt geprüft), Startseiten-Aufgaben, Projektleiter-Übersicht, Verifizierung, Unterauftrag-Kette.

Offen: echter SMTP-Versand auf dem Zielserver (Testmail), Projektakte bei sehr großen Projekten (Laufzeit, Speicher), Chat.

## 1e. Stufe A und B (24.10.2026, Branch `handwerker-plattform`)

| Befund (`AUDIT_20261024.md`) | Geprüft | Ergebnis |
|---|---|---|
| A1 Büro sieht Löhne, Rechnungen, Personalakten ohne Abstufung | bestätigt (alle Büro-Routen nur `rolle_noetig("buero")`) | vergebbare Rechte je Büro-Nutzer, jede Route prüft ihr Recht, Navigation blendet aus (`test_stufe_a_20261024.py::test_02`) |
| A2 Kollegen sehen Hochlader und Dateinamen fremder Projektfotos | bestätigt | `foto_fuer_nutzer`, EXIF-freie Auslieferung, Löschrecht eingeschränkt (`test_01`) |
| A3 Firmenart „Auftraggeber“ selbst wählbar → Ausschreibungen ohne Freigabe | bestätigt | `gu_freigeschaltet` (Testphase oder Betreiber-Freischaltung), 403 sonst (`test_03`) |
| A4 CSV-Import kippt bei Anführungszeichen und Dezimalkomma | bestätigt | robuster Parser (`lib/ausschreibung.js`), aus PR #8 übernommen |
| A5 Exporte-Seite meldet „Nicht gefunden“ gegen alten Server | bestätigt | Klartext „Server veraltet“ statt 404-Toast |
| A6 Angebotsart (Pauschal/Stunden) ohne Rückmeldung | bestätigt | gesperrte Preisart sichtbar, eigene Dialoge |
| A7 Keine Einsatzplanung, Lohn rechnet mit roher Stempelung | bestätigt | Plantafel mit Abgleich und Freigabe (`test_plantafel_20261024.py`, 4 Tests) |

Alle Backend-Tests grün (75, davon 7 neu für Stufe A und B); Frontend-Build grün; Browser-Prüfung Plantafel (Ziehen, Kopieren, Abgleich, Freigabe) und
„Meine Einsätze“/„Mein Tag“ am 24.10.2026.

Offen: Erinnerungsdienst auf dem Zielserver beobachten (Protokoll `erinnerungen`), SMTP-Testmail, Serien- und Schichtvorlagen.

## 1f. Stufe C – Kundenangebote und Kalkulation (24.10.2026)

| Prüfung | Ergebnis |
|---|---|
| Routenkonflikt `/api/angebote/{id}` mit den GU-Bieterangeboten | gefunden beim Testlauf (PUT lief auf die GU-Route); Kundenangebote liegen unter `/api/kundenangebote` |
| Dreifach eingefügte Blöcke aus dem Stufe-A-Patch (`auth.py` Rechte-Block, `gemeinsam.foto_fuer_nutzer`, zwei `ProjektIn`-Felder) | bereinigt, Suite unverändert grün |
| Summen und Rundung (Zuschlag, Rabatt, USt, § 19, § 13b, Alternativ/Eventual) | `test_angebote_20261024.py::test_01` |
| Senden mit PDF-Anhang und Antwortlink, Unveränderlichkeit, Versionen, Online-Annahme, Auftrag, Projektakte, Ablauf, Anfrage | `test_02` |
| Kalkulation: Aufschlag ≠ Marge, Deckungsbeitrag, Unvollständigkeit, Assistent, Vertraulichkeit | `test_03` |
| Browser (24.10.2026): Liste, Editor, Anlegen über Dialog, Position speichern, ohne E-Mail senden, Firma → Angebote, Projekt → Angebot & Auftrag, Antwortseite | ohne Konsolenfehler |

Backend-Tests gesamt: 78 grün. Offen: echter E-Mail-Versand mit Anhang über SMTP auf dem Zielserver prüfen (Anhangsgröße, Spam-Bewertung).

## 2. Abnahmetests Stempeluhr (vor dem Go-live auf dem echten Server)

Automatisiert (Backend): Zeitstempel/Server-Uhr, Pausen sekundengenau, > 24 h, Nachtarbeit, Offline-Übernahme, doppelte Übertragung, Serverfehler beim Synchronisieren, Monatsabschluss/Projektlöschung mit laufender Stempelung.
Im Browser geprüft (23.10.2026, Testinstanz): Start → Seite neu laden → Uhr läuft ohne Sprung weiter (Server-Uhr).

Manuell auf dem Zielsystem (je Gerät, Datum und Ergebnis notieren):

1. Einloggen → Start → 5 Minuten laufen lassen → Anzeige gegen eine Uhr prüfen.
2. Während laufender Stempelung zwischen allen Seiten wechseln, App schließen und öffnen.
3. Handy 30 Minuten sperren und entsperren (Anzeige muss sofort den richtigen Stand zeigen).
4. Pause starten → Seite verlassen → zurück → Pause läuft weiter → fortsetzen → Nettozeit prüfen.
5. Flugmodus während laufender Stempelung → ausstempeln → Netz an → Eintrag genau einmal vorhanden.
6. Flugmodus → einstempeln (offline) → Netz an → Uhr läuft serverseitig mit der Offline-Startzeit weiter.
7. Zwei Geräte gleichzeitig: Start auf A, Stand auf B, Stop auf B, A nach Neuladen leer.
8. Stempelung über Mitternacht und über den Monatswechsel; Abschluss des Vormonats währenddessen → Hinweis.
9. Server neu starten während laufender Stempelung → Uhr läuft weiter.
10. Nach jedem Szenario: Eintrag im Kalender, Wochen-PDF, Protokoll.

## 3. Was noch nicht nachgewiesen ist

- Wiederherstellung aus einer Sicherung auf einem frischen Server (Anleitung in `BETRIEB.md`, Probe muss durchgeführt werden).
- Lasttest mit mehreren gleichzeitigen Nutzern auf der Zielumgebung.
- Store-Builds auf echten Geräten (Android/iOS) – siehe `STORE.md`.
- E-Rechnung gegen einen externen Validator (XSD-Prüfung läuft in den Tests; KoSIT-Validator/Portalannahme steht aus).
- E-Mail-Versand: SMTP-Zugang eintragen und eine Einladung an eine echte Adresse prüfen (Protokoll → E-Mail-Nachweise zeigt den Status).
- Projektakte eines großen Projekts (viele Fotos) einmal erzeugen und die Laufzeit messen.
- Rechtliche Prüfung (AV-Vertrag, Aufbewahrung, Datenschutzerklärung) durch eine fachkundige Person.
- Abrechnung in der Praxis: Monatslauf über `/api/admin/abos`, Rechnungstellung und Zahlungseingang sind Handarbeit, bis ein Zahlungsdienst angebunden ist.

## 4. Freigabeempfehlung

Die in den Audits benannten Verlust- und Manipulationspfade (Nr. 1, 2, 9, 10, 11, 12, 15) sind geschlossen und durch Tests abgedeckt.
Freigabe für zahlende Kunden erst nach den manuellen Abnahmetests aus Abschnitt 2 auf dem Zielsystem und der Wiederherstellungsprobe aus
Abschnitt 3; bis dahin Testbetrieb mit einer Pilotfirma.
