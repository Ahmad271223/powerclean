# Baustellenplattform: Zusammenarbeit mehrerer Firmen (Branch `plattform`)

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
| Tests | pytest mit `DB_MODE=memory` (mongomock), vorher 32 Tests, jetzt 38 (Plattform 3, Baustellenalltag 3). |
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

## 8. Offen (ausdrücklich nicht fertig)

- Lieferungen sind Termine mit Freitext (Material, Menge); keine Mengen-/Lagerverwaltung, kein Zugang für Lieferanten.
- Bautagesbericht-PDF ohne Unterschrift; keine Sammel-PDF je Woche/Monat; Mängel ohne Serien-/Sammelabnahme.
- E-Mail-/Push-Benachrichtigungen (nur In-App), Benachrichtigungseinstellungen je Nutzer.
- Ein Nutzer in mehreren Firmen (Mehrfachmitgliedschaft): bewusst nicht gebaut; eine Person braucht je Firma ein Konto.
- Dubletten-Zusammenführung im Verzeichnis über Administratorprozess; aktuell verhindert nur die E-Mail-Eindeutigkeit doppelte Konten.
- Lasttests, Paginierung großer Listen (Limit 2000 je Monat bei Aufgaben/Lieferungen/Mängeln, 1000 Berichte).
- Vor Produktivbetrieb rechtlich prüfen: Auftragsverarbeitung je Kunde, Rechtsgrundlage für Anwesenheitsdaten gegenüber dem
  Auftraggeber (Freigabe durch die Partnerfirma ist eingebaut), Aufbewahrungsfristen für Fotos. Die Anwendung ist nicht ohne
  unabhängige Prüfung als DSGVO-konform zu bezeichnen.
