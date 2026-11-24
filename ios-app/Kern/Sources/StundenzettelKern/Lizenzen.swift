import Foundation

/// Fremde Bausteine in der App mit ihrer Lizenz – angezeigt unter „Über / Lizenzen“.
/// Regel: nur freie Lizenzen ohne Copyleft (MIT, Apache 2.0, BSD). Ein Test prüft die Liste.
public struct Baustein: Sendable, Identifiable, Equatable {
    public var id: String { name }
    public let name: String
    public let lizenz: String          // SPDX-Kennung
    public let urheber: String
    public let adresse: String
    public let zweck: String
}

public enum Lizenzen {
    public static let erlaubt: Set<String> = ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]

    /// Stand Schritt 1: keine fremden Bausteine. WhisperKit (MIT) kommt mit der Spracheingabe dazu.
    public static let bausteine: [Baustein] = []

    public static var alleErlaubt: Bool { bausteine.allSatisfy { erlaubt.contains($0.lizenz) } }
}
