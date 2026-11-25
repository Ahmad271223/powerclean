# Test-App: installieren, Mitarbeiter einladen, Sprache und Push einschalten

Kurzanleitung für den Inhaber. Eine App für alle: iPhone über **TestFlight**, Android über den **internen Test** im Play Store.
Alle Geräte sprechen mit demselben Server – Chef mit iPhone und Mitarbeiter mit Android passen zusammen.

## 1. Die Test-App aufs eigene iPhone

1. Im App Store die App **TestFlight** (von Apple, kostenlos) installieren.
2. In [App Store Connect](https://appstoreconnect.apple.com) → *Apps* → *Stundenzettel Pro* → *TestFlight* → *Interne Tests* →
   Gruppe anlegen (z. B. „Büro“) → dich selbst als Tester hinzufügen. Interne Tester müssen in *Benutzer und Zugriff* stehen (bis 100 Personen).
3. Auf dem iPhone die E-Mail „Du wurdest eingeladen …“ öffnen → *In TestFlight ansehen* → *Installieren*.
4. App öffnen, mit E-Mail und Passwort des Firmenkontos anmelden, Mitteilungen **erlauben** (sonst keine Push-Nachrichten).

Neue Test-Versionen erscheinen automatisch in TestFlight; jede Version läuft 90 Tage.

## 2. Mitarbeiter einladen

Zwei Schritte – erst das Konto, dann die App:

1. **Konto:** In Stundenzettel Pro → *Mitarbeiter* → *Einladen* → Name und E-Mail. Der Mitarbeiter bekommt einen Einladungslink,
   öffnet ihn und legt sein Passwort fest. (Ohne E-Mail-Versand am Server: Link in der Mitarbeiterliste kopieren und z. B. per WhatsApp schicken.)
2. **App aufs Handy:**
   - **iPhone:** In App Store Connect → *TestFlight* → *Externe Tests* → Gruppe „Mitarbeiter“ → *Öffentlichen Link aktivieren*.
     Den Link schicken; der Mitarbeiter installiert TestFlight und tippt den Link an. Die erste externe Version prüft Apple kurz
     (Beta-Review, meist unter 24 Stunden). Mitarbeiter brauchen **keinen** Zugang zu App Store Connect.
   - **Android:** [Play Console](https://play.google.com/console) → *Stundenzettel Pro* → *Testen* → *Interner Test* → Tester (E-Mail-Liste) →
     Teilnahme-Link schicken. Mitarbeiter öffnen den Link mit ihrem Google-Konto und installieren die App aus dem Play Store.
3. Mitarbeiter melden sich in der App an und **erlauben Mitteilungen**. In der Plantafel steht dann bei ihren Einsätzen „zugestellt“
   statt „ohne App“.

## 3. Einteilung per Sprache einschalten

Auf dem Server (`.env`, danach neu starten):

```
FEATURE_SPRACHPLANUNG=1
```

Dann erscheint in der Plantafel der Knopf **„Per Sprache“**. Beim ersten Tippen auf das Mikrofon lädt das iPhone das Sprachmodell
(iPhone 15 Pro und neuer: 632 MB, ältere: 216 MB) – **am besten im WLAN**. Danach läuft die Erkennung ohne Netz auf dem Gerät.

- Mikrofon **gedrückt halten**, sprechen, loslassen. Z. B. „Teile Nils an die Hauptstraße ein, Projekt Müller, 7 bis 16 Uhr die ganze Woche“.
- *Vorschlag erstellen* → Karte prüfen, Rückfragen antippen, Felder antippen zum Ändern → **Einteilen & … benachrichtigen**.
- Gespeichert wird erst beim Bestätigen. Die Aufnahme verlässt das Handy nie und wird nicht gespeichert.

Optional, KI auf dem Server für Android und ältere iPhones (sonst feste Regeln): `FEATURE_KI=1` und `MISTRAL_API_KEY=…`.
**Vorher den Vertrag zur Auftragsverarbeitung mit Mistral abschließen** – dann verlässt der getippte bzw. erkannte Satz den Server.

## 4. Push-Nachrichten einrichten (einmalig)

**iPhone (Apple):**
1. [developer.apple.com](https://developer.apple.com/account) → *Certificates, IDs & Profiles* → *Keys* → **+** → Name „Push Stundenzettel“,
   Haken bei *Apple Push Notifications service (APNs)* → *Continue* → *Register* → **.p8 herunterladen** (gibt es nur einmal!).
2. Auf dem Server ablegen (z. B. `/geheim/AuthKey.p8`) und in die `.env`:
   ```
   APNS_TEAM_ID=78MQGF36BD
   APNS_KEY_ID=<Key ID von der Seite>
   APNS_SCHLUESSEL_DATEI=/geheim/AuthKey.p8
   ```

**Android (Google Firebase, kostenlos):**
1. [console.firebase.google.com](https://console.firebase.google.com) → Projekt anlegen → *Android-App hinzufügen* mit Paketname
   `de.stundenzettelpro.app` → **google-services.json** herunterladen → nach `stundenzettel-pro/frontend/android/app/` legen
   (gehört nicht ins öffentliche Repo, als GitHub-Secret für den Build hinterlegen).
2. *Projekteinstellungen* → *Dienstkonten* → *Neuen privaten Schlüssel generieren* → JSON auf den Server und in die `.env`:
   ```
   FCM_DIENSTKONTO_DATEI=/geheim/firebase-dienstkonto.json
   ```

Ohne diese Schlüssel läuft alles weiter – die Plantafel zeigt dann „Push nicht eingerichtet“, Mitteilungen gibt es in der App und per E-Mail.
Push-Texte enthalten nur Projekt, Straße, Tage und Uhrzeit; mit `PUSH_OHNE_DETAILS=1` nur „Neue Einteilung – in der App ansehen“.

## 5. Kurz testen (Checkliste)

- [ ] Chef: anmelden, Plantafel öffnen, „Per Sprache“ → Modell laden → Satz sprechen → Vorschlag → Einteilen
- [ ] Mitarbeiter (iPhone **und** Android): Push kommt an, Antippen öffnet den Einsatz, „Gelesen & bestätigt“ tippen
- [ ] Chef sieht in der Plantafel: zugestellt → gelesen → ✓ bestätigt
- [ ] Rückfrage bei zwei gleichen Vornamen, Hinweis bei Urlaub/krank, Sperre bei Doppelbelegung
- [ ] Ohne Netz: Stempeluhr geht weiter, Spracherkennung geht weiter (Vorschlag braucht Netz)
