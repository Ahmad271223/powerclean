import Foundation

/// Datumsregeln der App – immer in Europe/Berlin, Woche beginnt am Montag (wie der Server: zeiten.montag_von).
public enum Kalender {
    public static let zeitzone = TimeZone(identifier: "Europe/Berlin")!

    public static var kalender: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = zeitzone
        c.firstWeekday = 2
        c.minimumDaysInFirstWeek = 4   // ISO-8601-Kalenderwochen
        c.locale = Locale(identifier: "de_DE")
        return c
    }

    private static let wochentage = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]
    private static let wochentageLang = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]

    /// „2026-11-24“
    public static func iso(_ datum: Date) -> String {
        let t = kalender.dateComponents([.year, .month, .day], from: datum)
        return String(format: "%04d-%02d-%02d", t.year ?? 0, t.month ?? 0, t.day ?? 0)
    }

    /// Mittag des Tages (vermeidet Sommerzeit-Kanten), nil bei ungültiger Eingabe.
    public static func tag(_ iso: String) -> Date? {
        let teile = iso.split(separator: "-").compactMap { Int($0) }
        guard teile.count == 3 else { return nil }
        let k = DateComponents(year: teile[0], month: teile[1], day: teile[2], hour: 12)
        guard let d = kalender.date(from: k), Self.iso(d) == iso else { return nil }
        return d
    }

    public static func plus(_ tage: Int, _ datum: Date) -> Date { kalender.date(byAdding: .day, value: tage, to: datum)! }

    public static func montag(von datum: Date) -> Date {
        let k = kalender
        let wochentag = k.component(.weekday, from: datum)           // 1 = Sonntag … 7 = Samstag
        let zurueck = (wochentag + 5) % 7                              // Montag 0, Sonntag 6
        return tag(iso(plus(-zurueck, datum)))!
    }

    /// Montag bis Sonntag als ISO-Tage.
    public static func woche(ab montag: Date) -> [String] { (0..<7).map { iso(plus($0, montag)) } }

    public static func kalenderwoche(_ datum: Date) -> Int { kalender.component(.weekOfYear, from: datum) }

    /// „Di, 24.11.“
    public static func kurz(_ iso: String) -> String {
        guard let d = tag(iso) else { return iso }
        let k = kalender.dateComponents([.weekday, .day, .month], from: d)
        return String(format: "%@, %02d.%02d.", wochentage[(k.weekday ?? 1) - 1], k.day ?? 0, k.month ?? 0)
    }

    /// „Dienstag, 24.11.2026“
    public static func lang(_ iso: String) -> String {
        guard let d = tag(iso) else { return iso }
        let k = kalender.dateComponents([.weekday, .day, .month, .year], from: d)
        return String(format: "%@, %02d.%02d.%04d", wochentageLang[(k.weekday ?? 1) - 1], k.day ?? 0, k.month ?? 0, k.year ?? 0)
    }

    /// „KW 48 · 23.11.–29.11.“
    public static func wochenTitel(_ montag: Date) -> String {
        let tage = woche(ab: montag)
        func tm(_ s: String) -> String { String(kurz(s).dropFirst(4)) }
        return "KW \(kalenderwoche(montag)) · \(tm(tage[0]))–\(tm(tage[6]))"
    }

    /// Zeitstempel des Servers („2026-11-24T16:36:48.002487+00:00“) als „24.11. 17:36“ in Berliner Zeit.
    public static func zeitpunkt(_ server: String?) -> String? {
        guard let server else { return nil }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let d = f.date(from: server) ?? ISO8601DateFormatter().date(from: server) else { return nil }
        let k = kalender.dateComponents([.day, .month, .hour, .minute], from: d)
        return String(format: "%02d.%02d. %02d:%02d", k.day ?? 0, k.month ?? 0, k.hour ?? 0, k.minute ?? 0)
    }
}
