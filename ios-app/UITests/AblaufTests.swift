import XCTest

/// Durchklick-Tests gegen einen lokalen Server mit Demo-Daten:
///   cd stundenzettel-pro/backend && DB_MODE=memory FEATURE_SPRACHPLANUNG=1 python -m uvicorn server:app --port 8010
///   python testdaten_app.py
/// Zugangsdaten aus testdaten_app.py. Ohne laufenden Server werden die Tests übersprungen.
final class AblaufTests: XCTestCase {
    private let server = "http://localhost:8010"
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        let erreichbar = (try? Data(contentsOf: URL(string: "\(server)/api/health")!)) != nil
        try XCTSkipUnless(erreichbar, "Lokaler Server läuft nicht – siehe Kopf dieser Datei.")
        app = XCUIApplication()
        app.launchArguments += ["-server-adresse", server]   // UserDefaults: Server-Adresse der App
        app.launch()
        abmeldenFallsNoetig()
    }

    func test_01_mitarbeiter_sieht_einteilung_und_bestaetigt() throws {
        anmelden("nils.becker@demo-bau.de", "demo-nils-2026")
        XCTAssertTrue(app.navigationBars["Meine Einsätze"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons.containing(NSPredicate(format: "label CONTAINS 'Badsanierung Müller'")).firstMatch.waitForExistence(timeout: 10))
        bild("1-meine-einsaetze")
        // eine noch offene Einteilung öffnen und bestätigen; danach muss die Liste eine offene weniger zeigen
        let offen = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Stand: offen'"))
        let vorher = offen.count
        try XCTSkipIf(vorher == 0, "Alle Demo-Einteilungen sind schon bestätigt – Demo-Daten neu laden.")
        offen.firstMatch.tap()
        XCTAssertTrue(app.buttons["Navigation starten"].waitForExistence(timeout: 10))
        let knopf = app.buttons["Gelesen & bestätigt"]
        XCTAssertTrue(knopf.waitForExistence(timeout: 5))
        bild("2-einsatz-offen")
        knopf.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label BEGINSWITH 'Bestätigt'")).firstMatch.waitForExistence(timeout: 10))
        bild("3-einsatz-bestaetigt")
        app.navigationBars.buttons.firstMatch.tap()
        // zurück in der Liste: der Stand ist ohne Ziehen zum Aktualisieren neu geladen
        let bis = Date().addingTimeInterval(10)
        while offen.count != vorher - 1 && Date() < bis { RunLoop.current.run(until: Date().addingTimeInterval(0.3)) }
        XCTAssertEqual(offen.count, vorher - 1)
        abmelden()
    }

    func test_02_chef_sieht_plantafel_und_mikrofon() throws {
        anmelden("karl@demo-bau.de", "demo-chef-2026")
        XCTAssertTrue(app.navigationBars["Plantafel"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label BEGINSWITH 'KW '")).firstMatch.exists)
        XCTAssertTrue(app.buttons.containing(NSPredicate(format: "label CONTAINS 'Nils Becker'")).firstMatch.waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Tom Wagner: Urlaub"].exists || app.swipeUntil(app.staticTexts["Tom Wagner: Urlaub"]))
        bild("4-plantafel-woche")
        let mikro = app.buttons["Einteilung sprechen"]
        XCTAssertTrue(mikro.exists)
        mikro.tap()
        XCTAssertTrue(app.alerts["Einteilung per Sprache"].waitForExistence(timeout: 5))
        bild("5-mikrofon-hinweis")
        app.alerts.buttons["OK"].tap()
        app.buttons["Nächste Woche"].tap()
        XCTAssertTrue(app.buttons.containing(NSPredicate(format: "label CONTAINS 'Dachsanierung Schmidt'")).firstMatch.waitForExistence(timeout: 10))
        bild("6-plantafel-naechste-woche")
        app.tabBars.buttons["Einstellungen"].tap()
        app.buttons["Über / Lizenzen"].tap()
        XCTAssertTrue(app.staticTexts["Diese Version enthält keine fremden Bausteine."].waitForExistence(timeout: 5))
        bild("7-lizenzen")
        app.navigationBars.buttons.firstMatch.tap()
        abmelden()
    }

    func test_03_falsches_passwort_zeigt_klartext() throws {
        anmelden("karl@demo-bau.de", "falsch-falsch")
        XCTAssertTrue(app.staticTexts["E-Mail oder Passwort stimmt nicht."].waitForExistence(timeout: 10))
        bild("0-anmeldung-fehler")
    }

    // MARK: Hilfen

    private func anmelden(_ email: String, _ passwort: String) {
        let feld = app.textFields["E-Mail"]
        XCTAssertTrue(feld.waitForExistence(timeout: 10))
        feld.tap()
        feld.typeText(email)
        let pw = app.secureTextFields["Passwort"]
        pw.tap()
        pw.typeText(passwort)
        app.buttons["Anmelden"].tap()
    }

    private func abmeldenFallsNoetig() {
        let tab = app.tabBars.buttons["Einstellungen"]
        if tab.waitForExistence(timeout: 4) { abmelden() }
    }

    private func abmelden() {
        app.tabBars.buttons["Einstellungen"].tap()
        app.buttons["Abmelden"].firstMatch.tap()
        let rueckfrage = app.alerts["Wirklich abmelden?"]
        XCTAssertTrue(rueckfrage.waitForExistence(timeout: 5))
        rueckfrage.buttons["Abmelden"].tap()
        XCTAssertTrue(app.textFields["E-Mail"].waitForExistence(timeout: 5))
    }

    private func bild(_ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot())
        a.name = name
        a.lifetime = .keepAlways
        add(a)
    }
}

private extension XCUIApplication {
    func swipeUntil(_ element: XCUIElement, versuche: Int = 4) -> Bool {
        for _ in 0..<versuche where !element.exists { swipeUp() }
        return element.exists
    }
}
