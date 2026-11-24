import SwiftUI
import StundenzettelKern

struct EinstellungenAnsicht: View {
    @Environment(Sitzung.self) private var sitzung
    @State private var abmeldenFragen = false

    var body: some View {
        Form {
            Section("Angemeldet") {
                LabeledContent("Name", value: sitzung.nutzer?.name ?? "–")
                LabeledContent("Rolle", value: sitzung.nutzer?.rolleName ?? sitzung.nutzer?.role ?? "–")
                LabeledContent("Firma", value: sitzung.firma?.name ?? "–")
                LabeledContent("Server", value: sitzung.serverAdresse)
            }
            .font(.body)
            Section {
                NavigationLink("Über / Lizenzen") { LizenzenAnsicht() }
                    .frame(minHeight: 44)
            }
            Section {
                Button("Abmelden", role: .destructive) { abmeldenFragen = true }
                    .font(.title3.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 52)
            }
        }
        .navigationTitle("Einstellungen")
        .alert("Wirklich abmelden?", isPresented: $abmeldenFragen) {
            Button("Abbrechen", role: .cancel) {}
            Button("Abmelden", role: .destructive) { sitzung.abmelden() }
        } message: {
            Text("Zum Wiederkommen brauchst du E-Mail und Passwort.")
        }
    }
}

struct LizenzenAnsicht: View {
    private var version: String {
        let i = Bundle.main.infoDictionary
        return "\(i?["CFBundleShortVersionString"] as? String ?? "?") (\(i?["CFBundleVersion"] as? String ?? "?"))"
    }

    var body: some View {
        List {
            Section("App") {
                LabeledContent("Stundenzettel Pro", value: "Version \(version)")
                Text("Die Anmeldung liegt nur im Schlüsselbund dieses iPhones. Die App enthält keine Zugangsschlüssel für Dienste Dritter.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            Section("Fremde Bausteine") {
                if Lizenzen.bausteine.isEmpty {
                    Text("Diese Version enthält keine fremden Bausteine.").foregroundStyle(.secondary)
                }
                ForEach(Lizenzen.bausteine) { b in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(b.name).font(.headline)
                        Text("\(b.lizenz) · \(b.urheber)").font(.subheadline)
                        Text(b.zweck).font(.subheadline).foregroundStyle(.secondary)
                        if let url = URL(string: b.adresse) { Link(b.adresse, destination: url).font(.footnote) }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .navigationTitle("Über / Lizenzen")
    }
}
