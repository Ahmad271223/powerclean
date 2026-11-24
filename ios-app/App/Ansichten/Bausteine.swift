import SwiftUI
import StundenzettelKern

extension Color {
    /// Markenrot von Stundenzettel Pro (#C41E3A).
    static let marke = Color(red: 0xC4 / 255, green: 0x1E / 255, blue: 0x3A / 255)
}

/// Großer Knopf für die Baustelle: mindestens 64 pt hoch, volle Breite, fette Schrift – mit Arbeitshandschuhen gut zu treffen.
struct GrosserKnopf: ButtonStyle {
    enum Art { case haupt, zweitrangig, erfolg }
    var art: Art = .haupt
    @Environment(\.isEnabled) private var aktiv

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.title3.weight(.bold))
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity, minHeight: 64)
            .padding(.horizontal, 16)
            .foregroundStyle(art == .zweitrangig ? Color.primary : Color.white)
            .background(hintergrund.opacity(aktiv ? 1 : 0.4), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .contentShape(RoundedRectangle(cornerRadius: 16))
    }

    private var hintergrund: Color {
        switch art {
        case .haupt: .marke
        case .zweitrangig: Color(.secondarySystemFill)
        case .erfolg: .green
        }
    }
}

/// Stand der Lesebestätigung als Symbol mit Text (nicht nur Farbe).
struct QuittungsAbzeichen: View {
    let quittung: Quittung

    var body: some View {
        Label(quittung.stand.capitalized, systemImage: symbol)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(farbe)
            .accessibilityLabel("Stand: \(quittung.stand)")
    }

    private var symbol: String { quittung.bestaetigt ? "checkmark.circle.fill" : (quittung.gelesen ? "eye.fill" : "circle.dashed") }
    private var farbe: Color { quittung.bestaetigt ? .green : (quittung.gelesen ? .blue : .secondary) }
}

/// Zeile einer Einteilung in Listen (Mitarbeiter-Ansicht und Plantafel).
struct EinsatzZeile: View {
    let einsatz: Einsatz
    var mitDatum = true
    var mitMitarbeiter = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if mitMitarbeiter, let name = einsatz.mitarbeiter {
                Text(name).font(.headline)
            }
            Text(einsatz.projekt.name).font(mitMitarbeiter ? .body.weight(.medium) : .title3.weight(.bold))
            HStack(spacing: 8) {
                if mitDatum { Text(Kalender.kurz(einsatz.date)) }
                Text(einsatz.zeitraum)
            }
            .font(.body.monospacedDigit())
            if !einsatz.ort.isEmpty {
                Label(einsatz.ort, systemImage: "mappin.and.ellipse").font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
            }
            HStack {
                if einsatz.abgesagt {
                    Label("Abgesagt", systemImage: "xmark.octagon.fill").font(.subheadline.weight(.semibold)).foregroundStyle(.red)
                } else {
                    QuittungsAbzeichen(quittung: einsatz.stand)
                }
            }
        }
        .padding(.vertical, 8)
        .strikethrough(einsatz.abgesagt)
        .accessibilityElement(children: .combine)
    }
}

/// Leere Liste mit Hinweis.
struct LeerHinweis: View {
    let titel: String
    let text: String
    let symbol: String

    var body: some View {
        ContentUnavailableView(titel, systemImage: symbol, description: Text(text))
    }
}
