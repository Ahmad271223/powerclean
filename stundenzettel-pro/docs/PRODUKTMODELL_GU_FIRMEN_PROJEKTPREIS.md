# Produktentscheidung: Handwerksfirmen versus Generalunternehmer — Rollen, Logins und 50,99-€-Projektabo

Status: verbindlicher Architektur- und Preismodellvorschlag, **keine bereits implementierte Funktion**. Basis: main f487941 vom 23.10.2026.
Ergänzt die Dokumente ARCHITEKTUR_AUSSCHREIBUNG_CHAT_PROJEKTARCHIV.md und APP_UX_AUDIT_UND_UMBAU.md.
**Diese Kundentyp-Trennung hat Vorrang**, wo frühere Konzepte normale Firmen zu Ausschreibungserstellern gemacht haben.

## 1. Kernentscheidung: Kundentyp und Rechte sind getrennt
Die Produktkategorie einer Organisation ist SMALL_BUSINESS oder GENERAL_CONTRACTOR (ggf. später ENTERPRISE_OWNER).
Eine Funktion wird durch Subscription-Entitlement + User-Capability + Projektmitgliedschaft + Ressourcensichtbarkeit genehmigt.
Der Firmenname oder ein selbstgewähltes Häkchen ist **kein** hinreichender Nachweis für Enterprise-Freigaben.
Normale Firmen können eigene Einsätze/Projekte anlegen, Subunternehmer im freigegebenen Firmenverzeichnis suchen, Kontakte anfragen und private, direkte Angebotsanfragen senden; sie können **keine formalen, sichtbaren Ausschreibungen veröffentlichen**, keinen Bietervergleich einer Ausschreibung steuern und keine Vergabezuschläge erteilen.
GU können nach Enterprise-Freischaltung formale Ausschreibungen erstellen, Lose veröffentlichen, Firmen einladen, Angebote prüfen, Zuschlag erteilen und GU-Projektstände verwalten.
Normale Firmen können ohne zusätzliche Publikationsrechte auf GU-Ausschreibungen antworten, Angebote einreichen und nach Zuschlag mitarbeiten.
Optional: GU kann Auftraggeberrolle in mehreren Projekten vergeben, ohne die Nutzerrolle global zu erhöhen.

## 2. Identität, Unternehmen, Projektleiter
- Ein realer Mensch = ein persönlicher Benutzeraccount mit verifizierter E-Mail, Passwort/MFA oder später SSO; keine gemeinsamen Logins wie projektleiter@goldbeck.de.
- GOLDBECK erhält **ein** verifiziertes Unternehmenskonto mit eigener Firmen-ID, zentralem Vertrag/Billing und Unternehmensadmins.
- GU-Firmenadmin lädt einzelne Projektleiter per individueller E-Mail ein, weist ggf. mehrere Projekte zu.
- Jeder Projektleiter hat **ein einziges Login für alle seine berechtigten Projekte**, nicht ein eigenes Login pro Baustelle. Bei Unternehmenswechsel oder Sperrung werden Mitgliedschaft und Projektrollen widerrufen.
- Auftragnehmerchef besitzt seine eigene Firma und Nutzer; Auftragnehmers Firmenmitarbeiter erhalten Einladungen in dessen Unternehmen und werden nach Bedarf GU-Projekt zugeordnet.
- Benutzt eine Person mehrere Organisationen, wählt sie nach Login den aktiven Firmenkontext; API validiert ihn serverseitig für jede Anfrage.
- Ein Nutzer wird nicht mehrmals berechnet, nur weil er an mehreren Projekten arbeitet; Sitz-Zählung je zahlender Organisation und zugeordnetem eigenem Team.
- Projektleiterkonten sind projektbezogen beschränkt: Projektleiter A darf nur Baustellen A/B sehen, PM B nur C, außer expliziter Freigabe. Zentrale Enterprise-Admins sehen erlaubte Firmenprojekte und Billing. Ein GU-Lesekonto darf keine Preis-/Vergaberechte allein aus Rolle "buero" erhalten.
- Für Großkunden SSO/SAML/OIDC, MFA, Audit und SCIM-Provisioning als Ausbaustufe; für den ersten Piloten individuelle Einladung und MFA.

## 3. Web versus mobile App
Ein und derselbe Benutzeraccount / Backend; **keine separaten Web- und App-Logins oder unterschiedliche Datenbestände**.
Web (Desktop) für GU: Projekt erstellen, Abrechnung, Ausschreibungen, Leistungsverzeichnisse, Bieter vergleichen, Benutzerrollen/Projektleiter verwalten, Chat, Aufgaben/Termine, Abschluss/ZIP.
GU mobile App: Projekte ansehen, Projektchat, Fotos/Dokumente/Abnahmen, Freigaben und offene Aufgaben; komplexe Angebotsvergleiche optional Web-only UX, aber dieselbe serverseitige Berechtigung.
Web für normale Firma: Firmenverwaltung, Mitarbeiter, Stundenzettel, Kunden, eigene Projekte, Rechnungen, Subunternehmen finden, auf erhaltene Ausschreibungen antworten, Projektchat, eigene ZIP.
App normaler Mitarbeiter: Start/Pause/Stop, Tagesnotiz, Fotos bis Limit, Einsatz/Projekt, Schicht und Chat.
App Unternehmer: kompakte Verwaltungsaktionen sowie Mitarbeiterfunktionen.
Tabbar maximal vier Hauptpunkte + "Mehr", auf Desktop linke Menüführung mit rollenbasierten Modulen.

## 4. Zwei Projektarten, gemeinsame Verknüpfung
A. COMPANY_JOB: normales Firmenprojekt eines Handwerkers; zählt **nicht** als kostenpflichtiges GU-Projekt. Bestehendes backend/projects mit firma_id möglichst unverändert betreiben.
B. GU_CONSTRUCTION_PROJECT: kostenpflichtiges übergeordnetes Bauvorhaben mit owner_org_id und optional vielen Ausschreibungen/Losen sowie Beteiligungen. Genau **ein** aktives GU-Projektabo je Bauvorhaben, nicht je Los/Angebot/Bieter.
Ein GU-Projekt hat viele Tenders/Lots, PM-Assignments und projektteilnehmende Firmen.
Jede Auftragnehmerfirma erhält einen eigenen, firmeneigenen Arbeitsbereich/Unterprojekt (COMPANY_JOB oder company_project_workspace, linked_gu_project_id + awarded_lot_id). Eigene Personal-/Lohndaten, interner Chat, Kalkulationspreise und interne Rechnungsentwürfe bleiben bei der Firma.
GU sieht nur explizit geteilte Projektfotos, Fortschritte, Abnahmeunterlagen, vertragliche Angebote und freigegebene Rechnungen – keine vollständige Fremdfirmen-Datenbank.
Die GU-ZIP enthält dokumentierte, berechtigte Gesamtprojektunterlagen; die Auftragnehmer-ZIP nur eigene/vertraglich geteilte Informationen.

## 5. Unternehmensverzeichnis und Subunternehmen-Finden
Normale Firma sieht nur öffentlich opt-in freigegebene Firma: Gewerke, Einsatzgebiete, öffentliches Profil, Kontaktoption, freiwillige Verfügbarkeitsinformation.
Keine privaten Kundenlisten, Mitarbeiter-Lohndaten, Projektbudgets, fremde Angebotskalkulationen oder persönliche Kontaktdaten ohne Freigabe.
"Anfrage senden": privat, direkt, ggf. mit Anfrage-PDF und optional Angebot der angefragten Firma. Kein öffentlicher Bietervergleich, keine formale Ausschreibung.
GU-Firma kann aus dem Verzeichnis Einladungen für ihre formalen Ausschreibungen generieren.
Verifikation von Unternehmen/Projektleitern vor großen GUs; Missbrauchsschutz bei Massennachrichten/Spam.

## 6. Abrechnung: GU 50,99 € netto je aktivem Projekt/Monat
- Default 50,99 EUR zzgl. USt. pro aktivem GU_CONSTRUCTION_PROJECT je Abrechnungsperiode. Preis muss im Checkout vertraglich sichtbar sein.
- Projektentwurf ist kostenlos; erste Veröffentlichung/Einladung oder "Projekt aktivieren" erfordert Zahlungsmethode und explizite kostenpflichtige Aktivierung.
- Ein Projekt darf mehrere Gewerke, Lose, Ausschreibungen, Mitarbeiterzuordnungen und externe Firmen haben, ohne weitere 50,99 € je Los.
- Ein Projekt darf nicht durch kostenlose Kopien derselben Baustelle die Kosten umgehen; Zusammenführung und Anti-Missbrauchsregeln ohne falsche Zusatzabrechnung.
- 1 Projekt = 50,99 €/Monat; 5 Projekte = 254,95 €/Monat; 10 = 509,90 €/Monat; 20 = 1.019,80 €/Monat (netto).
- Abnahme/Beendigung: aktives Abo zum bezahlten Periodenende kündigen; GU-Ansicht danach read-only für definierte vertragliche Archivfrist, Export verfügbar und gesetzlich zu bewahrende Unterlagen separat geschützt. Keine automatische Datenlöschung bei unbezahltem Abo.
- Preis ist für echte Konzernabläufe möglicherweise niedrig: Definiere fair-use für Fototraffic, Exportjobs, und Sonderfeatures; Enterprise-SLA/SSO/Integrationen/hohe Speichervolumen separat anbieten. Preis zum Start als Pilot- oder Basisangebot kennzeichnen, ggf. keine pauschalen 5.000-Firmen-Versprechen.
- Grundsätzlich eindeutiges billing_owner_org_id, provider_subscription_id, project_id, status, current_period_start/end, cancel_at_period_end, idempotency keys, provider webhooks, invoices, refunds/proration policy, payment-failure grace_period.
- Bestehende Firma.plan mit status test/aktiv/gesperrt ist **kein** Projektabo. Aktuell /api/admin/plan nur manuelle Freischaltung. Payment-/Subscriptionmodell muss neu implementiert werden.

## 7. Handwerksfirmen-Abos und Netzwerk-Effekt
Vorgesehener Handwerkerpreis: 4,99 €/Monat inklusive Chef-Account + 3,99 € je zusätzlichem **aktiven bezahlten** Mitarbeiteraccount, sofern Nettopreise so vereinbart.
Wichtig: Ein Unternehmen darf unabhängig vom GU-Projekt sein normales Abonnement haben. Ein MA auf mehreren Baustellen wird einmal je Firma berechnet, nicht je Baustelle.
**Einladung/Bieterportal/Projektgast grundsätzlich kostenlos**: Ein Subunternehmer kann einsehen, antworten, sein Angebot einreichen und im beauftragten GU-Projekt als eingeschränkter Gast wichtige gemeinsame Nachrichten, Vorgänge und Dokumente nutzen, ohne vorab die volle Firmensoftware abonnieren zu müssen.
Upgrade zu kostenpflichtiger Firmensoftware für eigene Stempeluhr, eigene Mitarbeiterkonten, interne Aufträge, volle Fotodokumentation, Rechnungen, eigene Kunden, Exporte und Archivierung.
Dies maximiert Netzwerkverbreitung und verhindert, dass ein GU bei jedem Bieter erst zahlende Accounts erzwingen muss. Alternative Variante als Business-Entscheidung: GU übernimmt Kosten der voll benötigten Ausführungs-Sitze (seat_sponsor = GU), **nie GU und Auftragnehmer für denselben Sitz doppelt abrechnen**.
Keine kalkulatorische Garantie, dass jede eingeladene Firma zusätzlich bezahlt; Conversion separat messen.

## 8. Beispiel vollständig
1. GOLDBECK wird durch Plattform als GU-Organisation freigeschaltet. Admin Julia erhält individuellen Account und verwaltet 3 Projektleiter.
2. Projektleiter Markus wird per E-Mail eingeladen und aktiviert MFA; GU-Admin weist ihm die Baustelle Hannover sowie Dresden zu.
3. Markus erstellt Baustelle Hannover zunächst als kostenlosen Entwurf, veröffentlicht erste Ausschreibung und bestätigt 50,99 € monatliches Projektabo.
4. Er lädt 12 Firmen ein. Diese Firmen nehmen kostenlos Einladungen an, kommunizieren privat und geben eigene Angebote ab.
5. Firma Elektro Müller gewinnt ein Los; Vertragsrevision und Angebot werden eingefroren. Eigener Firmenchef nimmt Zuschlag an. Mitarbeiterin A und Mitarbeiter B erhalten persönliche App-Einladungen im Unternehmenskontext Elektro Müller.
6. Firma Elektro Müller bezahlt 4,99 € Chef + 2 * 3,99 € Mitarbeiter = 12,97 €/Monat, sofern sie Vollfunktionen nutzt; sonst GU-finanzierte eingeschränkte Teilnahme ohne doppeltes Inkasso.
7. Mitarbeiter erfassen Zeiten und Fotos. GU sieht nur für GU freigegebene Ergebnisse. GU und Auftragnehmer nutzen denselben Projektchat-Kontext, interne Teamkommunikation bleibt getrennt.
8. Beim Abschluss exportiert GU ein berechtigtes Gesamtarchiv; Elektro Müller eine eigene Akte mit Einladung, eigenem Angebot, Zuschlag, erlaubten Nachrichten, Fotos, Zeiten, Rechnungen; PDF-Index und SHA-256.
9. Abo-Kündigung beendet neue bezahlte Aktionen nach Ablauf, verliert aber keine gesetzlich/vertraglich erforderlichen Nachweise.

## 9. Benötigte Backend-Änderungen
- users + organization_memberships (Migration aus user.firma_id), role/capability resolution, organization context, verified GU entitlements.
- gu_projects: owner_org_id, status, project_number, billing_subscription_id, project_owner, archive_status.
- project_memberships: org/user bindings, project_id, role, capabilities, state; separate Firmen-Arbeitsbereiche.
- company_directory_profiles: Gewerke, Regionen, Opt-in, Sichtbarkeit; contact_requests mit Abuse/Spam-Limits.
- tender_create/publish API verlangt GU-Tier + specific capability + aktives oder aktivierbares Projektabo; normale Firmen ausdrücklich 403.
- bids für alle berechtigten eingeladene Firmen; aber keinerlei Drittbieter-Leserechte.
- billing_project_subscriptions + billing_seats/entitlements + event ledger; Payment Provider sichere Signaturprüfung, getrennte wiederholbare Webhooks.
- invitation endpoints: GU-PM, Firmen-Einladungen, projektbezogene Teilnehmer und MA-Einladungen separat; gleicher Nutzer kann bestehenden Login wiederverwenden.
- Compliance: DSGVO, Mandantentrennung, eigene Datenhoheit, mögliche VgV-Vergaberegeln nur als separates Produkt.
- Rechte immer serverseitig, niemals nur durch ausblenden von Buttons.

## 10. Nötige Frontend-Änderungen
- Login: ein Account; aktive Organisation bei Mitgliedschaft in mehreren Firmen wählen, sonst direkt dashboard.
- GU Dashboard: "Meine Projekte", "Ausschreibungen", "Angebote prüfen", "Nachrichten", "Projektleiter", "Abrechnung".
- Normalfirma Dashboard: "Heute", "Mitarbeiter", "Eigene Projekte", "Subunternehmen finden", "Eingeladene Ausschreibungen", "Rechnungen".
- GU-Projekt anlegen: Draft → Teamzuweisung → Zahlungsentscheidung → Aktivierung → Ausschreibungen. Zeige Betrag und nächsten Abrechnungstermin vor Aktivierung.
- Normale Projektanlage bleibt einfach und ohne 50,99 € GU-Gebühr.
- Projektleiter einladen: GU-Admin wählt E-Mail, Rolle, zugewiesene Projekte, Option Einladung versenden; PM kann nach Anmeldung nur diese Projekte öffnen.
- Subunternehmen einladen: registrierte Firma wählen oder E-Mail-Einladung; bestehender Firmenaccount bleibt erhalten.
- Neue Seite "Mein Abo & Projekte" trennt aktive GU-Projektabos von Firmen-Mitarbeiterabos. Transparent: wer zahlt welche Gebühr, kein doppelt gebuchter MA.

## 11. Testmatrix (Release-Sperre)
1. Normale Firma darf eigenes Firmenprojekt kostenlos/entsprechend Firmenabo anlegen, aber keine formale Ausschreibung publizieren (API 403).
2. GU kann Draft anlegen, aber ohne bestätigte Zahlung nicht veröffentlichen/einladen. Erfolgreiche Zahlung genau ein Abo je aktivem GU-Projekt.
3. 10 PM in einem GU, jeweils verschiedene Projekte: Lesen/Schreiben korrekt eingeschränkt.
4. PM widerrufen: laufende Sessions und alte Downloadlinks verlieren Zugriff.
5. Ein PM verwaltet zehn GU-Projekte mit **einem** Login; keine doppelte Sitzabrechnung pro Projekt.
6. Zwei Firmen sind Bieter: keine fremden Angebote/Fragen; GU mit Vergaberecht bekommt vorgesehenen Zugriff.
7. Eingeladener freier Gast darf antworten, aber keine Vollfunktionen der Firma ohne Abo.
8. Unternehmensfirma mit bestehendem Abo wird GU-Projekt zugewiesen: keine Doppelabrechnung.
9. Zehn concurrent project activations/payment webhooks: idempotente Abo-Zuordnung, kein Gratiszugriff und keine Doppelzahlung.
10. GU kündigt Projekt: Vergabehistorie und Auftragnehmer-eigene Daten bleiben nach Retention erhalten, kein unbeabsichtigter Löschjob.
11. Web, iOS und Android konsistent und mit demselben Login/Backend; Berechtigungen identisch.
12. 5.000 Firmen, 10.000 Nutzer, 1.000 GU-Projekte als synthetische Testdaten, Last-/Kostenmetriken und Restore prüfen.

## 12. Reihenfolge
(A) Bestehende P0-Zeitverluste/Offline und fehlende ACLs beheben.
(B) Organisations-/Projektmitgliedschaften einführen und alte Firmen migrieren.
(C) GU-Tier, Projektabos/Payment, getrennte Dashboard-Menüs und PM-Einladung.
(D) B2B-Firmenverzeichnis und direkte Kontakte.
(E) GU-Ausschreibung, Bieterportal und Angebotsrevisionen.
(F) Chat, Mail-Outbox, GU-Unternehmensprojekt und Subunternehmer-Arbeitsbereiche.
(G) ZIP-Projektarchive, Retention, große Lasttests.
