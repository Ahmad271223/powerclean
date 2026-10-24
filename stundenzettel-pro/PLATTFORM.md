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

## 1b. Firmenarten (23.10.2026)

Jede Firma hat eine **Firmenart** (`firmen.art`), gewählt bei der Registrierung, änderbar durch den Inhaber unter Firma → Firmendaten:

| Art | Wer | Menü und Startseite | Ausschreibungen |
|---|---|---|---|
| `betrieb` (Standard) | Handwerk, Reinigung, Dienstleistung | Volles Menü wie bisher (Zeiten, Stundenzettel, Rechnungen, Kunden) | Entdecken, Einladungen, Meine Angebote, Erhaltene Aufträge; eigene Ausschreibungen möglich (z. B. an Nachunternehmer) |
| `auftraggeber` | Generalunternehmer, Bauherr, Projektsteuerung | Übersicht mit Ausschreibungen/Angeboten/Vergaben, Bauprojekte, Ausschreibungen, Zusammenarbeit, Aufgaben, Mitarbeiter, Stempeluhr, Auswertung, Abwesenheiten, Exporte, Firma, Protokoll – keine Rechnungen, keine Kunden | Nur „Meine Ausschreibungen“ und Vergaben; keine Benachrichtigung über fremde Ausschreibungen, keine Angebotsabgabe im Menü |
| `beides` | Firmen, die ausführen und vergeben | Volles Menü plus Auftraggeber-Block auf der Startseite | Alles |

Die Rechteprüfung bleibt datengetrieben (Projektbesitz, Beteiligung, Einladung); die Firmenart steuert Oberfläche, Startseite und Benachrichtigungen.
Rollen innerhalb der Firma (Inhaber, Büro, Vorarbeiter, Mitarbeiter) gelten unverändert für beide Arten; Mitarbeiter eines Auftraggebers sehen
weiterhin nur Stempeluhr, Zeiten, Projekte, Aufgaben und Abwesenheit.

## 1c. Lizenz- und Abrechnungsmodell (23.10.2026)

- **GU-Projektabo** (`projects.gu_abo`): wird für Firmen der Art auftraggeber/beides automatisch aktiviert, sobald eine Ausschreibung des
  Projekts veröffentlicht oder eine Firma zum Projekt eingeladen wird (`abo.gu_abo_aktivieren`); 50,99 € netto je Monat und Projekt,
  einmal je Projekt (nicht je Gewerk). Zeiträume (`zeitraeume[]`) bleiben für die Abrechnung erhalten; Beenden durch den Inhaber
  (`POST /api/projekte/{id}/gu-abo`), eine spätere Veröffentlichung/Einladung aktiviert erneut. Betriebe, die Partner einladen, zahlen nichts.
- **Firmenabo vs. kostenlose Projektteilnahme** (`plan.stufe` = firma|teilnahme): nach der Testphase ohne Freischaltung wird eine Firma
  zur Teilnahme (`plan_status` → status `teilnahme`, schreiben erlaubt). Mit `firmenabo_noetig`/`firmenabo_lesend` gesperrt (402):
  Mitarbeiter einladen, eigene Projekte, Zeiten/Stempeluhr auf eigenen Projekten (`gemeinsam.projekt_laden(schreiben=True)`), Rechnungen anlegen,
  Lohnvorbereitung, API-Schlüssel, Webhooks. Erlaubt: Ausschreibungen, Angebote, Rückfragen, Beteiligung annehmen, Zeiten/Fotos/Berichte auf verknüpften Projekten.
- **Nur Auftraggeber schreiben aus**: Anlegen und Veröffentlichen formaler Ausschreibungen verlangt `firmen.art` ∈ {auftraggeber, beides}
  (403 mit Hinweis). Betriebe laden Partner weiterhin direkt unter Zusammenarbeit ein.
- Preise an einer Stelle (`preise.py`, `GET /api/preise`), Abrechnungsgrundlage `GET /api/admin/abos` (Betreiber), Lizenzseite zeigt
  Firmenabo, aktive GU-Projekte und Monatssumme. Offen: Zahlungsdienst, automatische Verlängerung/Mahnung, Enterprise-Vertrag.

## 1d. Bauabwicklung, Projektakte, E-Mail-Nachweise, Rechte (23.10.2026)

- **Nachträge** (`routes/abwicklung.py`, Sammlung `nachtraege`, Scope `nachtrag` für Dateien): die beauftragte Firma legt einen Entwurf an
  (oder der Auftraggeber fragt an → `angefragt`), reicht mit Preis ein (`eingereicht`), die Projektleitung des Auftraggebers gibt frei oder
  lehnt mit Begründung ab. Erst die Freigabe setzt `auftragswert_vorher/nachher` am Nachtrag und `auftragswert_aktuell`/`nachtraege_summe`
  an der Beteiligung; der ursprüngliche Auftrag (Vergabe `summe_netto`) bleibt unverändert. PDF `GET /api/nachtraege/{id}/pdf` für beide Seiten.
- **Abnahmen** (`abnahmen`, Scope `abnahme`): Firma fordert an (`angefordert`) oder die Projektleitung legt einen Entwurf an; Ergebnis
  (abgenommen, unter Vorbehalt mit Mängeln, verweigert), Teilnehmer, Vorbehalte, Nachbesserungsfrist, Mängel-Snapshot aus `maengel`;
  `abschliessen` → `erstellt` (unveränderlich); die Firma bestätigt oder widerspricht (`antwort`). PDF `GET /api/abnahmen/{id}/pdf`.
- **Projektakte (ZIP)** (`projektakte.py`, `routes/archiv.py`, Sammlung `projektakten`, Dateien unter `DATA_DIR/projektakten/<firma>/`):
  `POST /api/projekte/{id}/projektakte` für jede Firma im Firmenabo (GU-Projekte des Auftraggebers auch ohne Firmenabo, 402 sonst).
  Inhalt siehe `00_LIESMICH.txt` in der ZIP; eigene Daten immer, Plattformdaten je nach Rolle (Eigentümer: alle sichtbaren Unterlagen der
  Firmen; beteiligte Firma: nur eigene und für alle freigegebene). Liste `GET /api/projektakten`, Download `GET /api/projektakten/{id}.zip`,
  Löschen nur Inhaber (vor Ablauf der Aufbewahrung `AUFBEWAHRUNG_JAHRE`, Standard 10, nur mit `erzwingen=true`). Erzeugung läuft synchron;
  für sehr große Projekte ist ein Hintergrundjob vorgesehen (offen).
- **E-Mail-Ausgang mit Nachweis** (`mail.py`, Sammlung `email_ausgang`): jede E-Mail wird gespeichert (Empfänger, Betreff, Text, Anlass,
  Projekt, Absender- und Empfängerfirma) und über SMTP zugestellt (Wiederholungen 1/5/15/60/240 min, Hintergrunddienst). Ohne SMTP bleibt
  der Nachweis mit Status `nicht_konfiguriert`. Anlässe: Mitarbeiter-/Projekt-/Ausschreibungseinladung, Einreichungsnachweis und Eingang
  eines Angebots, Zuschlag, Absage, Auftragsannahme, Nachtrag, Abnahme – nie jede Statusänderung. Abschaltbar je Firma
  (`firmen.email_benachrichtigungen`) und je Nutzer (`users.email_benachrichtigungen`). Liste `GET /api/firma/emails`.
- **Startseiten-Aufgaben** `GET /api/dashboard/aufgaben`: offene Punkte je Rolle (Vergaben freigeben, Angebote prüfen, Rückfragen,
  Fristen, Nachträge, Abnahmen, Berichte, Mängel, Anträge, Stempelungen, Abschluss; Mitarbeiter: Aufgaben heute, Anträge, Prüfhinweise).
- **Projektleiter & Rechte** `GET /api/firma/projektleiter` (Zuordnung weiter über `/api/projekte/{id}/leiter`). Rechtematrix:

| Daten | sehen | nie |
|---|---|---|
| Angebote/Preise der Bieter | Projektleitung des Bauprojekts | andere Bieter, Mitarbeiter |
| Zielpreis, Budget, interne Notizen | Projektleitung der eigenen Firma | beteiligte Firmen |
| Stundenlöhne, Personal-/Lohndaten, Rechnungen | Büro/Inhaber der jeweiligen Firma | Auftraggeber, Partnerfirmen |
| Aufgaben, Lieferungen, Mängel, Berichte, Nachträge, Abnahmen | Projektleitung alles; beteiligte Firma nur eigene | Mitarbeiter nur zugeteilte Aufgaben |
| Namen fremder Mitarbeiter | nur nach Freigabe der Partnerfirma | sonst nur Anzahlen |

- **Firmenverifizierung** `POST /api/admin/verifizieren` (Betreiber, `firmen.verifiziert = {status, am, hinweis}`), sichtbar im
  Verzeichnis, in `firma_kurz` (Auftraggeber-Info der Ausschreibungen) und bei der Firma („Geprüfte Firma“). Prüfung von Hand
  (Handelsregister/Gewerbeanmeldung, Ansprechpartner) – kein automatischer Abgleich.
- **Unteraufträge**: eine beauftragte Firma lädt zu ihrem verknüpften Projekt eigene Subfirmen ein (Kette über `verknuepft`); der
  Auftraggeber sieht davon nichts, Betriebe zahlen dafür keine Projektgebühr (Test `test_kern_20261023.py::test_07`).
- **Datenhoheit nach Projektende**: jede Firma behält ihre eigenen Daten (Zeiten, Fotos, Rechnungen, Angebote) im eigenen Mandanten; der
  Auftraggeber behält die Plattformdaten seines Projekts (Aufgaben, Mängel, Berichte, Nachträge, Abnahmen, freigegebene Nachweise); jede
  Seite kann jederzeit ihre Projektakte ziehen. Eine beendete Beteiligung entfernt keine Daten (`verknuepft.status = entfernt`).
- **Fair Use / Großprojektlimits**: 5 GB je Firma (`plan.speicher_gb`), 25 MB je Datei, 120 Uploads je 10 Minuten und Nutzer,
  sechs Fotos je Bautagesbericht-PDF; ein GU-Projekt ist über die Kontingente der beteiligten Firmen begrenzt.
- **Zahlungsfehler, Streitfälle**: ohne Zahlungsdienst setzt der Betreiber nach einer Mahnung `plan.hinweis` (sichtbar auf der Lizenzseite)
  und danach `status: gesperrt` (Lesen bleibt). Streit über Zuschlag, Nachtrag oder Abnahme wird aus `verlauf[]`, Protokoll und
  E-Mail-Nachweisen belegt; alle Entscheidungen tragen Name und Zeitstempel.
- Offen: Chat/Nachrichten-Threads, Zahlungsdienst, Hintergrundjob für große Projektakten, Zwei-Faktor-Anmeldung, automatische Verifizierung.

## 1e. Stufe A – Rechte je Büro-Nutzer, Fotoschutz, GU-Freischaltung (24.10.2026)

- Rechte (`auth.py`: `RECHTE`, `RECHTE_BUERO_STANDARD`, `rechte_von`, `hat_recht`, `recht_noetig`, `schreibend_mit_recht`,
  `firmenabo_noetig(…, recht)`): Inhaber alles; Büro Standard (Projekte, Personal, Lohn, Rechnungen, Plantafel) plus `users.rechte`;
  Vorarbeiter/Mitarbeiter nichts. Nur der Inhaber setzt `rechte`, nur an Büro-Konten. Betroffene Routen: Projekte anlegen/ändern (projekte),
  Mitarbeiter einladen/ändern/deaktivieren, fremde Zeiten, Warnungen, laufende Stempelungen, Konten, Protokoll/MiLoG-Export (personal),
  Lohndaten/Lohnvorbereitung/Lohnexporte (lohn), Rechnungen (rechnungen), Plantafel (plantafel). Kalkulation und Kostensätze sind
  vorbereitet und standardmäßig nicht vergeben.
- Fotoschutz: `gemeinsam.foto_fuer_nutzer` entfernt Hochlader und Dateiname für Kollegen ohne Personal-Recht; `GET /api/dokumente/{id}/datei`
  liefert Projektfotos anderer ohne EXIF; Löschen nur Hochlader oder Personal-Recht.
- GU-Freischaltung: `abo.gu_freigeschaltet` (Testphase oder `firmen.freischaltungen.gu`), gesetzt über `POST /api/admin/plan` mit `gu`;
  Auftraggeber-Routen antworten sonst 403 „GU-Freischaltung“.
- Bestandsaudit mit Befunden A1–A7 und PR-#8-Bewertung: `AUDIT_20261024.md`. Tests `tests/test_stufe_a_20261024.py`.

## 1f. Stufe B – Plantafel, Arbeitszeitabgleich, Erinnerungen (24.10.2026)

- Datenmodell: `einsaetze` {id, firma_id, project_id, user_id, date, start_time, end_time, pause_minutes, planned_minutes, address, note,
  taetigkeit, kolonne_id, status geplant|abgesagt, version, verlauf[], freigabe, serie_id}, `kolonnen` {id, firma_id, name, mitglieder[]},
  `erinnerungen` (eindeutige `id` je Einsatz und Version). Nachtschichten über Mitternacht erlaubt (Ende < Beginn).
- API `/api/einsatzplan`: `GET` (Zeitraum, Filter; Planer bekommen Mitarbeiter, Kolonnen, Projekte, Kapazität; alle bekommen Abwesenheiten,
  Feiertage, Erinnerungseinstellung), `GET /meine`, `POST` (409 bei Überschneidung oder Abwesenheit, `erzwingen` übersteuert), `PUT /{id}`,
  `POST /{id}/kopieren`, `DELETE /{id}?grund=` (Absage, nicht Löschung), `POST /{id}/wiederherstellen`, `POST /{id}/rueckgaengig`,
  Kolonnen CRUD, `GET /abgleich`, `POST /{id}/freigabe`, `POST /{id}/freigabe-zuruecknehmen`, `GET /stundenzettel.pdf`.
- Abgleich: je Einsatz Status `passt` (± 15 Minuten), `abweichung` (mit Hinweisen: zu früh/spät, Pause, fehlende Pause), `fehlt` (keine
  Stempelung), `offen` (Zukunft), `freigegeben`. Freigabe schreibt die anrechenbare Zeit in den Zeiteintrag, hebt die Stempelung als
  `original` auf und vermerkt Name, Zeit und Begründung; ohne Stempelung entsteht ein Eintrag mit Quelle `freigabe`. Zurücknehmen stellt
  `original` wieder her. Lohn, Exporte (zeiten.csv mit Spalten „Freigegeben“, „Ursprünglich …“) und Projektakte rechnen mit dem Eintrag.
- Erinnerungen (`erinnerungen.py`): Dienst prüft minütlich; je Firma `firmen.erinnerung = {uhrzeit, email}` (Standard 18:00, E-Mail an);
  Benachrichtigung und E-Mail für Einsätze des Folgetags, einmal je Einsatz und Version. Planänderungen für heute/morgen melden sofort
  (`_planaenderung_melden`, Art `einsatz_aenderung`). Im Speicher-Modus läuft der Dienst nur mit `EINSATZ_DIENST=1`.
- Oberfläche: `PlantafelPage.jsx` (Raster, Drag & Drop, Kopiermodus, Kolonnen, Abgesagte einblenden, Abgleich-Bereich, PDF), `MeinEinsatzplanPage.jsx`
  (Heute, Morgen, Diese Woche, Nächste Woche, Später, Letzte Tage; Navigation, Einstempeln), Stempeluhr „Mein Tag“ mit den Einsätzen von
  heute und morgen, Startseite „Plantafel: Mitarbeiter einteilen“. Tests `tests/test_plantafel_20261024.py` (4 Tests).
- Offen: Serien (`serie_id` vorbereitet), Schichtvorlagen, Kapazitätsplanung über Wochenstunden, Push-Benachrichtigung.

## 1g. Stufe C – Kundenangebote, Auftrag, Kalkulation (24.10.2026)

- Sammlungen `kundenangebote` (getrennt von den GU-Bieterangeboten in `angebote`): {id, firma_id, nummer, jahr, seq, version, vorgaenger_id, ersetzt_durch,
  status anfrage|entwurf|gesendet|angenommen|abgelehnt|zurueckgezogen|abgelaufen|ersetzt, titel, customer_id, kunde (Momentaufnahme), project_id,
  datum, gueltig_bis, anfrage, einleitung, schluss, zahlungsbedingungen, positionen[], zuschlaege[], rabatt_prozent, reverse_charge, summen, token,
  pdf_pfad, versand[], annahme, ablehnung, auftrag, verlauf[], intern}; `angebotsvorlagen`; Zähler `firmen.angebotszaehler.{jahr}`.
- Positionsstruktur (`angebote.py`, auch für Rechnungen/Aufmaß gedacht): {id, art titel|leistung|stunden|material|pauschal|text, text, beschreibung, menge,
  einheit, einzelpreis, rabatt_prozent, alternativ, eventual, leistung_id, kalkulation}. `nummerieren()` (1, 1.1 …), `summen()` (Positionen → Zuschläge →
  Rabatt → USt), `steuer_bestimmen()` (S/E/AE), `kalkulation_position()`/`kalkulation_angebot()` (Selbstkosten, vk_vorschlag, gewinn, aufschlag_prozent,
  marge_prozent, deckungsbeitrag, stundenverrechnungssatz, vollstaendig, hinweise), `oeffentlich()` (Kundensicht ohne Kalkulation/Verlauf).
- API `/api/kundenangebote`: Liste (status, project_id, customer_id, alle), POST (auch `status: anfrage`, `vorlage_id`, `kunde_frei`), GET/PUT/DELETE (nur
  anfrage/entwurf), `/kopieren`, `/als-vorlage`, `/angebot.pdf`, `/senden` (an, nachricht, ohne_email → Snapshot unter `DATA_DIR/angebote/<firma>/`,
  Token, E-Mail mit Anhang), `/version`, `/annahme`, `/ablehnen`, `/zurueckziehen`, `/auftrag` (project_id oder neues Projekt: `projects.auftrag`,
  `abrechnungsart_projekt`, `pauschale_netto`), `/kalkulation` GET/PUT (Recht kalkulation, auch nach dem Senden), `/kalkulation/uebernehmen`;
  Vorlagen `/api/kundenangebote/vorlagen`. Öffentlich ohne Anmeldung: `GET /api/oeffentlich/angebot/{token}`, `…/angebot.pdf`, `POST …/antwort`.
- Rechte: neues Recht `angebote` (Standard für Büro an); `kalkulation` für die interne Kalkulation; `kostensaetze` für `firmen.kalkulation`
  (`firma_oeffentlich` blendet das Feld sonst aus, `PUT /api/firma` lehnt ab). E-Mail-Ausgang kann Anhänge (`email_ausgang.anhaenge`, Dateien unter
  `DATA_DIR/email_anhaenge/<id>/`). Projektakte: `06_Angebote/` (PDF je Version, angebote.csv, auftrag.json). Startseite: Kachel „Offene Angebote“
  und offene Punkte (Anfragen, bald ablaufende Angebote, Aufträge anlegen).
- Oberfläche: `AngebotePage` (Liste, Filter, Neu-Dialog mit Kunde/Vorlage/Projekt oder nur Anfrage, Vorlagenverwaltung), `AngebotPage` (Editor,
  Summen live, Senden-/Annahme-/Auftragsdialoge, Versionen, Verlauf), `components/angebot/{PositionenEditor,KalkulationPanel,AngeboteEinstellungenKarte,AuftragTab}`,
  `AngebotOeffentlichPage` (`/angebot/:token`), `lib/angebot.js` (Summenrechnung wie der Server). Tests `tests/test_angebote_20261024.py` (3 Tests).
- Offen: Aufmaß-Mengen in Positionen, Artikelstamm statt freier Materialpositionen (Stufe D/F), Rechnung aus dem Auftrag (Stufe E), Unterschrift
  des Kunden auf dem Antwortlink, Erinnerung zum Nachfassen per E-Mail.

## 1h. Stufe D – Artikel, Material, Eingangsrechnungen, Nachkalkulation (24.10.2026)

- Sammlungen: `artikel` {id, firma_id, nummer (eindeutig je Firma), name, beschreibung, einheit, einkaufspreis, verkaufspreis, hersteller, lieferant, kategorie,
  steuer_satz, aktiv, quelle manuell|csv}, `materialverbrauch` {id, firma_id, project_id, user_id, user_name, date, artikel_id, artikel_nummer, bezeichnung, menge,
  einheit, einkaufspreis (Momentaufnahme), verkaufspreis, kosten, note, quelle, status erfasst|geprueft, geprueft_von/at}, `eingangsrechnungen` {id, firma_id,
  lieferant, lieferant_ustid, rechnungsnummer, rechnungsdatum, faellig_am, netto, ust, brutto, zuordnungen[{project_id, projekt_name, betrag_netto, kostenart}],
  kostenart, notiz, dokument_id, status erfasst|geprueft|bezahlt|storniert, bezahlt_am, zahlungsart, dublette, dublette_hinweis, verlauf[]}; Belege als
  `documents` mit scope `eingangsrechnung` (Zugriff nur mit Recht `rechnungen`).
- `material.py`: `csv_lesen`/`spalten_zuordnen`/`artikel_aus_csv` (Synonyme für Spaltennamen, `zahl()` für Dezimalkomma), `erechnung_auslesen` (CII-XML →
  Vorschlag), `zugferd_xml_aus_pdf` (pikepdf-Anhang), `dublette_schluessel`, `kostensatz_mitarbeiter` (Stundenlohn × (1 + Lohnnebenkosten) | Monatsgehalt ÷
  (Wochenstunden × 4,33) | Firmensatz | fehlt), `nachkalkulation(firma, projekt)`.
- API: `/api/artikel` (GET mit q/kategorie/aktiv, POST, PUT, DELETE → deaktiviert bei Verwendung, `/auswahl` für Mitarbeiter ohne Preise, `/import` mit
  `vorschau=1`), `/api/projekte/{id}/material` (GET/POST), `/api/material/{id}` (PUT/DELETE), `/api/material/{id}/pruefen` (Recht kalkulation; Preis setzen
  braucht kostensaetze), `/api/eingangsrechnungen` (GET mit status/project_id, POST mit `erzwingen` bei Dublette, `/datei` Upload mit Vorschlag, GET/PUT/DELETE
  `{id}`, `/pruefen`, `/bezahlt`, `/storno`), `/api/projekte/{id}/nachkalkulation`, `/api/nachkalkulation` (Übersicht mit `warnung`). Startseite:
  `kostenabweichungen`, offene Punkte `eingangsrechnungen_pruefen`, `eingangsrechnungen_faellig`, `material_pruefen`. Projektakte: `07_Material/`,
  `08_Eingangsrechnungen/` (CSV + Belege), `09_Nachkalkulation/nachkalkulation.json`.
- Kostenmodell: `firmen.kalkulation.lohnnebenkosten_prozent` (neu, Standard 0 – bewusst nicht geraten). Geplante Zeit (Angebotskalkulation, Plantafel) und
  tatsächliche Zeit (gebucht, davon freigegeben) werden nie vermischt; die Ist-Personalkosten rechnen mit allen gebuchten Stunden und benennen die ungeprüften.
- Oberfläche: `ArtikelPage` (Suche, Dialog, CSV-Import mit Vorschau), `EingangsrechnungenPage` (Liste, Dialog mit Upload/Vorschlag/Aufteilung/Aktionen,
  `?id=` öffnet direkt), `NachkalkulationPage` (Übersicht, aufklappbar), `components/material/{MaterialTab,NachkalkulationTab}` als Projekt-Reiter,
  Angebotspositionen „Aus Artikel übernehmen“. Tests `tests/test_material_20261024.py` (3 Tests).
- Offen: Lager (Bestände, Ein-/Ausgang, Inventur, Reservierung), DATANORM-Import (Stufe F), Positionen der Eingangsrechnung einzeln erfassen, OCR für
  Bild-/PDF-Belege ohne E-Rechnung (Stufe H, Feature-Flag), Teilzahlungen (Stufe E).

## 1i. Stufe E – Rechnungsprozesse (24.10.2026)

- Alles in `invoices` mit `art` monat|pauschal|abschlag|schluss|storno|gutschrift; Nummern über `firmen.rechnungszaehler` wie bisher. Nicht-Monatsrechnungen
  tragen `month = -seq` (der eindeutige Index Firma/Projekt/Jahr/Monat bleibt), ihre Zeilen liegen in `extras` (text, quantity, unit, unit_price, amount),
  die PDF/XML schon kennen. Neue Felder: `faellig_am` (beim Festschreiben gesetzt), `zahlungen[]`, `bezahlt_betrag`, `mahnstufe`, `mahnungen[]`,
  `versand[]`, `abschlag_nr`, `kumulativ`, `leistungsstand_prozent`, `vorherige[]`, `abschlaege_netto`, `storno_von`, `storno_id`/`storno_nummer`,
  `leistung_von/bis`, `rechnungstext`, `auftrag_nummer`. Status zusätzlich `teilbezahlt` (aus den Zahlungen abgeleitet).
- `rechnungslauf.py`: `zeilen_summen` (Netto/USt/Brutto freier Zeilen, § 19/§ 13b), `auftragsbasis` (Auftragswert + freigegebene Nachträge),
  `abschlag_zeilen` (kumulativ: Leistungsstand × Basis − gestellte Abschläge; pauschal: Betrag), `schluss_zeilen` (Auftragspositionen + Nachträge −
  Abschläge, informativ „offen aus Abschlägen“), `storno_zeilen` (Gegenbuchung), `zahlungsstand`, `faellig_am`, `mahn_regeln`/`mahn_vorschlag`
  (Stufe, Frist, jetzt fällig), `mahn_text`, `mahn_gebuehr`. `erechnung.rechnungsdaten` kennt `art`, `art_name`, `typecode`, `vorherige`;
  `cii_xml` schreibt den Typcode und `InvoiceReferencedDocument`; `rechnung_pdf` überschreibt Titel, Betragszeile und Zahlungssatz je Art.
- API (`routes/rechnungslauf.py`): `GET /api/projekte/{id}/abrechnung`, `POST /api/rechnungen/auftrag` (art pauschal|abschlag|schluss,
  `leistungsstand_prozent` oder `betrag_netto`, `nur_pruefen` für die Vorschau; 409 bei vorhandener Schlussrechnung, Abschlagsarten werden nicht
  gemischt), `POST /api/rechnungen/{id}/storno` (nur ausgestellte, nie Storno vom Storno), `POST /api/rechnungen/gutschrift`,
  `POST/DELETE /api/rechnungen/{id}/zahlungen[/{zid}]`, `POST /api/rechnungen/{id}/senden`, `GET /api/mahnwesen`, `POST /api/rechnungen/{id}/mahnung`
  (stufe = nächste Stufe, `erzwingen` für die Frist, `per_email`, `gebuehr`, `text`), `GET /api/rechnungen/{id}/mahnung/{stufe}.pdf`. Bestehend
  angepasst: Liste liefert `art_name`, `status_name`, `bezahlt_betrag`, `offen_betrag`, `mahnstufe`; `PUT /{id}` Status bezahlt legt die Restzahlung an;
  `GET /{id}/daten` liefert für Nicht-Monatsrechnungen `server_pdf: true`. Firmenregeln `firmen.mahnwesen` (FirmaIn-Validator). Mail-Arten
  `rechnung`, `mahnung`; Mahn-PDFs unter `DATA_DIR/mahnungen/<firma>/`.
- Oberfläche: `RechnungenPage` (Art-Badges, vier Statuskacheln, Server-PDF für neue Arten, Zahlungen, Senden, formaler Storno, Gutschrift),
  `components/rechnungen/{RechnungDialoge,AbrechnungTab}` (Projekt-Reiter „Abrechnung“ mit Abschlag-Dialog und Vorschau), `MahnwesenPage` mit Regeln.
  Tests `tests/test_rechnungslauf_20261024.py` (3 Tests).
- Bewusst nicht: automatische Mahnläufe, Verzugszinsen, Inkasso-Übergabe, Skonto-Automatik, Sammelrechnungen über mehrere Projekte, Zahlungsabgleich
  per Kontoauszug (CAMT/MT940) – offen für spätere Stufen.

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
- Benachrichtigungen In-App und (für Einladungen, Nachweise, Einsatz-Erinnerungen) per E-Mail; „bald endende Frist“ ohne Zeitplaner; kein Push.
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
