import SwiftUI
import StundenzettelKern

/// Anmeldung mit dem bestehenden Konto (Chef, Büro, Mitarbeiter). Mitarbeiter legen ihr Passwort vorher über den Einladungslink fest.
struct AnmeldeAnsicht: View {
    @Environment(Sitzung.self) private var sitzung
    @State private var email = ""
    @State private var passwort = ""
    @State private var fehler: String?
    @State private var laeuft = false
    @State private var serverZeigen = false
    @FocusState private var feld: Feld?

    enum Feld { case email, passwort }

    var body: some View {
        @Bindable var sitzung = sitzung
        ScrollView {
            VStack(spacing: 16) {
                Image(systemName: "calendar.badge.clock").font(.system(size: 44)).foregroundStyle(Color.marke).padding(.top, 32)
                Text("Stundenzettel Pro").font(.title.bold())
                Text("Mit deinem Firmenkonto anmelden").font(.body).foregroundStyle(.secondary)

                VStack(spacing: 12) {
                    TextField("E-Mail", text: $email)
                        .textContentType(.username)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($feld, equals: .email)
                        .submitLabel(.next)
                        .onSubmit { feld = .passwort }
                        .eingabefeld()
                    SecureField("Passwort", text: $passwort)
                        .textContentType(.password)
                        .focused($feld, equals: .passwort)
                        .submitLabel(.go)
                        .onSubmit { anmelden() }
                        .eingabefeld()
                }

                if let fehler {
                    Label(fehler, systemImage: "exclamationmark.triangle.fill")
                        .font(.body.weight(.medium)).foregroundStyle(.red).frame(maxWidth: .infinity, alignment: .leading)
                }

                Button(action: anmelden) {
                    if laeuft { ProgressView().tint(.white) } else { Text("Anmelden") }
                }
                .buttonStyle(GrosserKnopf())
                .disabled(laeuft || email.isEmpty || passwort.isEmpty)

                DisclosureGroup("Server-Adresse", isExpanded: $serverZeigen) {
                    TextField("https://pro.deine-firma.de", text: $sitzung.serverAdresse)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .eingabefeld()
                        .padding(.top, 8)
                }
                .font(.body)
                .tint(.primary)

                Text("Noch kein Passwort? Den Einladungslink aus der E-Mail deines Betriebs öffnen und dort ein Passwort festlegen.")
                    .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(20)
        }
        .scrollDismissesKeyboard(.interactively)
        .onAppear { serverZeigen = sitzung.serverAdresse.isEmpty }
    }

    private func anmelden() {
        guard !laeuft, !email.isEmpty, !passwort.isEmpty else { return }
        laeuft = true
        fehler = nil
        Task {
            defer { laeuft = false }
            do {
                try await sitzung.anmelden(email: email, passwort: passwort)
                passwort = ""
            } catch {
                fehler = error.localizedDescription
                if case APIFehler.ungueltigeAdresse = error { serverZeigen = true }
            }
        }
    }
}

extension View {
    /// Eingabefeld (50 pt hoch).
    func eingabefeld() -> some View {
        self.font(.body)
            .padding(.horizontal, 14)
            .frame(minHeight: 50)
            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}
