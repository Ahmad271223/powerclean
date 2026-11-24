import SwiftUI

/// Großer runder Mikrofon-Knopf der Plantafel. Schritt 1: nur der Platz und die Bedienung; die Spracherkennung (WhisperKit, gedrückt halten)
/// und der Einteilungsvorschlag kommen in Schritt 3 bis 5. Es wird nichts aufgenommen.
struct MikrofonKnopf: View {
    @State private var hinweis = false

    var body: some View {
        Button { hinweis = true } label: {
            Image(systemName: "mic.fill")
                .font(.system(size: 40, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 96, height: 96)
                .background(Color.marke, in: Circle())
                .shadow(color: .black.opacity(0.25), radius: 8, y: 4)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Einteilung sprechen")
        .accessibilityHint("Mitarbeiter, Projekt, Zeit und Tage ansagen")
        .alert("Einteilung per Sprache", isPresented: $hinweis) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Kommt im nächsten Schritt: Knopf gedrückt halten, z. B. „Nils ab Montag Badsanierung Müller, 7 bis 16 Uhr“ sagen, Vorschlag prüfen und bestätigen.")
        }
    }
}
