import SwiftUI
import StundenzettelKern

/// Eine Einteilung mit Adresse, Navigation und dem Knopf „Gelesen & bestätigt“.
/// Öffnet die eingeplante Person die Ansicht, meldet die App „gelesen“; „bestätigt“ nur per Knopf.
struct EinsatzDetailAnsicht: View {
    @Environment(Sitzung.self) private var sitzung
    @Environment(\.openURL) private var oeffnen
    let einsatzId: String
    @State private var einsatz: Einsatz?
    @State private var fehler: String?
    @State private var sendet = false

    /// Eigene Einteilung: der Server lässt userId für Mitarbeiter weg, Planer sehen sie.
    private var eigene: Bool {
        guard let e = einsatz else { return false }
        return e.userId == nil || e.userId == sitzung.nutzer?.id
    }

    var body: some View {
        ScrollView {
            if let e = einsatz {
                VStack(alignment: .leading, spacing: 20) {
                    kopf(e)
                    if e.abgesagt {
                        Label("Dieser Einsatz wurde abgesagt.", systemImage: "xmark.octagon.fill")
                            .font(.title3.bold()).foregroundStyle(.red)
                    }
                    angaben(e)
                    if !e.ort.isEmpty {
                        Button { navigation(e.ort) } label: { Label("Navigation starten", systemImage: "car.fill") }
                            .buttonStyle(GrosserKnopf(art: .zweitrangig))
                    }
                    bestaetigung(e)
                }
                .padding(20)
            } else if fehler == nil {
                ProgressView().controlSize(.large).padding(.top, 80)
            }
            if let fehler {
                Label(fehler, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red).padding(20)
            }
        }
        .navigationTitle("Einsatz")
        .navigationBarTitleDisplayMode(.inline)
        .task { await laden() }
        .refreshable { await laden() }
    }

    private func kopf(_ e: Einsatz) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if let name = e.mitarbeiter { Text(name).font(.title3).foregroundStyle(.secondary) }
            Text(e.projekt.name).font(.largeTitle.bold())
            Text(Kalender.lang(e.date)).font(.title3)
            Text(e.zeitraum).font(.title2.weight(.semibold).monospacedDigit())
        }
    }

    private func angaben(_ e: Einsatz) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            if !e.ort.isEmpty { zeile("Adresse", e.ort, "mappin.and.ellipse") }
            if let p = e.pauseMinutes, p > 0 { zeile("Pause", "\(p) Minuten", "cup.and.saucer") }
            if let t = e.taetigkeit, !t.isEmpty { zeile("Tätigkeit", t, "hammer") }
            if let n = e.note, !n.isEmpty { zeile("Hinweis", n, "info.circle") }
            if let k = e.kolonne { zeile("Kolonne", k, "person.3") }
            if let kollegen = e.kollegen, !kollegen.isEmpty { zeile("Mit dabei", kollegen.joined(separator: ", "), "person.2") }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
    }

    private func zeile(_ titel: String, _ text: String, _ symbol: String) -> some View {
        Label {
            VStack(alignment: .leading, spacing: 2) {
                Text(titel).font(.subheadline).foregroundStyle(.secondary)
                Text(text).font(.title3)
            }
        } icon: {
            Image(systemName: symbol).font(.title3).foregroundStyle(Color.marke)
        }
    }

    @ViewBuilder
    private func bestaetigung(_ e: Einsatz) -> some View {
        let q = e.stand
        if q.bestaetigt {
            Label("Bestätigt\(Kalender.zeitpunkt(q.bestaetigtAt).map { " am \($0)" } ?? "")", systemImage: "checkmark.circle.fill")
                .font(.title3.bold()).foregroundStyle(.green)
                .frame(maxWidth: .infinity, minHeight: 64)
                .background(Color.green.opacity(0.12), in: RoundedRectangle(cornerRadius: 16))
        } else if eigene && !e.abgesagt {
            Button { Task { await bestaetigen() } } label: {
                if sendet { ProgressView().tint(.white) } else { Label("Gelesen & bestätigt", systemImage: "checkmark") }
            }
            .buttonStyle(GrosserKnopf(art: .erfolg))
            .disabled(sendet)
        } else if !eigene {
            HStack { Text("Stand beim Mitarbeiter:").font(.title3); QuittungsAbzeichen(quittung: q).font(.title3) }
        }
    }

    private func navigation(_ adresse: String) {
        var k = URLComponents(string: "https://maps.apple.com/")!
        k.queryItems = [URLQueryItem(name: "daddr", value: adresse)]
        if let url = k.url { oeffnen(url) }
    }

    private func laden() async {
        guard let client = sitzung.client else { return }
        do {
            var e = try await client.einsatz(einsatzId)
            fehler = nil
            if (e.userId == nil || e.userId == sitzung.nutzer?.id) && !e.stand.gelesen {
                e = try await client.gelesen(einsatzId)
            }
            einsatz = e
        } catch {
            fehler = sitzung.meldung(error)
        }
    }

    private func bestaetigen() async {
        guard let client = sitzung.client else { return }
        sendet = true
        defer { sendet = false }
        do {
            einsatz = try await client.bestaetigen(einsatzId)
            fehler = nil
        } catch {
            fehler = sitzung.meldung(error)
        }
    }
}
