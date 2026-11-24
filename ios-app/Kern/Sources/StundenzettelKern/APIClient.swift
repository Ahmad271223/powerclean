import Foundation

public enum APIFehler: Error, LocalizedError, Equatable {
    /// 401: abgemeldet, Token abgelaufen oder Konto deaktiviert – die App meldet ab.
    case nichtAngemeldet(String)
    /// Fehler mit Klartext vom Server (403, 404, 409, 422 …).
    case server(Int, String)
    case keineVerbindung(String)
    case unlesbareAntwort
    case ungueltigeAdresse

    public var errorDescription: String? {
        switch self {
        case .nichtAngemeldet(let t): t
        case .server(_, let t): t
        case .keineVerbindung(let t): "Keine Verbindung zum Server. \(t)"
        case .unlesbareAntwort: "Die Antwort des Servers war nicht lesbar. Bitte App aktualisieren."
        case .ungueltigeAdresse: "Die Server-Adresse ist ungültig."
        }
    }
}

/// Zugriff auf die Server-API. Wertetyp ohne Zustand: die Sitzung erzeugt bei Bedarf einen neuen mit dem aktuellen Token.
public struct APIClient: Sendable {
    public let basis: URL
    public let token: String?
    private let session: URLSession

    public init(basis: URL, token: String?, session: URLSession = .shared) {
        self.basis = basis
        self.token = token
        self.session = session
    }

    static var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }

    func url(_ pfad: String, _ query: [URLQueryItem] = []) throws -> URL {
        var u = basis
        for teil in pfad.split(separator: "/") { u.appendPathComponent(String(teil)) }
        guard var k = URLComponents(url: u, resolvingAgainstBaseURL: false) else { throw APIFehler.ungueltigeAdresse }
        if !query.isEmpty { k.queryItems = query }
        guard let fertig = k.url else { throw APIFehler.ungueltigeAdresse }
        return fertig
    }

    func anfrage<T: Decodable>(_ methode: String, _ pfad: String, query: [URLQueryItem] = [], json: [String: String]? = nil) async throws -> T {
        var r = URLRequest(url: try url(pfad, query), timeoutInterval: 20)
        r.httpMethod = methode
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let json {
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try JSONSerialization.data(withJSONObject: json)
        }
        let daten: Data
        let antwort: URLResponse
        do {
            (daten, antwort) = try await session.data(for: r)
        } catch {
            throw APIFehler.keineVerbindung((error as NSError).localizedDescription)
        }
        let code = (antwort as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            let text = (try? JSONDecoder().decode(FehlerAntwort.self, from: daten))?.detail ?? "Fehler \(code)."
            throw code == 401 ? APIFehler.nichtAngemeldet(text) : APIFehler.server(code, text)
        }
        do {
            return try Self.decoder.decode(T.self, from: daten)
        } catch {
            throw APIFehler.unlesbareAntwort
        }
    }

    // MARK: Anmeldung

    public func anmelden(email: String, passwort: String) async throws -> AnmeldeAntwort {
        try await anfrage("POST", "api/auth/login", json: ["email": email.trimmingCharacters(in: .whitespacesAndNewlines), "password": passwort])
    }

    public func ich() async throws -> IchAntwort { try await anfrage("GET", "api/auth/ich") }

    public func features() async throws -> FeatureAntwort { try await anfrage("GET", "api/features") }

    // MARK: Einteilungen

    public func meineEinsaetze() async throws -> MeineEinsaetze { try await anfrage("GET", "api/einsatzplan/meine") }

    public func einsatz(_ id: String) async throws -> Einsatz {
        let a: EinsatzAntwort = try await anfrage("GET", "api/einsatzplan/\(id)")
        return a.einsatz
    }

    public func gelesen(_ id: String) async throws -> Einsatz {
        let a: EinsatzAntwort = try await anfrage("POST", "api/einsatzplan/\(id)/gelesen")
        return a.einsatz
    }

    public func bestaetigen(_ id: String) async throws -> Einsatz {
        let a: EinsatzAntwort = try await anfrage("POST", "api/einsatzplan/\(id)/bestaetigen")
        return a.einsatz
    }

    /// Plantafel (nur Planer sehen alle Personen) von Montag bis Sonntag.
    public func plantafel(woche montag: Date) async throws -> Plantafel {
        let tage = Kalender.woche(ab: montag)
        return try await anfrage("GET", "api/einsatzplan", query: [URLQueryItem(name: "von", value: tage[0]), URLQueryItem(name: "bis", value: tage[6])])
    }
}
