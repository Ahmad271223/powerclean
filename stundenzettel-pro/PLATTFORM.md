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
| Tests | pytest mit `DB_MODE=memory` (mongomock), vorher 32 Tests, jetzt 35. |
| Migrationsrisiken | Keine Schemaänderung nötig. Neue Felder sind optional (`projects.leiter_ids`, `projects.verknuepft`, `firmen.verzeichnis`), neue Sammlungen leer. Indizes werden beim Start idempotent angelegt. |

## 2. Architekturentscheidung

Eigentümer, Projekt und Zugriff werden getrennt:

- **Eigentümer eines Datensatzes** bleibt die Firma (`firma_id`). Nichts wird firmenübergreifend geschrieben.
- **Projekt**: gehört genau einer Firma (Auftraggeber). Andere Firmen nehmen über eine **Beteiligung** (`beteiligungen`) teil.
- **Verknüpftes lokales Projekt**: Bei Annahme einer Einladung entsteht in der Partnerfirma ein eigenes Projekt mit
  `verknuepft = {project_id, owner_firma_id, beteiligung_id, gewerk, rolle, status}`. Darauf laufen Stempeluhr, Stundenzettel,
  Monats-PDF, Rechnung (Kunde = Auftraggeber), Lohnvorbereitung – unverändert und nur in der Partnerfirma sichtbar.
- **Zwischen den Firmen fließen nur**: Aufgaben (vom Auftraggeber), Fotos zu Aufgaben, Anwesenheitszahlen (Namen erst nach
  Freigabe der Partnerfirma), ausdrücklich freigegebene Wochen-Nachweise (Zeiten mit Namen, Kunden-Unterschrift).
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
| `documents` (scope `aufgabe`) | Fotos zu Aufgaben, `firma_id` = hochladende Firma, Zugriff über die Aufgabe. |
| `freigaben` | `{project_id, beteiligung_id, firma_id, lokales_project_id, week_monday, freigegeben_von}` |
| `benachrichtigungen` | `{firma_id, user_ids|null, mindestens, art, text, link, gelesen_von[]}` |

Aufgabenstatus: geplant → zugewiesen → in_bearbeitung / blockiert → eingereicht → abgeschlossen / abgenommen. Die beauftragte Firma darf
`in_bearbeitung`, `blockiert`, `eingereicht` setzen, zugeteilte Mitarbeiter `in_bearbeitung`, `eingereicht`; abnehmen darf nur die
Projektleitung der Eigentümerfirma. Jeder Statuswechsel steht im `verlauf` und im Sicherheitsprotokoll.

## 4. Rechteprüfung

`plattform.zugang(user, project_id)` leitet für jede Anfrage aus der Datenbank ab: Eigentümerfirma (Büro/Inhaber, eingetragene
Leitung, zugewiesene Mitarbeiter) oder aktive Beteiligung der eigenen Firma (Mitarbeiter zusätzlich nur, wenn dem lokalen Projekt
zugewiesen). Alles andere antwortet 404, damit fremde Projekt-IDs nichts verraten. `aufgabe_laden` schränkt zusätzlich auf
Aufgaben der eigenen Firma bzw. eigene Zuteilung ein. Mitgeschickte Firmen-IDs werden nie als Berechtigung gewertet.

Geprüft in `tests/test_plattform_20261023.py`: Definition-of-Done-Szenario (22 Schritte), Einladung per Link für unregistrierte Firma,
Ablehnen, Entfernen (Zugang endet, lokales Projekt bleibt), Projektleiter-Sichtbarkeit, fremde Firma, manipulierte IDs,
fremde Lohndaten/Personalakte/Rechnungen.

## 5. API (neu)

`GET/PUT /api/firma/verzeichnis`, `GET /api/verzeichnis/firmen?q=` · `GET/POST/DELETE /api/projekte/{id}/leiter` ·
`GET/POST/DELETE /api/projekte/{id}/beteiligungen` · `GET /api/beteiligungen`, `POST /api/beteiligungen/{id}/antwort`,
`POST /api/beteiligungen/token`, `PUT /api/beteiligungen/{id}/freigaben` · `GET /api/plattform/uebersicht` ·
`GET/POST /api/projekte/{id}/aufgaben`, `GET/PUT/DELETE /api/aufgaben/{id}`, `POST …/status`, `POST …/zuteilung`, `POST …/fotos`,
`GET /api/aufgaben/meine` · `GET /api/projekte/{id}/anwesenheit` · `GET/POST/DELETE /api/projekte/{lokal}/freigaben`,
`GET /api/projekte/{id}/nachweise` · `GET /api/benachrichtigungen`, `POST …/{id}/gelesen`, `POST …/alle-gelesen`.
Bestehende Endpunkte sind unverändert.

## 6. Oberfläche

- **Zusammenarbeit** (Büro/Inhaber): offene Einladungen annehmen/ablehnen, eigene Plattform-Projekte, Beteiligungen, Verzeichnis-Eintrag, Benachrichtigungen.
- **Projekt (Eigentümer, Leitung)**: Reiter Firmen (Projektleitung, Firmen einladen per Verzeichnis oder E-Mail-Link), Aufgaben, Anwesenheit, Nachweise.
- **Projekt (Partner, verknüpft)**: Hinweisbanner, Reiter Aufgaben (eigene Aufgaben, Zuteilung, Status, Fotos) und Freigaben (Wochen-Nachweis, Namen in der Anwesenheit).
- **Aufgaben** (alle Nutzer): Tagesliste „Heute“, Details, Status melden, Fotos.
- Einladungslink `/#/projekteinladung/<token>`: wird gemerkt, nach Anmeldung oder Registrierung automatisch eingelöst (30 Tage gültig, einmalig).

## 7. Migration

Keine Datenmigration erforderlich. Beim Serverstart legt `db.indizes_anlegen` die neuen Indizes an (idempotent). Bestehende Projekte
ohne `leiter_ids` verhalten sich exakt wie bisher. Vor dem Ausrollen: Datenbank-Backup (`mongodump`) wie bei jedem Update.

## 8. Offen (ausdrücklich nicht fertig)

- Lieferungs- und Materialmanagement, Bautagesberichte, Mängelmanagement (Phase 5 des Masterprompts) – Datenmodell und Statusflüsse
  sind vorbereitet (gleiches Muster wie Aufgaben), aber nicht implementiert.
- E-Mail-/Push-Benachrichtigungen (nur In-App), Benachrichtigungseinstellungen je Nutzer.
- Ein Nutzer in mehreren Firmen (Mehrfachmitgliedschaft): bewusst nicht gebaut; eine Person braucht je Firma ein Konto.
- Dubletten-Zusammenführung im Verzeichnis über Administratorprozess; aktuell verhindert nur die E-Mail-Eindeutigkeit doppelte Konten.
- Projektkalender mit Lieferungen/Meilensteinen (Aufgaben haben ein Datum, der Kalender zeigt weiterhin Zeiten).
- Lasttests, Paginierung großer Aufgabenlisten (Limit 2000 je Monat).
- Vor Produktivbetrieb rechtlich prüfen: Auftragsverarbeitung je Kunde, Rechtsgrundlage für Anwesenheitsdaten gegenüber dem
  Auftraggeber (Freigabe durch die Partnerfirma ist eingebaut), Aufbewahrungsfristen für Fotos. Die Anwendung ist nicht ohne
  unabhängige Prüfung als DSGVO-konform zu bezeichnen.
