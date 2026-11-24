import SwiftUI
import StundenzettelKern

/// Chef/Büro: Wochenansicht der Plantafel (lesen), Tag für Tag mit Einsätzen, Abwesenheiten und Feiertagen.
/// Unten der große Mikrofon-Knopf für die Einteilung per Sprache (nur mit Flag „sprachplanung“).
struct PlantafelWochenAnsicht: View {
    @Environment(Sitzung.self) private var sitzung
    @State private var montag = Kalender.montag(von: Date())
    @State private var tafel: Plantafel?
    @State private var fehler: String?
    @State private var laedt = false

    private var tage: [String] { Kalender.woche(ab: montag) }

    var body: some View {
        List {
                if let fehler {
                    Label(fehler, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red)
                }
                if let t = tafel {
                    ForEach(tage, id: \.self) { tag in tagesAbschnitt(tag, t) }
                }
        }
        .listStyle(.insetGrouped)
        .listSectionSpacing(.compact)
        .overlay { if tafel == nil && fehler == nil { ProgressView().controlSize(.large) } }
        .refreshable { await laden() }
        .safeAreaInset(edge: .bottom) {
            if sitzung.sprachplanungAktiv {
                MikrofonKnopf().padding(.bottom, 4)
            }
        }
        .navigationTitle("Plantafel")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { wochenwahl }
        .navigationDestination(for: Einsatz.self) { e in EinsatzDetailAnsicht(einsatzId: e.id) }
        .task(id: montag) { await laden() }
        .onAppear { if tafel != nil { Task { await laden() } } }
    }

    /// Woche blättern direkt in der Navigationsleiste (kein eigener Kopfbereich). Antippen des Titels springt zur laufenden Woche.
    @ToolbarContentBuilder
    private var wochenwahl: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            Button { montag = Kalender.plus(-7, montag) } label: { Image(systemName: "chevron.left").font(.headline) }
                .accessibilityLabel("Vorige Woche")
        }
        ToolbarItem(placement: .principal) {
            let titel = Kalender.wochenTitel(montag).components(separatedBy: " · ")
            let andereWoche = Kalender.iso(montag) != Kalender.iso(Kalender.montag(von: Date()))
            Button { montag = Kalender.montag(von: Date()) } label: {
                VStack(spacing: 0) {
                    Text(titel[0]).font(.headline)
                    Text(andereWoche ? "\(titel.last ?? "") · zurück zu heute" : (titel.last ?? "")).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
            }
            .buttonStyle(.plain)
            .disabled(!andereWoche)
            .accessibilityLabel(andereWoche ? "Zur laufenden Woche" : titel.joined(separator: ", "))
        }
        ToolbarItem(placement: .topBarTrailing) {
            Button { montag = Kalender.plus(7, montag) } label: { Image(systemName: "chevron.right").font(.headline) }
                .accessibilityLabel("Nächste Woche")
        }
    }

    @ViewBuilder
    private func tagesAbschnitt(_ tag: String, _ t: Plantafel) -> some View {
        let einsaetze = t.einsaetze(am: tag)
        let abwesend = t.abwesenheiten(am: tag)
        Section {
            if let feiertag = t.feiertage[tag] {
                Label(feiertag, systemImage: "star.fill").foregroundStyle(.orange)
            }
            ForEach(abwesend) { a in
                Label("\(a.userName ?? "Mitarbeiter"): \(a.artName)\(a.status == "beantragt" ? " (beantragt)" : "")", systemImage: "person.fill.xmark")
                    .foregroundStyle(.secondary)
            }
            if einsaetze.isEmpty && abwesend.isEmpty && t.feiertage[tag] == nil {
                Text("Keine Einsätze").foregroundStyle(.secondary)
            }
            ForEach(einsaetze) { e in
                NavigationLink(value: e) { EinsatzZeile(einsatz: e, mitDatum: false, mitMitarbeiter: true) }
            }
        } header: {
            HStack {
                Text(Kalender.kurz(tag)).font(.headline).foregroundStyle(tag == t.heute ? Color.marke : .primary)
                if tag == t.heute { Text("heute").font(.caption.bold()).foregroundStyle(Color.marke) }
                Spacer()
                if !einsaetze.isEmpty { Text("\(einsaetze.filter { !$0.abgesagt }.count) eingeteilt").font(.caption) }
            }
            .textCase(nil)
        }
    }

    private func laden() async {
        guard let client = sitzung.client else { return }
        laedt = true
        defer { laedt = false }
        do {
            tafel = try await client.plantafel(woche: montag)
            fehler = nil
        } catch {
            fehler = sitzung.meldung(error)
        }
    }
}
