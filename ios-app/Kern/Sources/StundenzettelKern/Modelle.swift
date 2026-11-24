import Foundation

// Datenmodelle wie der Server sie liefert (stundenzettel-pro/backend). Felder in snake_case werden beim Lesen automatisch
// umgewandelt (project_id → projectId). Nur was die App braucht; unbekannte Felder werden ignoriert.

public struct Nutzer: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public let name: String
    public let email: String?
    public let role: String
    public let rolleName: String?
    public let rechte: [String: Bool]

    /// Inhaber und Büro mit dem Recht „plantafel“ planen; alle anderen sehen nur eigene Einteilungen.
    public var darfPlanen: Bool { rechte["plantafel"] == true }
}

public struct Firma: Codable, Sendable, Equatable {
    public let id: String
    public let name: String
}

public struct Lizenzstand: Codable, Sendable, Equatable {
    public let status: String
    public let hinweis: String?
    public let schreiben: Bool?
}

public struct AnmeldeAntwort: Codable, Sendable {
    public let token: String
    public let user: Nutzer
    public let firma: Firma
    public let plan: Lizenzstand?
}

public struct IchAntwort: Codable, Sendable {
    public let user: Nutzer
    public let firma: Firma
    public let plan: Lizenzstand?
}

public struct FeatureAntwort: Codable, Sendable {
    public let features: [String: Bool]
}

public struct ProjektKurz: Codable, Sendable, Equatable, Identifiable, Hashable {
    public let id: String
    public let name: String
    public let color: String?
    public let address: String?
}

/// Lesebestätigung des Mitarbeiters für die aktuelle Version des Einsatzes.
public struct Quittung: Codable, Sendable, Equatable {
    public let gelesen: Bool
    public let bestaetigt: Bool
    public let gelesenAt: String?
    public let bestaetigtAt: String?

    public static let offen = Quittung(gelesen: false, bestaetigt: false, gelesenAt: nil, bestaetigtAt: nil)

    public init(gelesen: Bool, bestaetigt: Bool, gelesenAt: String?, bestaetigtAt: String?) {
        self.gelesen = gelesen
        self.bestaetigt = bestaetigt
        self.gelesenAt = gelesenAt
        self.bestaetigtAt = bestaetigtAt
    }

    /// Kurzer Stand für Listen: bestätigt > gelesen > offen.
    public var stand: String { bestaetigt ? "bestätigt" : (gelesen ? "gelesen" : "offen") }
}

public struct Einsatz: Codable, Sendable, Equatable, Identifiable, Hashable {
    public let id: String
    public let projectId: String
    public let date: String              // JJJJ-MM-TT
    public let startTime: String         // HH:MM
    public let endTime: String
    public let pauseMinutes: Int?
    public let plannedMinutes: Int?
    public let address: String?
    public let note: String?
    public let taetigkeit: String?
    public let kolonne: String?
    public let status: String            // geplant | abgesagt
    public let version: Int?
    public let projekt: ProjektKurz
    public let quittung: Quittung?
    // nur für Planer
    public let userId: String?
    public let mitarbeiter: String?
    // nur in „meine“ und im Einzelabruf
    public let kollegen: [String]?

    public var abgesagt: Bool { status == "abgesagt" }
    public var zeitraum: String { "\(startTime)–\(endTime) Uhr" }
    /// Adresse des Einsatzes, sonst die des Projekts.
    public var ort: String { [address, projekt.address].compactMap { $0 }.first { !$0.isEmpty } ?? "" }
    public var stand: Quittung { quittung ?? .offen }

    public static func == (a: Einsatz, b: Einsatz) -> Bool { a.id == b.id && a.version == b.version && a.quittung == b.quittung && a.status == b.status }
    public func hash(into h: inout Hasher) { h.combine(id) }
}

public struct MeineEinsaetze: Codable, Sendable {
    public let heute: [Einsatz]
    public let morgen: [Einsatz]
    public let woche: [Einsatz]
    public let naechsteWoche: [Einsatz]
    public let spaeter: [Einsatz]
    /// Die letzten sieben Tage (wie „Letzte Tage“ in der bisherigen App).
    public let vergangen: [Einsatz]
    public let stand: String?

    /// Rest der laufenden Woche nach heute, ohne morgen (der steht schon oben). Vergangene Tage der Woche fallen weg.
    public func restDerWoche(heute tag: String) -> [Einsatz] {
        let oben = Set((heute + morgen).map(\.id))
        return woche.filter { !oben.contains($0.id) && $0.date > tag }
    }
}

public struct Abwesenheit: Codable, Sendable, Identifiable, Equatable {
    public let id: String
    public let userId: String
    public let type: String
    public let fromDate: String
    public let toDate: String
    public let status: String?
    public let userName: String?

    public var artName: String {
        switch type {
        case "urlaub": "Urlaub"
        case "krank": "Krank"
        case "feiertag": "Frei (Feiertag)"
        case "unbezahlt": "Unbezahlt frei"
        default: "Abwesend"
        }
    }

    public func betrifft(_ tag: String) -> Bool { fromDate <= tag && tag <= toDate }
}

public struct MitarbeiterKurz: Codable, Sendable, Identifiable, Equatable, Hashable {
    public let id: String
    public let name: String
    public let role: String?
}

public struct Plantafel: Codable, Sendable {
    public let einsaetze: [Einsatz]
    public let abwesenheiten: [Abwesenheit]
    public let feiertage: [String: String]
    public let planer: Bool
    public let heute: String
    public let mitarbeiter: [MitarbeiterKurz]?
    public let projekte: [ProjektKurz]?

    public func einsaetze(am tag: String) -> [Einsatz] {
        einsaetze.filter { $0.date == tag }.sorted { ($0.startTime, $0.mitarbeiter ?? "") < ($1.startTime, $1.mitarbeiter ?? "") }
    }

    public func abwesenheiten(am tag: String) -> [Abwesenheit] { abwesenheiten.filter { $0.betrifft(tag) } }
}

struct EinsatzAntwort: Codable, Sendable {
    let einsatz: Einsatz
}

struct FehlerAntwort: Decodable {
    let detail: String?
}
