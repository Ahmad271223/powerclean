# Stundenzettel Pro im Play Store und App Store

Die Store-App ist eine native Hülle (Capacitor 8) um die gebaute Oberfläche aus `frontend/dist`. Sie liegt als Paket auf
dem Handy und spricht mit **deinem Server** (`VITE_API_URL`). Ein Code, zwei Stores. Alles Native liegt unter
`frontend/android` und `frontend/ios` und gehört ins Repo.

## Was schon eingebaut ist

| Store-Pflicht | Wo |
|---|---|
| Konto in der App löschen (Apple 5.1.1(v), Google „Kontolöschung“) | Profil → „Konto löschen“ (Mitarbeiter), Firma → Lizenz → „Firma und alle Daten löschen“ (Inhaber); `DELETE /api/auth/konto`, `DELETE /api/firma` |
| Datenschutzerklärung und Impressum als Adresse | Server liefert `/datenschutz` und `/impressum` (Texte in `backend/rechtstexte.py`, Anbieterdaten aus `.env`: `ANBIETER_NAME`, `ANBIETER_ANSCHRIFT`, `ANBIETER_EMAIL`, `ANBIETER_TELEFON`) |
| Berechtigungstexte | `ios/App/App/Info.plist` (Standort, Kamera, Fotos, Mikrofon, Sprache), `android/app/src/main/AndroidManifest.xml` |
| Deep Links (QR-Codes am Objekt, Einladungslinks öffnen die App) | Android App Links (`assetlinks.json`), iOS Universal Links (`apple-app-site-association`) – beides liefert der Server, wenn `ANDROID_SHA256` bzw. `APPLE_TEAM_ID` gesetzt sind; App: `src/lib/native.js` |
| Icons und Splash in allen Größen | `npm run assets` (aus `public/icon-512*.png`) |
| Offline-Fähigkeit, keine reine „Website-Hülle“ (Apple 4.2) | Stempeluhr offline, QR-Scan-Start, Kamera, PDFs, Unterschriften – echte App-Funktionen; im Review-Hinweis nennen |
| Export-Compliance (Verschlüsselung) | `ITSAppUsesNonExemptEncryption = false` (nur HTTPS) |
| Signierte Builds | `.github/workflows/stundenzettel-pro-mobile.yml` baut AAB und IPA mit Secrets |

## Einmalig einrichten

1. **Server mit eigener Domain** (siehe README, Docker + HTTPS), `.env` mit Anbieterdaten ausfüllen, `/datenschutz` prüfen.
2. **App-Kennung festlegen**, bevor etwas hochgeladen wird (danach nicht mehr änderbar): `de.stundenzettelpro.app` steht in
   `frontend/capacitor.config.json`, `android/app/build.gradle` (`applicationId`, `namespace`), `android/app/src/main/res/values/strings.xml`
   und `ios/App/App.xcodeproj` (`PRODUCT_BUNDLE_IDENTIFIER`). Zum Ändern: alle vier Stellen oder `npx cap add` neu.
3. **Google Play Console**: Entwicklerkonto (25 $ einmalig), Firma verifizieren (Handelsregister/Gewerbe, D-U-N-S nicht nötig).
   App anlegen → „App-Integrität“ → Play App Signing aktivieren (Google verwaltet den App-Signierschlüssel, du den Upload-Schlüssel).
4. **Apple Developer Program**: 99 $/Jahr, als Firma mit D-U-N-S-Nummer (kostenlos bei Dun & Bradstreet, dauert bis 14 Tage).
   App Store Connect → App anlegen (Bundle-ID wie oben), API-Schlüssel erzeugen (Users and Access → Integrations → App Store Connect API,
   Rolle „Admin“, damit Xcode im Workflow Zertifikate und Profile selbst anlegen darf). Issuer-ID, Key-ID und die .p8-Datei notieren –
   die .p8 gibt es nur einmal zum Herunterladen.
5. **Upload-Keystore für Android** erzeugen (einmal, sicher aufbewahren, Verlust = Problem):
   ```powershell
   keytool -genkeypair -v -keystore upload.jks -alias stundenzettel -keyalg RSA -keysize 2048 -validity 10000
   ```
   Fingerabdruck für App Links: `keytool -list -v -keystore upload.jks -alias stundenzettel` → SHA-256 in `.env` des Servers als
   `ANDROID_SHA256` (Komma-getrennt zusätzlich der Fingerabdruck des Play-App-Signierschlüssels aus der Play Console).
6. **GitHub-Secrets** setzen (Namen im Workflow-Kopf): Server-Adresse, Keystore als Base64
   (`[Convert]::ToBase64String([IO.File]::ReadAllBytes("upload.jks")) | Set-Clipboard`), Apple-Team-ID, API-Schlüssel (.p8-Inhalt), Distribution-Zertifikat (.p12).

## Bauen

**Automatisch (empfohlen):** GitHub → Actions → „Stundenzettel Pro – Store-Builds“ → Run workflow, oder ein Tag pushen:
```powershell
git tag pro-v1.0.0
git push origin pro-v1.0.0
```
Ergebnis: `stundenzettel-pro-android-aab` und `stundenzettel-pro-ios` als Artefakte des Laufs; mit Haken „upload“ geht das
Paket direkt in den internen Play-Test-Track und nach TestFlight. iOS braucht keinen eigenen Mac – der Workflow läuft auf
einem macOS-Runner von GitHub. Ohne Secrets baut er nur unsignierte Testpakete (zum Prüfen, dass alles kompiliert).
Die Versionsnummer kommt aus dem Tag (`pro-v1.2.3` → 1.2.3), der Build-Zähler aus der Laufnummer.

**Von Hand (Android, Windows):** Android Studio installieren (bringt JDK 21 mit; sonst lädt Gradle JDK 21 automatisch nach),
dann
```powershell
cd stundenzettel-pro\frontend
copy .env.app.example .env.app      # Server-Adresse eintragen
npm run cap:sync
npm run cap:android                 # öffnet Android Studio → Build → Generate Signed App Bundle
```
Oder ohne Studio: `cd android; .\gradlew bundleRelease` mit den Umgebungsvariablen `RELEASE_KEYSTORE`, `RELEASE_KEYSTORE_PASSWORD`,
`RELEASE_KEY_ALIAS`, `RELEASE_KEY_PASSWORD`, `APP_HOST`, `VERSION_CODE`, `VERSION_NAME`.
Hinweis für diesen PC: Norton Antivirus tauscht TLS-Zertifikate aus, deshalb steht in `%USERPROFILE%\.gradle\gradle.properties`
`systemProp.javax.net.ssl.trustStoreType=WINDOWS-ROOT` (Java vertraut dem Windows-Zertifikatspeicher). Ohne diese Zeile scheitern
Gradle-Downloads mit „PKIX path building failed“. Der Debug-Build `.\gradlew assembleDebug` erzeugt `app\build\outputs\apk\debug\app-debug.apk`
zum Ausprobieren auf dem eigenen Handy (Entwickleroptionen → USB-Debugging, dann `adb install`).

**Von Hand (iOS):** nur auf einem Mac mit Xcode 16: `npm run cap:sync; npm run cap:ios` → Signing & Capabilities: Team wählen,
Capability „Associated Domains“ mit `applinks:<deine Domain>` (Datei `App/App.entitlements`), dann Product → Archive → Distribute.

## Store-Eintrag (Texte zum Kopieren)

- **Name:** Stundenzettel Pro – Zeiterfassung
- **Kurzbeschreibung (80 Zeichen):** Stempeluhr, Stundenzettel, Rechnungen und Lohnexport für Reinigung und Handwerk.
- **Beschreibung:** Stundenzettel Pro ist die Zeiterfassung für Reinigungsfirmen, Hausmeisterdienste und Handwerksbetriebe mit
  Mitarbeitern. Mitarbeiter stempeln am Handy ein und aus (auch ohne Netz, auch per QR-Code am Objekt), das Büro bekommt
  Stundenzettel je Woche, Rechnungen je Monat, Lohnexport, Stundenkonten, Urlaubskonten, Arbeitszeitnachweise nach § 17 MiLoG,
  Personalakten und ein Sicherheitsprotokoll. Feiertage je Bundesland, Prüfung nach Arbeitszeitgesetz, Monatsabschluss,
  Kunden-Unterschrift auf dem Handy. Kein Tracking, keine Werbung, Daten auf Servern in Deutschland.
  Hinweis: Die App braucht ein Firmenkonto. Neue Firmen testen 14 Tage kostenlos.
- **Kategorie:** Business / Produktivität. **Alter:** 4+ / USK 0.
- **Datenschutz-Adresse:** `https://<deine Domain>/datenschutz`, **Support:** E-Mail aus `.env`.
- **Datenangaben (Play „Datensicherheit“, Apple „App-Datenschutz“):** Name, E-Mail, Telefon (Konto); Arbeitszeiten (App-Funktion);
  Standort nur freiwillig, Fotos nur freiwillig; verschlüsselte Übertragung; Löschung in der App möglich; kein Tracking, keine Weitergabe.
- **Review-Hinweise (Apple):** Testzugang angeben (Firma, Inhaber-Login und ein Mitarbeiter-Login auf dem Testserver) und erklären:
  „Die App ist die Zeiterfassung der Firma; Mitarbeiter werden vom Arbeitgeber eingeladen. Offline-Stempeluhr, QR-Code-Start,
  Kamera für Akten, PDF-Erzeugung und Unterschriften laufen auf dem Gerät.“ Für die Prüfung eine Testfirma auf dem Produktivserver
  mit `python backend/testdaten.py https://<deine Domain>` anlegen und die Zugangsdaten im Review-Feld nennen.
- **Screenshots:** mindestens Stempeluhr, Projektkalender, Stundenzettel-PDF, Übersicht, Auswertung; Größen 6,7" iPhone und
  Android-Phone (1080×1920 oder höher). Am einfachsten im Browser mit Geräteansicht (Chrome → Gerätesymbol) aufnehmen.

## Nach dem ersten Upload

- Play Console: internen Test-Track → Tester einladen → geschlossener Test (Google verlangt für neue Privatkonten 12 Tester
  über 14 Tage; für Firmenkonten nicht) → Produktion.
- App Store Connect: TestFlight-Build → interne Tester → „Zur Überprüfung einreichen“.
- Bei Updates nur `VERSION_CODE`/`CURRENT_PROJECT_VERSION` hochzählen (macht der Workflow über die Build-Nummer).
- Preise/Abos im Store: Die App verkauft nichts im Store (Firmenlizenz läuft über den Anbieter per Rechnung) – das ist bei
  Apple als „Business-App mit externer Lizenz“ zulässig (Richtlinie 3.1.3(b)); keine Kaufknöpfe in der App einbauen.
