# Baustellenplattform: Zusammenarbeit mehrerer Firmen (Branches `plattform` und `ausschreibungen`)

Stand 23.10.2026. Erweiterung von Stundenzettel Pro um eine Projekt- und Unternehmensebene, auf der ein Auftraggeber
(Generalunternehmer) Projekte führt und Subunternehmer mit eigenen Firmenkonten beteiligt. Alle bisherigen Funktionen bleiben
unverändert; die Erweiterung ist rein additiv (neue Sammlungen, neue optionale Felder, neue Routen).

## 1. Bestandsanalyse (Phase 1)

| Bereich | Befund |
|---|---|
| Architektur | FastAPI + Motor/MongoDB, React/Vite, Capacitor. Jede Sammlung trägt `firma_id`; jede Abfrage filtert darauf. |
| Rollen | Feste Firmenrollen `mitarbeiter < vorarbeiter < buero < inhaber` (`auth.ROLLEN`), Prüfung über `rolle_noetig` / `schreibend` (Lizenz). |
| Authentifizierung | JWT je Nutzer; ein Nutzer gehört genau einer Firma (`users.firma_id`). Einladung per Link, PIN nur vorbereitet. |
| Firma | `firmen` (Stammdaten, Rechnungsdaten, Arbeitszeitregeln, Lizenz `plan`, DATEV-Einstellungen). |
| Projekt | `projects` gehört einer Firma; Sichtbarkeit über `employee_ids` (leer = alle), Leitung = Büro/Inhaber oder zugewiesener Vorarbeiter. |
| Zugriffskontrolle | `projekt_laden(user, id)` erzwingt `firma_id == user.firma_id`; Dokumente über `_dokument_zugriff` (Scope user/project). |
| API | Router je Modul (`routes/*.py`), ca. 130 Endpunkte; lesende Fremd-API mit Schlüssel (`api_v1`), Webhooks. |
| Tests | pytest mit `DB_MODE=memory` (mongomock), vorher 32 Tests, jetzt 42 (Plattform 3, Baustellenalltag 3, Ausschreibungen/Vergabe 4). |
| Migrationsrisiken | Keine Schemaänderung nötig. Neue Felder sind optional (`projects.leiter_ids`, `projects.verknuepft`, `firmen.verzeichnis`), neue Sammlungen leer. Indizes werden beim Start idempotent angelegt. |

## 2. Architekturentscheidung

Eigentümer, Projekt und Zugriff werden getrennt:

- **Eigentümer eines Datensatzes** bleibt die Firma (`firma_id`). Nichts wird firmenübergreifend geschrieben.
- **Projekt**: gehört genau einer Firma (Auftraggeber). Andere Firmen nehmen über eine **Beteiligung** (`beteiligungen`) teil.
- **Verknüpftes lokales Projekt**: Bei Annahme einer Einladung entsteht in der Partnerfirma ein eigenes Projekt mit
  `verknuepft = {project_id, owner_firma_id, beteiligung_id, gewerk, rolle, status}`. Darauf laufen Stempeluhr, Stundenzettel,
  Monats-PDF, Rechnung (Kunde = Auftraggeber), Lohnvorbereitung – unverändert und nur in der Partnerfirma sichtbar.
- **Zwischen den Firmen fließen nur**: Aufgaben (vom Auftraggeber), Lieferungen, Mängel, Bautagesberichte, Meilensteine und
  ausdrücklich geteilte Projektdokumente, Fotos dazu, Anwesenheitszahlen (Namen erst nach Freigabe der Partnerfirma),
  ausdrücklich freigegebene Wochen-Nachweise (Zeiten mit Namen, Kunden-Unterschrift).
- **Nie sichtbar für andere Firmen**: Personalakte, Lohndaten, Stundenkonten, Urlaub, Rechnungen, Kunden, Lizenz.

Eine Firma kann in Projekt A Auftraggeber und in Projekt B Subunternehmer sein; kein Konzern ist im Code ein Sonderfall.

## 3. Datenmodell (neu)

| Sammlung / Feld | Inhalt |
|---|---|
| `firmen.verzeichnis` | `{sichtbar, gewerke[], beschreibung, ort}` – nur diese Felder sind im Verzeichnis sichtbar. |
| `projects.leiter_ids` | Projektleiter der Eigentümerfirma (mehrere je Projekt). Mit eingetragener Leitung sehen Vorarbeiter/Mitarbeiter das Projekt nur noch, wenn sie Leitung oder zugewiesen sind. |
| `projekt_leiter` | `{project_id, firma_id, user_id, user_name, funktion, created_at}` |
| `beteiligungen` | `{project_id, owner_firma_id, firma_id, firma_name, email, gewerk, rolle, status: eingeladen/aktiv/abgelehnt/entfernt, token, token_bis, lokales_project_id, freigaben{namen}, kontakt_user_id}` |
| `aufgaben` | `{project_id, owner_firma_id, firma_id (beauftragt), titel, beschreibung, gewerk, datum, start_time, end_time, prioritaet, bereich, material, vorarbeiter_user_id, mitarbeiter_ids, status, verlauf[]}` |
| `documents` (scope `aufgabe`, `lieferung`, `mangel`, `tagesbericht`) | Fotos zum jeweiligen Eintrag, `firma_id` = hochladende Firma, Zugriff über den Eintrag (`plattform.dokument_zugang`). |
| `documents` (scope `plattform`) | Geteilte Projektdokumente (Baupläne, Aufträge, Protokolle, Sicherheit …) mit `freigabe_alle`: Eigentümer-Leitung sieht alles, Partner nur eigene und freigegebene. |
| `lieferungen` | `{project_id, owner_firma_id, firma_id (zuständig), material, menge, lieferant, geplant_am, zeitfenster_von/bis, entladeort, ansprechpartner, bemerkungen, status, tatsaechlich_am, verlauf[]}` |
| `maengel` | `{project_id, owner_firma_id, firma_id (verantwortlich, optional), beschreibung, bereich, kategorie, frist, prioritaet, status, gemeldet_von, kommentare[], verlauf[]}` |
| `tagesberichte` | `{project_id, firma_id (Verfasserfirma), datum, bereich, wetter, firmen[], mitarbeiter_anzahl, taetigkeiten, fortschritt, lieferungen, behinderungen, maengel, besondere_vorkommnisse, notizen, status, verfasser, verlauf[]}` |
| `meilensteine` | `{project_id, titel, datum, erledigt, notiz}` – nur Eigentümer-Leitung pflegt, alle Beteiligten sehen sie. |
| `freigaben` | `{project_id, beteiligung_id, firma_id, lokales_project_id, week_monday, freigegeben_von}` |
| `benachrichtigungen` | `{firma_id, user_ids|null, mindestens, art, text, link, gelesen_von[]}` |

Aufgabenstatus: geplant → zugewiesen → in_bearbeitung / blockiert → eingereicht → abgeschlossen / abgenommen. Die beauftragte Firma darf
`in_bearbeitung`, `blockiert`, `eingereicht` setzen, zugeteilte Mitarbeiter `in_bearbeitung`, `eingereicht`; abnehmen darf nur die
Projektleitung der Eigentümerfirma. Jeder Statuswechsel steht im `verlauf` und im Sicherheitsprotokoll.

Lieferungsstatus: angefragt → bestaetigt → unterwegs → eingetroffen → entladen → abgeschlossen, dazu verspaetet und storniert. Die zuständige
Firma darf bestätigen, unterwegs/eingetroffen/entladen melden und Verspätung melden; abschließen und stornieren nur die Leitung.
Mangelstatus: offen → zugewiesen → in_bearbeitung → behoben_gemeldet → in_pruefung → abgenommen, oder erneut_geoeffnet (zurück zur Firma).
Die verantwortliche Firma darf in_bearbeitung und behoben_gemeldet setzen und kommentieren; abnehmen und erneut öffnen nur die Leitung.
Bautagesbericht: entwurf → eingereicht (Verfasserfirma) → freigegeben oder zurück auf entwurf (Eigentümer-Leitung). Freigegebene Berichte
sind unveränderlich; PDF über reportlab mit bis zu sechs Fotos.

## 4. Rechteprüfung

`plattform.zugang(user, project_id)` leitet für jede Anfrage aus der Datenbank ab: Eigentümerfirma (Büro/Inhaber, eingetragene
Leitung, zugewiesene Mitarbeiter) oder aktive Beteiligung der eigenen Firma (Mitarbeiter zusätzlich nur, wenn dem lokalen Projekt
zugewiesen). Alles andere antwortet 404, damit fremde Projekt-IDs nichts verraten. `aufgabe_laden` schränkt zusätzlich auf
Aufgaben der eigenen Firma bzw. eigene Zuteilung ein; `eintrag_laden` macht dasselbe für Lieferungen, Mängel und Tagesberichte
(Partner nur eigene Firma und nur als Büro/Projektleitung des lokalen Projekts). Mitgeschickte Firmen-IDs werden nie als Berechtigung gewertet.

Geprüft in `tests/test_plattform_20261023.py`: Definition-of-Done-Szenario (22 Schritte), Einladung per Link für unregistrierte Firma,
Ablehnen, Entfernen (Zugang endet, lokales Projekt bleibt), Projektleiter-Sichtbarkeit, fremde Firma, manipulierte IDs,
fremde Lohndaten/Personalakte/Rechnungen. `tests/test_baustelle_20261023.py`: Lieferung (Bestätigen, Verspätung, Lieferschein-Foto,
Abschluss nur Leitung), Mangel (Kommentar, Foto, behoben melden, erneut öffnen, abnehmen, Partner meldet ohne Firmenzuweisung),
Tagesbericht (Vorschlag, Entwurf mit Foto, einreichen, freigeben, PDF, danach unveränderlich), Meilensteine, geteilte Dokumente
(internes Dokument für Partner unsichtbar bis zur Freigabe), Plattform-Kalender je Rolle, Übersichtszähler.

## 5. API (neu)

`GET/PUT /api/firma/verzeichnis`, `GET /api/verzeichnis/firmen?q=` · `GET/POST/DELETE /api/projekte/{id}/leiter` ·
`GET/POST/DELETE /api/projekte/{id}/beteiligungen` · `GET /api/beteiligungen`, `POST /api/beteiligungen/{id}/antwort`,
`POST /api/beteiligungen/token`, `PUT /api/beteiligungen/{id}/freigaben` · `GET /api/plattform/uebersicht` ·
`GET/POST /api/projekte/{id}/aufgaben`, `GET/PUT/DELETE /api/aufgaben/{id}`, `POST …/status`, `POST …/zuteilung`, `POST …/fotos`,
`GET /api/aufgaben/meine` · `GET /api/projekte/{id}/anwesenheit` · `GET/POST/DELETE /api/projekte/{lokal}/freigaben`,
`GET /api/projekte/{id}/nachweise` · `GET /api/benachrichtigungen`, `POST …/{id}/gelesen`, `POST …/alle-gelesen`.

Phase 5 (`routes/baustelle.py`): `GET/POST /api/projekte/{id}/lieferungen?von&bis`, `GET/PUT/DELETE /api/lieferungen/{id}`, `POST …/status`,
`POST …/fotos` · `GET/POST /api/projekte/{id}/maengel?offen=`, `GET/PUT /api/maengel/{id}`, `POST …/status`, `POST …/kommentare`,
`POST …/fotos` · `GET/POST /api/projekte/{id}/tagesberichte`, `GET /api/projekte/{id}/tagesbericht-vorschlag?datum=`,
`GET/PUT/DELETE /api/tagesberichte/{id}`, `POST …/status`, `POST …/fotos`, `GET …/pdf` · `GET/POST /api/projekte/{id}/meilensteine`,
`PUT/DELETE /api/meilensteine/{id}` · `GET/POST /api/projekte/{id}/dokumente` (Formular: datei, kategorie, note, fuer_alle),
`PUT /api/projektdokumente/{id}` · `GET /api/projekte/{id}/plattform-kalender?von&bis` (Aufgaben, Lieferungen, Meilensteine,
Mängel-Fristen, nach Rolle gefiltert). `GET /api/plattform/uebersicht` liefert zusätzlich `lieferungen_heute`, `maengel_offen`, `berichte_offen`.
Bestehende Endpunkte sind unverändert.

## 6. Oberfläche

- **Zusammenarbeit** (Büro/Inhaber): offene Einladungen annehmen/ablehnen, eigene Plattform-Projekte, Beteiligungen, Verzeichnis-Eintrag, Benachrichtigungen.
- **Projekt (Eigentümer, Leitung)**: Reiter Firmen (Projektleitung, Firmen einladen per Verzeichnis oder E-Mail-Link, Meilensteine), Aufgaben,
  Lieferungen (je Tag planen, Status, Lieferschein-Fotos), Mängel (melden, Firma/Frist/Priorität, Kommentare, Fotos, abnehmen),
  Berichte (Bautagesberichte prüfen, freigeben, PDF), Dokumente (hochladen, für alle Firmen freigeben), Anwesenheit, Nachweise.
- **Projekt (Partner, verknüpft)**: Hinweisbanner, Reiter Aufgaben (eigene Aufgaben, Zuteilung, Status, Fotos, Meilensteine des Auftraggebers),
  für Büro/Vorarbeiter zusätzlich Lieferungen (bestätigen, Verspätung/Eintreffen melden), Mängel (behoben melden, eigene Mängel melden),
  Berichte (Entwurf mit Vorbelegung aus Aufgaben/Lieferungen/Anwesenheit, einreichen, PDF), Dokumente (freigegebene sehen, eigene hochladen)
  und Freigaben (Wochen-Nachweis, Namen in der Anwesenheit).
- **Kalender**: Tageszellen zeigen Aufgaben, Lieferungen, Meilensteine und Mängel-Fristen als Markierungen; der Tagesdialog listet sie mit
  Status und springt per „Öffnen“ in den passenden Reiter. **Zusammenarbeit** zeigt je Projekt Lieferungen heute, offene Mängel und Berichte zur Freigabe.
- **Aufgaben** (alle Nutzer): Tagesliste „Heute“, Details, Status melden, Fotos.
- Einladungslink `/#/projekteinladung/<token>`: wird gemerkt, nach Anmeldung oder Registrierung automatisch eingelöst (30 Tage gültig, einmalig).

## 7. Migration

Keine Datenmigration erforderlich. Beim Serverstart legt `db.indizes_anlegen` die neuen Indizes an (idempotent). Bestehende Projekte
ohne `leiter_ids` verhalten sich exakt wie bisher. Vor dem Ausrollen: Datenbank-Backup (`mongodump`) wie bei jedem Update.

## 8. Ausschreibungen, Angebote und Vergabe (Branch `ausschreibungen`, 23.10.2026)

Zweite Erweiterung nach dem Masterprompt „Projektplanung, Ausschreibungen und digitale Vergabeplattform“. Alles additiv:
neue Sammlungen, neue optionale Projektfelder, neue Routen (`routes/ausschreibungen.py`, Rechtemodell in `ausschreibung.py`).

### 8.1 Erweiterte Projekte und Dokumente

- `projects` optional: `projektnummer, auftraggeber, generalunternehmer, projektart, beschreibung, baubeginn, bauende, phasen[], bauabschnitte[],
  gewerke[], projektstatus, volumen, kosten, anforderungen, lat, lon` (Projektdialog → „Bauvorhaben“; Karte als OpenStreetMap-Link).
- `documents` bekommt `ordner`, `version`, `vorgaenger_id`, `aktuell`, `ersetzt_von`: neue Version per `ersetzt_id` beim Upload (Projektakte,
  geteilte Projektdokumente, Ausschreibungsunterlagen). Jede Datei trägt Name, Typ, Größe, Ersteller, Zeit, Version, Freigabe.
- Grenzen statt willkürlicher Stückzahlen: Dateigröße `MAX_DATEI_MB` (25), Speicher je Firma `SPEICHER_GB` (5, je Firma über `plan.speicher_gb`),
  Uploadrate `UPLOADS_JE_10_MIN` (120 je Nutzer); `GET /api/firma/speicher` zeigt den Stand. Überschreitung → 413/429.
- Projektinterne Dokumente (Scope `project`, nicht freigegebene Plattformdokumente) bleiben für Bieter unsichtbar; Bieter sehen nur
  Unterlagen der Ausschreibung (Scope `ausschreibung`).

### 8.2 Datenmodell

| Sammlung | Inhalt |
|---|---|
| `ausschreibungen` | `{nummer A-JJJJ-NNNN, project_id, firma_id, titel, gewerk, leistungsart, beschreibung, leistungsumfang, ausfuehrungsort, sichtbarkeit: oeffentlich/privat/kombiniert, status: entwurf/veroeffentlicht/in_vergabe/vergeben/aufgehoben, bewerbungsfrist, angebotsfrist, ausfuehrung_von/bis, anforderungen{…}, kaufmaennisch{abrechnungsart, budget, zahlungsbedingungen, vertragsbedingungen, preisaufschluesselung}, freigabe{budget, auftraggeber, adresse}, positionen[{nr, leistung, beschreibung, menge, einheit}], intern, verantwortlich_user_id, verlauf[]}` |
| `ausschreibung_einladungen` | `{ausschreibung_id, firma_id, firma_name, nachricht, status: eingeladen/angesehen/angebot}` – eindeutig je Firma |
| `angebote` | `{ausschreibung_id, firma_id, nummer AN-JJJJ-NNNN, preisart: pauschal/einheitspreise/stunden, preis_netto, stundensatz, stunden_geschaetzt, ust_satz, reverse_charge, positionen[{nr, einzelpreis, bemerkung}], leistungsbeschreibung, ausfuehrung_von/bis, verfuegbarkeit, kapazitaet, material, zusatzleistungen, bemerkungen, gueltig_bis, status, version, versionen[], nachreichen_bis, bewertung{kriterien, notiz, mindestanforderungen_erfuellt}, verlauf[]}` – ein Angebot je Firma, Überarbeitungen als Versionen |
| `ausschreibung_fragen` | `{ausschreibung_id, firma_id, text, position_nr, antwort, beantwortet_von, oeffentlich}` |
| `vergaben` | `{ausschreibung_id, angebot_id, firma_id, summe_netto, begruendung, status: vorgeschlagen/freigegeben/mitgeteilt/angenommen/abgelehnt_firma/zurueckgezogen, vorgeschlagen_von, freigegeben_von, mitgeteilt_at, bestaetigung{name, text, user}, beteiligung_id, lokales_project_id, verlauf[]}` |
| `documents` Scopes | `ausschreibung` (Unterlagen), `angebot` (Anhänge des Bieters), `vergabe` (Vertrags-/Auftragsdokumente) |

Angebotsstatus: entwurf → eingereicht → in_pruefung / rueckfrage → ueberarbeitet → angenommen / abgelehnt / zurueckgezogen.
Gesamtpreise werden serverseitig aus Mengen × Einzelpreisen berechnet; Einreichen verlangt vollständige Positionspreise.

### 8.3 Rechte und Vergaberegeln

- `ausschreibung_zugang`: Eigentümerfirma nur mit Projektleitung („leitung“); andere Firmen nur Büro/Inhaber und nur, wenn veröffentlicht
  und (plattformweit sichtbar oder eingeladen oder eigenes Angebot). Entwürfe sind unsichtbar, fremde IDs antworten 404.
- `angebot_zugang`: bietende Firma sieht ihr Angebot; die Eigentümer-Leitung erst ab Einreichung (nie Entwürfe); Bewertungen nur Eigentümer.
  Bieter sehen keine fremden Angebote, Preise, Anhänge oder Bewertungen – auch nicht über `/api/dokumente/{id}/datei`.
- Fristen: Einreichen/Ändern nur bis zur Angebotsfrist (Zeitzone der Anwendung); danach nur nach Rückfrage/Nachforderung mit
  `nachreichen_bis`. Änderungen an Ausschreibungen landen im `verlauf` (Felder) und im Sicherheitsprotokoll; Bieter werden informiert.
- Vergabe: Vorschlag (Leitung) → interne Freigabe (Büro/Inhaber; Vier-Augen-Prinzip, sobald eine zweite berechtigte Person existiert) →
  Mitteilung mit Vertragsdokumenten → **verbindliche Annahme nur durch den Inhaber der Firma mit dem Satz „Ich nehme den Auftrag verbindlich an“
  und Namensangabe**. Erst dann: Beteiligung aktiv, verknüpftes lokales Projekt (wie bei der Einladung), Ausschreibung „vergeben“, übrige Angebote
  „abgelehnt“ mit Absage. Ablehnung durch die Firma öffnet die Ausschreibung wieder. Keine automatische Vergabe nach Punkten.
- Benachrichtigungen (In-App): ausschreibung_neu (Gewerk/Region aus dem Verzeichnis), ausschreibung_einladung, ausschreibung_aktualisiert,
  ausschreibung_dokument, rueckfrage_neu, rueckfrage_antwort, angebot_eingereicht, angebot_bestaetigung, angebot_in_pruefung,
  angebot_nachforderung, angebot_entscheidung, vergabe_freigabe, vergabe_erhalten, vergabe_dokument, vergabe_angenommen, vergabe_abgelehnt,
  absage, ausschreibung_aufgehoben. „Bald endende Frist“ wird in der Übersicht berechnet (kein Zeitplaner).
- Öffentliche Auftraggeber: Die Plattform ist **keine** vergaberechtskonforme Vergabeplattform (GWB/VgV/UVgO, eVergabe); dafür wären
  separate Prüfung und Umsetzung nötig.

### 8.4 API (neu)

`GET/POST /api/projekte/{id}/ausschreibungen` · `GET /api/ausschreibungen/uebersicht` · `GET /api/ausschreibungen?q&gewerk&ort&auftraggeber&projektart&abrechnungsart&von&bis&frist_bis&volumen_max&status&nur_einladungen` ·
`GET/PUT/DELETE /api/ausschreibungen/{id}`, `POST …/veroeffentlichen`, `POST …/aufheben`, `POST …/einladungen`, `DELETE …/einladungen/{eid}`, `POST …/dokumente`,
`GET …/positionen.csv`, `POST …/positionen/import` (CSV), `POST …/positionen/gaeb` (501, Modul `gaeb.py` vorbereitet), `POST …/fragen`, `POST /api/fragen/{id}/antwort`,
`POST …/angebot`, `GET …/angebote` (Liste + Vergleich), `POST …/vergabe` · `GET/PUT /api/angebote/{id}`, `POST …/einreichen`, `POST …/zurueckziehen`, `POST …/dokumente`,
`GET …/positionen.csv`, `POST …/pruefung`, `PUT …/bewertung` · `GET /api/vergaben/{id}`, `POST …/freigabe`, `POST …/dokumente`, `POST …/mitteilen`, `POST …/zurueckziehen`, `POST …/antwort` ·
`GET /api/firma/speicher`. `GET/PUT /api/firma/verzeichnis` um `regionen[]` und `ausschreibungen_benachrichtigen` erweitert.

### 8.5 Oberfläche

- Menü **Ausschreibungen** (Büro/Inhaber): Entdecken (Filter Gewerk, Ort, Abrechnungsart, Frist, nur Einladungen), Einladungen, Meine Angebote,
  Erhaltene Aufträge (mit Annahme), Meine Ausschreibungen (mit Zählern und laufenden Vergaben); Hinweis auf bald endende Fristen.
- Projekt → Reiter **Ausschreibungen** (Eigentümer-Leitung): Liste, Neue Ausschreibung (Dialog mit allen Feldern, Positionen-Editor, CSV-Einfügen).
- Ausschreibungsdetail: Übersicht (Eckdaten, Kaufmännisches, Projekt, Einladungen, Verlauf), Positionen (CSV), Unterlagen (Bilder und Dokumente),
  Anforderungen, Rückfragen (fragen/antworten, Freigabe für alle Bieter), Angebot abgeben (Bieter: Preisart, Einzelpreise je Position mit
  Summen, Anhänge, Entwurf/Einreichen/Zurückziehen, Verlauf), Angebote (Leitung: Vergleichstabelle, Details, Bewertung 0–5 je Kriterium,
  In Prüfung/Rückfrage/Ablehnen, Zur Vergabe vorschlagen), Vergabe (Schritte, Dokumente, Freigabe, Mitteilung, verbindliche Annahme).
- Projektdialog → „Bauvorhaben“; Zusammenarbeit → Verzeichnis mit Regionen und Benachrichtigungsschalter; Projektdokumente mit Ordnern,
  Versionen und „ältere Versionen anzeigen“.

### 8.6 Tests

`tests/test_ausschreibung_20261023.py` (Beispielablauf GOLDBECK – Logistikzentrum Hannover): Anlegen, Entwurf unsichtbar, Veröffentlichen mit
Pflichtfeldern, Benachrichtigungen nach Gewerk/Region, Marktplatz und Filter, private Ausschreibung nur für Eingeladene, Mitarbeiter ohne Zugriff,
Bieteransicht ohne interne Vermerke/Budget, interne Projektunterlagen privat, Änderungsprotokoll, Aufheben; Angebote mit Positionspreisen und
Summen, kein Doppelangebot, Entwürfe für den Eigentümer unsichtbar, Konkurrenten sehen nichts, Vergleich sortiert, Bewertung nur Leitung,
Rückfragen öffentlich/privat, Frist serverseitig, Nachforderung mit Version 2, Rücknahme protokolliert; Vergabe mit Vier-Augen-Freigabe,
Vertragsdokument, Mitteilung, Annahme nur Inhaber mit Bestätigungssatz, Beteiligung + lokales Projekt, Absage an Konkurrenten, Aufgabe für die
Firma, Zeiten/Monat/Rechnung/PDF der Firma weiterhin (und für den Auftraggeber unsichtbar), Protokoll beider Firmen; Ablehnung durch die Firma,
Vergabe zurückziehen, CSV-Import, GAEB 501, Dokumentversionen, Speichergrenze 413.

## 9. Offen (ausdrücklich nicht fertig)

- GAEB (X83/X84, GAEB 90): nur Erkennung und ehrliche Ablehnung (`gaeb.py`); Austausch des LV über CSV.
- Umkreissuche mit Geokoordinaten (Projekte können lat/lon tragen; der Marktplatz filtert nach Ortstext); Karte nur als OpenStreetMap-Link.
- Benachrichtigungen nur In-App; „bald endende Frist“ ohne Zeitplaner; keine E-Mail/Push.
- Tabellenimport nur CSV (kein XLSX); Angebots-PDF wird vom Bieter hochgeladen, nicht erzeugt.
- Vergaberecht für öffentliche Auftraggeber nicht abgedeckt (siehe 8.3).

- Lieferungen sind Termine mit Freitext (Material, Menge); keine Mengen-/Lagerverwaltung, kein Zugang für Lieferanten.
- Bautagesbericht-PDF ohne Unterschrift; keine Sammel-PDF je Woche/Monat; Mängel ohne Serien-/Sammelabnahme.
- E-Mail-/Push-Benachrichtigungen (nur In-App), Benachrichtigungseinstellungen je Nutzer.
- Ein Nutzer in mehreren Firmen (Mehrfachmitgliedschaft): bewusst nicht gebaut; eine Person braucht je Firma ein Konto.
- Dubletten-Zusammenführung im Verzeichnis über Administratorprozess; aktuell verhindert nur die E-Mail-Eindeutigkeit doppelte Konten.
- Lasttests, Paginierung großer Listen (Limit 2000 je Monat bei Aufgaben/Lieferungen/Mängeln, 1000 Berichte).
- Vor Produktivbetrieb rechtlich prüfen: Auftragsverarbeitung je Kunde, Rechtsgrundlage für Anwesenheitsdaten gegenüber dem
  Auftraggeber (Freigabe durch die Partnerfirma ist eingebaut), Aufbewahrungsfristen für Fotos. Die Anwendung ist nicht ohne
  unabhängige Prüfung als DSGVO-konform zu bezeichnen.
