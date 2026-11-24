import Foundation

#if canImport(FoundationModels)
import FoundationModels

/// Feste Ausgabestruktur für Apples Modell auf dem Gerät (iOS 26, Apple Intelligence): immer sauber befüllte Felder.
/// Die KI zerlegt nur – Tage ausrechnen und Namen/Projekte zuordnen macht der Server mit normalem Code.
@available(iOS 26.0, *)
@Generable(description: "Einteilung von Mitarbeitern auf eine Baustelle, aus einem gesprochenen deutschen Satz")
struct Einteilungsvorschlag {
    @Guide(description: "Namen der Mitarbeiter genau wie gesagt, z. B. Nils oder Nils Becker; mehrere getrennt")
    var mitarbeiter: [String]
    @Guide(description: "Projekt, Baustelle oder Kunde wie gesagt, z. B. Badsanierung Müller oder Müller; leer, wenn nicht gesagt")
    var projekt: String
    @Guide(description: "Straße oder Ort wie gesagt, z. B. Hauptstraße; leer, wenn nicht gesagt")
    var standort: String
    @Guide(description: "Beginn im Format HH:MM, z. B. 07:00; leer, wenn nicht gesagt")
    var startzeit: String
    @Guide(description: "Ende im Format HH:MM; auf der Baustelle heißt „sieben bis vier“ 16:00; leer, wenn nicht gesagt")
    var endzeit: String
    @Guide(description: "Zeitangabe wörtlich wie gesagt, z. B. die ganze Woche, ab Montag drei Tage, morgen, nächste Woche Mittwoch – nichts ausrechnen")
    var zeitraum: String
    @Guide(description: "Feldnamen, bei denen du unsicher bist: mitarbeiter, projekt, standort, startzeit, endzeit, zeitraum")
    var unsicher: [String]
}

@available(iOS 26.0, *)
enum AppleZerleger {
    static var verfuegbar: Bool {
        let modell = SystemLanguageModel.default
        guard case .available = modell.availability else { return false }
        return modell.supportsLocale(Locale(identifier: "de_DE"))
    }

    static func zerlegen(_ text: String) async throws -> [String: Any] {
        let sitzung = LanguageModelSession(instructions: """
            Du zerlegst Sätze eines Handwerksmeisters, der Mitarbeiter auf Baustellen einteilt. \
            Übernimm Namen, Projekt, Ort und Zeitangaben wörtlich, erfinde nichts und rechne keine Daten aus. \
            Was nicht gesagt wurde, bleibt leer.
            """)
        let antwort = try await sitzung.respond(to: text, generating: Einteilungsvorschlag.self)
        let v = antwort.content
        return ["mitarbeiter": v.mitarbeiter, "projekt": v.projekt, "standort": v.standort, "startzeit": v.startzeit,
                "endzeit": v.endzeit, "zeitraum": v.zeitraum, "unsicher": v.unsicher]
    }
}
#endif

enum AppleKI {
    /// Apples Modell auf diesem Gerät nutzbar (iOS 26, Apple Intelligence an, Deutsch)?
    static var verfuegbar: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) { return AppleZerleger.verfuegbar }
        #endif
        return false
    }

    /// Felder oder nil, wenn nicht verfügbar (dann zerlegt der Server).
    static func zerlegen(_ text: String) async throws -> [String: Any]? {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *), AppleZerleger.verfuegbar { return try await AppleZerleger.zerlegen(text) }
        #endif
        return nil
    }
}
