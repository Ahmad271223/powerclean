# Stundenzettel Pro: Ausschreibung, Kommunikation, Vergabe und vollständige ZIP-Projektakte

Stand 23.10.2026. Architektur- und Implementierungsspezifikation, **noch keine produktiv implementierte Funktion**. Grundlage: main f487941c15c2daafd6c34318b8fdb581ff18488c.

## 1. Produktziel
Ein Auftraggeber/Generalunternehmer (z. B. ein großer GU) schreibt Gewerke aus; Handwerksbetriebe erhalten Einladungen oder entdecken öffentliche privatwirtschaftliche Ausschreibungen, können direkt in der App Fragen stellen und Angebote einreichen. Projektleiter werten Gebote aus und erteilen Aufträge. Aus dem Zuschlag entsteht eine beauftragte Projektbeteiligung, kein isoliertes zweites Projekt. Die vollständige Kette aus Ausschreibung, Angebot, Rückfragen, Nachrichten, E-Mail-Benachrichtigungen, Auftrag, Ausführung, Fotos, Zeiten, Abnahmen und Rechnungen wird im ZIP-Projektarchiv nach Berechtigung exportiert.

Private gewerbliche Ausschreibungen sind der erste Anwendungsfall. Öffentliche Vergabeverfahren erfordern separat geprüfte technische und rechtliche Anforderungen, besonders Fristen und Geheimhaltung.

## 2. Navigation und einfache Benutzeroberfläche
GU-Projektleiter: Übersicht | Ausschreibungen | Projekte | Nachrichten | Mehr.
Chef Handwerksbetrieb: Übersicht | Ausschreibungen | Projekte | Nachrichten | Rechnungen | Mehr.
Mitarbeiter mobil: Stempeluhr | Meine Einsätze | Projekte | Nachrichten | Profil.
Ausschreibungen für Nachunternehmer: Entdecken / Eingeladen / Meine Angebote / Vergeben.
Ausschreibungen für GU: Entwürfe / Laufend / Prüfen / Vergeben / Archiv.
Jede Ausschreibungskarte: Titel, Gewerk, Ort, Frist, Auftraggeber und eine zentrale Aktion.
Ausschreibungsdetail: Überblick / Unterlagen / Fragen / Angebot (Bieter) oder Bieter & Vergleich (GU).
Angebot in fünf kurzen Schritten: Leistungsumfang / Preise / Anlagen / Prüfung / Einreichen. Ein Entwurf darf jederzeit bearbeitet werden; eine eingereichte Version ist unveränderbar.
Nach Zuschlag erscheint unter Projekte der Reiter Auftrag & Angebot mit Originalfassung, Version, Zuschlag und Vertrag; vorbestehende Ausschreibungsunterlagen und Kommunikation werden nicht erneut hochgeladen.
Posteingang: Ungelesen / Ausschreibungen / Bauprojekte / Entscheidungen; Suche nach Person, Firma und Vorgang. Keine technischen Audit-Logs als Nutzerchat darstellen.
Projektansicht modularisieren: Übersicht / Kalender / Kommunikation / Dokumente / Auftrag & Angebot / Abschluss. Auf dem Handy primär eine einfache Tageserfassung.

## 3. Organisations- und Zugriffsmodell
Der bestehende Code verwendet einen firmenspezifischen Nutzer mit fixer Rollen-Hierarchie. Für gemeinsame GU-Nachunternehmer-Projekte braucht es:
- organizations (bestehende firmen als Organisationen migrieren, IDs bewahren)
- organization_memberships (user_id, organization_id, role, active), ein Nutzer kann explizit mehreren Firmen angehören
- capabilities: company_manage, tender_create, tender_invite, bid_submit, bid_evaluate, award_approve, project_manage, time_capture, invoice_manage, archive_export, mail_settings
- project_participants(project_id, organization_id, lot_id, permissions, status)
- tender_participants(tender_id, organization_id, invite_state, access_scope)
- document_acl(document_id, owner_org_id, allowed_org_ids, purpose, scope, classification)
Zugriff wird serverseitig pro Organisation, Projekt, Los, Dokument und Thread geprüft. Globale Rollen reichen nicht. Eine leere Mitarbeiter-Zuordnung darf nicht stillschweigend Zugriff für sämtliche Nutzer bewirken.
Angebotsrevisionen anderer Bieter dürfen nie an Konkurrenten gelangen. GU-intern unterscheidet sich der Zugriff auf eingereichte/noch versiegelte Angebote vom Zugriff auf allgemeine Tender-Informationen.

## 4. Fachliches Datenmodell (MongoDB)
tenders: id, owner_org_id, project_id, title, description, procurement_mode, visibility, status, question_deadline, bid_deadline, opening_at, timezone, published_revision.
tender_lots: id, tender_id, trade, quantity_items, schedule, site, contract_conditions.
tender_document_versions: tender_id, document_id, revision, sha256, storage_key, published_at, visibility.
tender_invitations: tender_id, bidder_org_id, sender_user_id, status, created_at, responded_at.
tender_questions: tender_id, bidder_org_id, visibility private/shared_anonymized, body, answer, created_at, answered_at.
bids: id, tender_id, lot_id, bidder_org_id, status, current_revision_id.
bid_revisions: bid_id, revision, price_net, tax, positions, execution_schedule, reservations, attachment_ids, sha256, submitted_at, submitted_by, receipt_id.
award_decisions: tender_id, lot_id, winning_bid_revision_id, decided_by, reason, approval_events, decided_at, state.
contracts: project_id, lot_id, contractor_org_id, award_id, document_version, effective_at, status.
communication_threads: id, context_type, context_id, participants, audience, visibility, state.
communication_messages: id, thread_id, sender_user_id, sender_org_id, body, attachment_ids, created_at, immutable_version.
message_events: message_id, actor, event, occurred_at, request_id, details (append-only).
notification_outbox: event_id, recipient_id, template_id, channel, state, attempts, next_retry_at, provider_message_id.
email_delivery_events: notification_id, provider_event_id, occurred_at, state, reason.
archive_jobs: project_id, requester_org_id, requested_by, categories, access_scope, status, snapshot_at, progress, storage_key, sha256, expires_at.
retention_policies, legal_holds, deletion_jobs: reference_id, owner_org_id, data_category, eligibility, deadline, approvals.
audit_events: versionierte Geschäftsereignisse; keine ungefilterten sensiblen Details in Webhooks.

Nötige Unique-Indizes: Bid (tender_id, lot_id, bidder_org_id), BidRevision (bid_id, revision), ProjectParticipant (project_id, organization_id, lot_id), Invitation (tender_id, bidder_org_id), NotificationOutbox (event_id, recipient_id, channel). Weitere Indizes für organization/status/deadline, project messages by thread/date, pending emails by retry date. Sicherheitskritische Indizes müssen beim Start verbindlich vorhanden sein.

## 5. Zustandsabläufe
Ausschreibung: draft → published → bidding_closed → evaluation → awarded/partially_awarded/cancelled → archived.
Einladung: invited → viewed → interested/declined → submitted.
Angebot: draft → submitted → superseded/withdrawn/awarded/rejected. Jede Einreichung erzeugt eine neue unveränderliche Revision.
Zuschlag: selected → approvals_pending → award_sent → contractor_accepted/declined → contract_active. Bei Ablehnung keine automatische Projektbeteiligung.
Projekt: planned → active → on_hold → completed → archived.
Archiv: queued → generating → ready/failed → download_confirmed → temporary_copy_expired. Download darf niemals den Originalbestand löschen.
Jeder Statuswechsel besitzt UTC-Zeit, Akteur, Organisationskontext, Idempotency-Key und Audit-Ereignis.

## 6. Firmenkontakt, Chat und E-Mail-Nachweis
- In der Ausschreibung sind private 1:1-Bieterthreads strikt von gemeinsamen anonymisierten Q&A getrennt. Nachrichten an alle Bieter sind eine bewusste separate Aktion des GU.
- Nach Vergabe existieren Projektthreads, deren Teilnehmer auf beauftragte Firma, GU und ausdrücklich freigegebene Rollen begrenzt sind. Der vorherige Bieterthread bleibt als Historie archiviert.
- Eine Nachricht wird zuerst persistent und mit Outbox-Ereignis gespeichert, dann erst per separatem Worker benachrichtigt (Transactional Outbox). Kein E-Mail-Send direkt im HTTP-Request.
- E-Mail-Provider mit SPF, DKIM, DMARC, Template-Versionen, Delivery-Webhooks und Retry/Dead-Letter. Versandstatus unterscheiden: serverseitig gespeichert, an Provider übergeben, Provider akzeptiert, zugestellt, fehlgeschlagen, gelesen (letzteres nicht belastbar).
- Jede Einladung, Einreichung, Rückfrage, Antwort, Änderung der Unterlagen, Friständerung, Zuschlag, Absage und projektbezogene Entscheidung erzeugt In-App-Benachrichtigung und gemäß Empfängerpräferenzen E-Mail.
- Sicherer Default: Benachrichtigung enthält Projekt, Vorgang, Absender, Zeitpunkt und zeitlich begrenzten App-Link; Angebotspreise, Personalakten und vertrauliche Anhänge **nicht** ungefragt als unverschlüsselter E-Mail-Anhang.
- Firma kann für berechtigte Nachrichten eine ausführliche E-Mail-Kopie konfigurieren. Empfängerverifikation, Klassifizierung, Dokumentenrechte, Anhanglimit und Datenminimierung vorher prüfen.
- Für Nachweis optional EML-Fassung, Message-ID, UTC-Sendezeit, Empfänger, Body-Hash, Provider-Events, DKIM-/Transportheader soweit vorhanden und nachweislich eingegangene Bestätigungen archivieren. Ein gewöhnliches versendetes E-Mail ist nicht automatisch ein qualifizierter elektronischer Zustellnachweis.
- E-Mail-Antworten in die App importieren erst in Phase 2 (reply address, Absenderprüfung, Anhangsprüfung, Rechtemodell, Spamfilter). Standardantwort in der App.

## 7. Zuschlag → Projekt
Eine bestätigte Vergabe fixiert gewinnende Angebotsrevision, Ausschreibungsversion, Los, Preis- und Leistungsumfang und erteilt beauftragtem Unternehmen projektbezogene Rechte. Das Projektverhältnis entsteht nur einmal; wiederholte Netzwerkaufrufe müssen idempotent sein. Ein GU kann viele Projektleiter und Firmen je Projekt verwalten. Auftragnehmer dürfen nur ihre eigenen Angebote, beauftragten Lose und freigegebenen Nachrichten/Dokumente sehen. Keine Konkurrenzangebote durch Projektkalender, Rechnungs-API, Dateilinks, Suche oder ZIP.

## 8. ZIP-Projektakte
Erzeuge ein **berechtigungsspezifisches** Archiv, dessen Manifest jede Datei mit Quelle, Revision, UTC-Zeit, Hash und exportierender Organisation auflistet:
00_INDEX/Projektuebersicht.pdf, Dokumentenverzeichnis.pdf, manifest.json, pruefsummen.sha256
01_AUSSCHREIBUNG/Einladung/, Leistungsverzeichnis/, Plaene/, Unterlagenversionen/
02_UNSER_ANGEBOT/Angebot_Revisionen/, Anlagen/, Einreichungsquittung/
03_VERGABE_AUFTRAG/Zuschlag.pdf, Auftrag.pdf, Vertrag/, Aenderungen/
04_KOMMUNIKATION/Vor_Vergabe/Chronologie.pdf, Nachrichten.jsonl, Mailnachweise/, Bauphase/Chronologie.pdf, Nachrichten.jsonl, Anlagen/, Zustellstatus.csv
05_AUSFUEHRUNG/Fotos/<Mitarbeiter>/<Datum>/, Stundenzettel/<Mitarbeiter>/<Datum>/, Taetigkeiten/, Berichte/, Checklisten/
06_ABNAHMEN/Unterschriften/, Abnahmen/, Maengel/
07_RECHNUNGEN/Rechnungen/, E_Rechnung/, Nachtraege/
08_ABSCHLUSS/Abschlussbericht.pdf, Vollstaendigkeitsbericht.pdf

Eine Auftragnehmer-ZIP enthält nur dessen eigenes Angebot und eigene freigegebene Kommunikation. GU-Bieter-Gesamtakten haben ein anderes, besonders berechtigtes Exportprofil. Fehlende Quellen müssen explizit im Vollständigkeitsbericht stehen, nicht stillschweigend als vollständig gelten.
Archive asynchron per dauerhafter Queue und separatem Worker erzeugen; Streaming/temporäre Dateien, Größenquoten, Integritätsprüfung, Malware-Prüfung von Anhängen, ZIP-Slip-Vermeidung. ZIP standardmäßig 7 Tage als temporäre Downloadkopie. Originale behalten ihre eigene Aufbewahrungsregel. Nach Download: explizite Empfangsbestätigung möglich; kein Auto-Delete.

## 9. Retention und Rechtssicherheit
Pro Datenklasse eigene Fristen, vertragliche Aufbewahrung, rechtliche Sperren, Firmenaustritt und Projektschluss berücksichtigen. Projektablauf + 90 Tage ist eine sinnvolle Bedien-/Exportphase, **keine allgemeine rechtliche Löschfrist**. PDF-Angebot, Zuschlag, Vertrag und Rechnungen können länger notwendig sein; reine Chat-Benachrichtigungen können anders behandelt werden. Löschungsprozess immer separater Auftrag mit Prüf- und Sperrstatus. DSGVO Zweckbindung/Speicherbegrenzung beachten, Auftragsverarbeitungsverträge für Mail- und Speicheranbieter. Kein rechtssicherer Nachweis allein durch Standard-E-Mail behaupten. Öffentliche Vergaben brauchen zusätzlich gesonderte Compliance-Prüfung nach anwendbarem Vergaberecht.

## 10. Repo-spezifischer Umbauplan
backend/auth.py: organization_memberships + aktiver Kontext statt fixer Einzelfirma-Rolle.
backend/gemeinsam.py: projekt_sichtbar und projekt_leitung auf Teilnehmer-/Dokumentenfähigkeiten umstellen.
backend/routes/projekte.py: gemeinsame Projekthülle und Los-/Firmenbeteiligungen; archivierbar statt pauschal kaskadierend löschen.
backend/routes/rechnungen.py: Vertrags-/Losbezug, Entwurf/ausgestellt/bezahlt und revisionssichere Belege; kein stillschweigendes Neu-Berechnen ausgestellter Rechnungen.
backend/routes/zeiten_routes.py: P0-Stempelverlust beheben, sichere Idempotenz und Benutzerrollen.
backend/routes/exporte.py: asynchrones Archivmodul statt großer synchroner Exportantworten.
backend/db.py + server.py: neue Collections/Indizes/Router/Worker.
frontend/src/App.jsx: geschützte neue Routen für Ausschreibungen, Nachrichten, Vergabe und Archiv.
frontend/src/components/Layout.jsx: rollenspezifische Navigation nach Fähigkeiten; maximal vier primäre mobile Tabs.
frontend/src/pages/ProjektPage.jsx: großen Kalender-/Akte-/PDF-Monolithen in übersichtliche Projektmodule trennen, mobile Zeiterfassung verbessern.
frontend/src/pages/RechnungenPage.jsx: Rechnungsstatus vereinfachen und Pflichtschritte erkennbar machen.
frontend/src/pages/FirmaPage.jsx: technische Konfiguration hinter «Erweitert» statt Firmenstammdaten.
frontend/src/pages/ExportePage.jsx: Lohn/DATEV/Monatsabschluss getrennt von Projektarchiv.
Neue getrennte Module: tenders, invitations, bids, awards, company_directory, conversations, notifications, archive_worker, retention.

## 11. Sicherheits- und Lasttests (Go-live-Gates)
- Mehrere GUs und mehrere Bieter, wechselnde Projektleiter: kein Cross-Org-Leak.
- Bieter A darf zu keinem Zeitpunkt Angebot B lesen, auch nicht in Suchen, PDFs, ZIP und Dateidownloads.
- Unveränderbarkeit eingereichter Angebotsrevisionen, eindeutiger Fristzeitpunkt, atomarer Zuschlag, idempotente Wiederholungen.
- E-Mail-Provider down und Worker-Restart: Nachricht bleibt gespeichert, Outbox versucht wieder, keine unbemerkten Verluste.
- E-Mail-Zustellstatus ≠ rechtssicherer Zugang.
- Richtige Verknüpfung nach Auftragnehmerbestätigung; Nachträge/Abnahmen und gebuchte Zeiten korrekt dem Los zugeordnet.
- Berechtigungsentzug sofort in API und alten Downloadlinks wirksam.
- ZIP mit 10.000 Fotos und 100 gleichzeitigen Exporten ohne unkontrollierte RAM-Nutzung.
- 20 Fotos je Mitarbeiter/Arbeitstag atomar und firmenübergreifend konsistent.
- Rückkehr zum Projekt nach Browserwechsel ohne Timer-Reset und ohne Zeitverlust.
- Restore von Datenbank und Objektspeicher erfolgreich; Löschprozess respektiert Legal Holds.
- Mobile E2E für Mitarbeiter, Handwerkschef und GU-Projektleiter.
Ziel: realistische 5.000-Firmen-Datenbasis, Testspitzen 500/1000/5000 parallele Aktionen, gemessene P95/P99-Latenzen, Fehlerquote und DB-Slow-Queries. Messwerte nicht simulieren.

## 12. Lieferphasen
0. Bestehende P0-/Sicherheitsprobleme und Datenverlustpfade beheben.
1. Organisationen, Rollen und sichere Beteiligungen, Bestandsmigration (Feature Flag).
2. Private Ausschreibungen, Einladungen, strukturierte Angebote/Revisionen, Empfangsbestätigungen.
3. Kanalsicherer Chat, Posteingang, persistente E-Mail-Outbox und Provider-Ereignisse.
4. Vergabevergleich, Freigabe, Zuschlag, Vertrags-/Projektbindung.
5. Projektmodule und ZIP inkl. eigener Ausschreibung, eigenem Angebot, Antworten, Nachrichten, Fotos, Stundenzettel und Rechnungen.
6. Ausfallsichere Worker, Aufbewahrung, Legal Holds, Datenschutz, Tests und kontrollierter Rollout.
7. Öffentliche Vergabe nur nach eigener rechtlich/technischer Abnahme.

## 13. Abnahmekriterium
GU veröffentlicht Ausschreibung und lädt zehn Firmen ein. Zwei Bieter fragen privat, einer stellt eine freigegebene allgemeine Frage. Beide reichen revisionsgesicherte Angebote vor Frist ein. GU kann alle berechtigten Angebote korrekt prüfen und einem Bieter beauftragen; Verlierer erfährt keine vertraulichen Gebotsdetails. Beauftragte Firma findet Angebot, Zuschlag und Vertrag direkt in ihrem Projekt. Während des Bauvorhabens bleiben Chat, Fotos, Arbeitszeiten, Nachträge, Abnahmen und Rechnung zugeordnet. Eine vollständig erzeugte ZIP-Datei enthält nur berechtigte Unterlagen samt Nachrichtenevents und E-Mail-Sendehistorie. Alle Vorgänge bleiben nach Seitenwechsel und Neustart erhalten.
