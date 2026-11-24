import Foundation
import Observation
import StundenzettelKern

/// Anmeldestand der App. Das Token liegt nur im Schlüsselbund, die Server-Adresse (kein Geheimnis) in den Einstellungen.
@MainActor @Observable
final class Sitzung {
    enum Zustand: Equatable { case startet, offline(String), abgemeldet, angemeldet }

    private(set) var zustand: Zustand = .startet
    private(set) var nutzer: Nutzer?
    private(set) var firma: Firma?
    private(set) var features: [String: Bool] = [:]
    var serverAdresse: String {
        didSet { UserDefaults.standard.set(serverAdresse, forKey: Self.serverSchluessel) }
    }

    private let speicher: TokenSpeicher
    private var token: String?
    private static let serverSchluessel = "server-adresse"

    #if DEBUG
    static let standardServer = "http://localhost:8010"   // Simulator erreicht den Mac unter localhost
    #else
    static let standardServer = ""
    #endif

    init(speicher: TokenSpeicher = Schluesselbund()) {
        self.speicher = speicher
        serverAdresse = UserDefaults.standard.string(forKey: Self.serverSchluessel) ?? Self.standardServer
    }

    var client: APIClient? {
        let adresse = serverAdresse.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: adresse), url.scheme == "https" || url.scheme == "http", url.host != nil else { return nil }
        return APIClient(basis: url, token: token)
    }

    var darfPlanen: Bool { nutzer?.darfPlanen == true }
    var sprachplanungAktiv: Bool { features["sprachplanung"] == true }

    func starten() async {
        token = speicher.lesen()
        guard token != nil, let client else { zustand = .abgemeldet; return }
        do {
            let ich = try await client.ich()
            nutzer = ich.user
            firma = ich.firma
            await featuresLaden()
            zustand = .angemeldet
        } catch APIFehler.nichtAngemeldet {
            abmelden()
        } catch {
            zustand = .offline(error.localizedDescription)
        }
    }

    func anmelden(email: String, passwort: String) async throws {
        guard let client else { throw APIFehler.ungueltigeAdresse }
        let antwort = try await client.anmelden(email: email, passwort: passwort)
        try speicher.speichern(antwort.token)
        token = antwort.token
        nutzer = antwort.user
        firma = antwort.firma
        await featuresLaden()
        zustand = .angemeldet
    }

    func abmelden() {
        speicher.loeschen()
        token = nil
        nutzer = nil
        firma = nil
        features = [:]
        zustand = .abgemeldet
    }

    func featuresLaden() async {
        features = (try? await client?.features().features) ?? [:]
    }

    /// Einheitliche Fehlerbehandlung der Ansichten: bei 401 abmelden, sonst den Klartext zurückgeben.
    func meldung(_ fehler: Error) -> String {
        if case APIFehler.nichtAngemeldet = fehler { abmelden() }
        return fehler.localizedDescription
    }
}
