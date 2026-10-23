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
- Rechtliche Prüfung (AV-Vertrag, Aufbewahrung, Datenschutzerklärung) durch eine fachkundige Person.

## 4. Freigabeempfehlung

Die in den Audits benannten Verlust- und Manipulationspfade (Nr. 1, 2, 9, 10, 11, 12, 15) sind geschlossen und durch Tests abgedeckt.
Freigabe für zahlende Kunden erst nach den manuellen Abnahmetests aus Abschnitt 2 auf dem Zielsystem und der Wiederherstellungsprobe aus
Abschnitt 3; bis dahin Testbetrieb mit einer Pilotfirma.
