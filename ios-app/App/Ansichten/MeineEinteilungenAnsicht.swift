import SwiftUI
import StundenzettelKern

/// Mitarbeiter: eigene Einteilungen – heute, morgen, Rest der Woche, nächste Woche, später.
struct MeineEinteilungenAnsicht: View {
    @Environment(Sitzung.self) private var sitzung
    @State private var daten: MeineEinsaetze?
    @State private var fehler: String?

    private var heute: String { Kalender.iso(Date()) }

    var body: some View {
        List {
            if let fehler {
                Label(fehler, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red)
            }
            if let d = daten {
                abschnitt("Heute", d.heute, mitDatum: false, leer: "Heute keine Einteilung.")
                abschnitt("Morgen", d.morgen, mitDatum: false, leer: "Morgen keine Einteilung.")
                abschnitt("Diese Woche", d.restDerWoche(heute: heute))
                abschnitt("Nächste Woche", d.naechsteWoche)
                abschnitt("Später", d.spaeter)
            }
        }
        .listStyle(.insetGrouped)
        .overlay {
            if daten == nil && fehler == nil { ProgressView().controlSize(.large) }
        }
        .navigationTitle("Meine Einsätze")
        .navigationDestination(for: Einsatz.self) { e in EinsatzDetailAnsicht(einsatzId: e.id) }
        .refreshable { await laden() }
        .task { await laden() }
        .onAppear { if daten != nil { Task { await laden() } } }   // nach dem Zurückkehren aus dem Einsatz: Stand aktualisieren
    }

    @ViewBuilder
    private func abschnitt(_ titel: String, _ liste: [Einsatz], mitDatum: Bool = true, leer: String? = nil) -> some View {
        if !liste.isEmpty || leer != nil {
            Section {
                if liste.isEmpty, let leer {
                    Text(leer).foregroundStyle(.secondary)
                }
                ForEach(liste) { e in
                    NavigationLink(value: e) { EinsatzZeile(einsatz: e, mitDatum: mitDatum) }
                }
            } header: {
                Text(titel).font(.title3.bold()).foregroundStyle(.primary).textCase(nil)
            }
        }
    }

    private func laden() async {
        guard let client = sitzung.client else { return }
        do {
            daten = try await client.meineEinsaetze()
            fehler = nil
        } catch {
            fehler = sitzung.meldung(error)
        }
    }
}
