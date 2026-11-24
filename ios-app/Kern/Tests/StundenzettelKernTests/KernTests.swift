import Foundation
import Testing
@testable import StundenzettelKern

// Die JSON-Beispiele unter Beispiele/ sind echte Antworten des Servers (Speicher-DB), erzeugt mit einem Skript gegen das Backend.
// Ändert sich die Server-Antwort, zeigen diese Tests, ob die App sie noch lesen kann.

private func beispiel(_ name: String) throws -> Data {
    let url = try #require(Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Beispiele"))
    return try Data(contentsOf: url)
}

private func lesen<T: Decodable>(_ typ: T.Type, _ name: String) throws -> T {
    try APIClient.decoder.decode(T.self, from: try beispiel(name))
}

@Suite("Server-Antworten lesen")
struct ModellTests {
    @Test func anmeldungChef() throws {
        let a = try lesen(AnmeldeAntwort.self, "login_chef")
        #expect(a.token == "beispiel-token")
        #expect(a.user.name == "Karl Chef" && a.user.role == "inhaber" && a.user.darfPlanen)
        #expect(a.firma.name == "Müller Bau GmbH")
    }

    @Test func mitarbeiterDarfNichtPlanen() throws {
        let ich = try lesen(IchAntwort.self, "ich_mitarbeiter")
        #expect(ich.user.name == "Nils Becker" && !ich.user.darfPlanen && ich.user.rolleName == "Mitarbeiter")
    }

    @Test func featureFlag() throws {
        let f = try lesen(FeatureAntwort.self, "features")
        #expect(f.features["sprachplanung"] == true)   // Beispiel wurde mit FEATURE_SPRACHPLANUNG=1 erzeugt
        #expect(f.features["chat"] == true)
    }

    @Test func meineEinteilungen() throws {
        let m = try lesen(MeineEinsaetze.self, "meine")
        let heute = try #require(m.heute.first)
        #expect(heute.projekt.name == "Badsanierung Müller" && heute.zeitraum == "07:00–16:00 Uhr")
        #expect(heute.ort == "Hauptstraße 5, 30159 Hannover" && heute.kollegen == ["Tom Wagner"] && heute.kolonne == "Trupp Bad")
        #expect(heute.note == "Schlüssel beim Hausmeister" && heute.taetigkeit == "Fliesen Bad OG")
        #expect(heute.stand.bestaetigt && heute.stand.stand == "bestätigt")
        #expect(heute.mitarbeiter == nil && heute.userId == nil)   // Mitarbeiter sehen keine fremden Namen
        #expect(m.morgen.count == 1 && m.morgen[0].stand == .offen)
        #expect(!m.restDerWoche(heute: heute.date).contains { $0.id == heute.id || $0.id == m.morgen[0].id })
    }

    @Test func einzelnerEinsatz() throws {
        let e = try lesen(EinsatzAntwort.self, "einsatz_mitarbeiter").einsatz
        #expect(e.status == "geplant" && !e.abgesagt && e.version == 1 && e.plannedMinutes == 510)
    }

    @Test func plantafelWoche() throws {
        let p = try lesen(Plantafel.self, "plantafel")
        #expect(p.planer)
        let tag = p.heute
        let einsaetze = p.einsaetze(am: tag)
        #expect(einsaetze.count == 1 && einsaetze[0].mitarbeiter == "Nils Becker" && einsaetze[0].userId != nil)
        let ab = p.abwesenheiten(am: tag)
        #expect(ab.count == 1 && ab[0].userName == "Tom Wagner" && ab[0].artName == "Urlaub")
        #expect(p.mitarbeiter?.contains { $0.name == "Tom Wagner" } == true)
        #expect(p.projekte?.first?.name == "Badsanierung Müller")
    }
}

@Suite("Kalender (Europe/Berlin, Woche ab Montag)")
struct KalenderTests {
    @Test func isoHinUndZurueck() throws {
        let d = try #require(Kalender.tag("2026-11-24"))
        #expect(Kalender.iso(d) == "2026-11-24")
        #expect(Kalender.tag("2026-02-30") == nil && Kalender.tag("Unsinn") == nil)
    }

    @Test(arguments: [("2026-11-23", "2026-11-23"), ("2026-11-24", "2026-11-23"), ("2026-11-29", "2026-11-23"), ("2026-11-30", "2026-11-30"), ("2027-01-01", "2026-12-28")])
    func montag(tag: String, erwartet: String) throws {
        #expect(Kalender.iso(Kalender.montag(von: try #require(Kalender.tag(tag)))) == erwartet)
    }

    @Test func sommerzeitWechsel() throws {
        // 29.03.2026: Umstellung auf Sommerzeit – die Woche hat trotzdem sieben verschiedene Tage
        let m = Kalender.montag(von: try #require(Kalender.tag("2026-03-29")))
        #expect(Kalender.woche(ab: m) == ["2026-03-23", "2026-03-24", "2026-03-25", "2026-03-26", "2026-03-27", "2026-03-28", "2026-03-29"])
    }

    @Test func anzeigen() throws {
        #expect(Kalender.kurz("2026-11-24") == "Di, 24.11.")
        #expect(Kalender.lang("2026-11-24") == "Dienstag, 24.11.2026")
        #expect(Kalender.wochenTitel(try #require(Kalender.tag("2026-11-23"))) == "KW 48 · 23.11.–29.11.")
        #expect(Kalender.kalenderwoche(try #require(Kalender.tag("2026-12-31"))) == 53)
        #expect(Kalender.zeitpunkt("2026-11-24T16:36:48.002487+00:00") == "24.11. 17:36")
        #expect(Kalender.zeitpunkt("2026-07-01T10:00:00+00:00") == "01.07. 12:00")
    }
}

@Suite("Lizenzen")
struct LizenzTests {
    @Test func nurFreieLizenzen() {
        #expect(Lizenzen.alleErlaubt)
        #expect(!Lizenzen.erlaubt.contains("GPL-3.0") && !Lizenzen.erlaubt.contains("AGPL-3.0"))
    }
}

@Suite("Token-Ablage")
struct TokenTests {
    @Test func speicherImArbeitsspeicher() throws {
        let s = SpeicherImArbeitsspeicher()
        #expect(s.lesen() == nil)
        try s.speichern("abc")
        #expect(s.lesen() == "abc")
        s.loeschen()
        #expect(s.lesen() == nil)
    }
}
