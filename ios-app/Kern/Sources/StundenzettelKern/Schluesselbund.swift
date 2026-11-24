import Foundation
import Security

/// Ablage für das Anmelde-Token. In der App der Schlüsselbund, in Tests ein Speicher im Arbeitsspeicher.
public protocol TokenSpeicher: Sendable {
    func lesen() -> String?
    func speichern(_ token: String) throws
    func loeschen()
}

/// Token im iOS-Schlüsselbund: nur auf diesem Gerät, erst nach dem ersten Entsperren lesbar, nicht in Backups auf andere Geräte.
public struct Schluesselbund: TokenSpeicher {
    public let dienst: String
    public let konto: String

    public init(dienst: String = "de.stundenzettelpro.ios", konto: String = "anmeldung") {
        self.dienst = dienst
        self.konto = konto
    }

    private var abfrage: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: dienst, kSecAttrAccount as String: konto]
    }

    public func lesen() -> String? {
        var q = abfrage
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var ergebnis: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &ergebnis) == errSecSuccess, let daten = ergebnis as? Data else { return nil }
        return String(data: daten, encoding: .utf8)
    }

    public func speichern(_ token: String) throws {
        loeschen()
        var q = abfrage
        q[kSecValueData as String] = Data(token.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(q as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw NSError(domain: NSOSStatusErrorDomain, code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Anmeldung konnte nicht im Schlüsselbund gespeichert werden (\(status))."])
        }
    }

    public func loeschen() {
        SecItemDelete(abfrage as CFDictionary)
    }
}

/// Für Tests und Vorschauen.
public final class SpeicherImArbeitsspeicher: TokenSpeicher, @unchecked Sendable {
    private let sperre = NSLock()
    private var wert: String?

    public init(_ wert: String? = nil) { self.wert = wert }

    public func lesen() -> String? { sperre.withLock { wert } }
    public func speichern(_ token: String) throws { sperre.withLock { wert = token } }
    public func loeschen() { sperre.withLock { wert = nil } }
}
