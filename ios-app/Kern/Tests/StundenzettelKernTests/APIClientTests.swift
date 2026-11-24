import Foundation
import Testing
@testable import StundenzettelKern

/// Ersetzt das Netz: jede Anfrage geht an `antwort`, die letzte Anfrage wird festgehalten. Kein echter Server nötig.
final class NetzAttrappe: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var antwort: (URLRequest) -> (Int, Data) = { _ in (200, Data("{}".utf8)) }
    nonisolated(unsafe) static var letzte: URLRequest?
    nonisolated(unsafe) static var letzterKoerper: Data?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.letzte = request
        Self.letzterKoerper = request.httpBody ?? request.httpBodyStream.map { strom in
            strom.open(); defer { strom.close() }
            var daten = Data(); var puffer = [UInt8](repeating: 0, count: 4096)
            while strom.hasBytesAvailable { let n = strom.read(&puffer, maxLength: puffer.count); if n <= 0 { break }; daten.append(puffer, count: n) }
            return daten
        }
        let (code, daten) = Self.antwort(request)
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: daten)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}

    static func sitzung() -> URLSession {
        let k = URLSessionConfiguration.ephemeral
        k.protocolClasses = [NetzAttrappe.self]
        return URLSession(configuration: k)
    }
}

@Suite("Server-Zugriff", .serialized)
struct APIClientTests {
    let basis = URL(string: "https://pro.beispiel.de/firma")!

    @Test func anmeldenSchicktJsonUndLiestAntwort() async throws {
        let beispiel = try Data(contentsOf: try #require(Bundle.module.url(forResource: "login_chef", withExtension: "json", subdirectory: "Beispiele")))
        NetzAttrappe.antwort = { _ in (200, beispiel) }
        let a = try await APIClient(basis: basis, token: nil, session: NetzAttrappe.sitzung()).anmelden(email: "  chef@beispiel.de ", passwort: "geheim123")
        #expect(a.user.darfPlanen)
        let r = try #require(NetzAttrappe.letzte)
        #expect(r.httpMethod == "POST" && r.url?.absoluteString == "https://pro.beispiel.de/firma/api/auth/login")
        #expect(r.value(forHTTPHeaderField: "Authorization") == nil)
        let koerper = try JSONSerialization.jsonObject(with: try #require(NetzAttrappe.letzterKoerper)) as? [String: String]
        #expect(koerper == ["email": "chef@beispiel.de", "password": "geheim123"])
    }

    @Test func tokenUndWochenzeitraum() async throws {
        let beispiel = try Data(contentsOf: try #require(Bundle.module.url(forResource: "plantafel", withExtension: "json", subdirectory: "Beispiele")))
        NetzAttrappe.antwort = { _ in (200, beispiel) }
        let montag = try #require(Kalender.tag("2026-11-23"))
        _ = try await APIClient(basis: basis, token: "t-123", session: NetzAttrappe.sitzung()).plantafel(woche: montag)
        let r = try #require(NetzAttrappe.letzte)
        #expect(r.value(forHTTPHeaderField: "Authorization") == "Bearer t-123")
        #expect(r.url?.absoluteString == "https://pro.beispiel.de/firma/api/einsatzplan?von=2026-11-23&bis=2026-11-29")
    }

    @Test func fehler401MitKlartext() async throws {
        let beispiel = try Data(contentsOf: try #require(Bundle.module.url(forResource: "fehler_401", withExtension: "json", subdirectory: "Beispiele")))
        NetzAttrappe.antwort = { _ in (401, beispiel) }
        await #expect(throws: APIFehler.nichtAngemeldet("E-Mail oder Passwort stimmt nicht.")) {
            _ = try await APIClient(basis: basis, token: nil, session: NetzAttrappe.sitzung()).anmelden(email: "a@b.de", passwort: "falsch")
        }
    }

    @Test func konfliktMitKlartext() async throws {
        NetzAttrappe.antwort = { _ in (409, Data(#"{"detail": "Dieser Einsatz ist abgesagt und lässt sich nicht bestätigen."}"#.utf8)) }
        do {
            _ = try await APIClient(basis: basis, token: "t", session: NetzAttrappe.sitzung()).bestaetigen("e-1")
            Issue.record("Fehler erwartet")
        } catch let f as APIFehler {
            #expect(f == .server(409, "Dieser Einsatz ist abgesagt und lässt sich nicht bestätigen."))
            #expect(f.errorDescription == "Dieser Einsatz ist abgesagt und lässt sich nicht bestätigen.")
        }
        #expect(NetzAttrappe.letzte?.url?.path == "/firma/api/einsatzplan/e-1/bestaetigen")
    }

    @Test func unlesbareAntwort() async throws {
        NetzAttrappe.antwort = { _ in (200, Data("<html>".utf8)) }
        await #expect(throws: APIFehler.unlesbareAntwort) {
            _ = try await APIClient(basis: basis, token: "t", session: NetzAttrappe.sitzung()).meineEinsaetze()
        }
    }
}
