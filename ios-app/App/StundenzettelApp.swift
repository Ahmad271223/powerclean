import SwiftUI
import StundenzettelKern

@main
struct StundenzettelApp: App {
    @State private var sitzung = Sitzung()

    var body: some Scene {
        WindowGroup {
            StartAnsicht()
                .environment(sitzung)
                .tint(.marke)
        }
    }
}

struct StartAnsicht: View {
    @Environment(Sitzung.self) private var sitzung

    var body: some View {
        Group {
            switch sitzung.zustand {
            case .startet:
                ProgressView("Anmeldung wird geprüft …").controlSize(.large)
            case .offline(let text):
                OfflineAnsicht(text: text)
            case .abgemeldet:
                AnmeldeAnsicht()
            case .angemeldet:
                Hauptansicht()
            }
        }
        .task { await sitzung.starten() }
    }
}

/// Planer (Inhaber, Büro mit Plantafel-Recht): Plantafel zuerst. Alle anderen: eigene Einteilungen.
struct Hauptansicht: View {
    @Environment(Sitzung.self) private var sitzung

    var body: some View {
        TabView {
            if sitzung.darfPlanen {
                NavigationStack { PlantafelWochenAnsicht() }
                    .tabItem { Label("Plantafel", systemImage: "calendar") }
            }
            NavigationStack { MeineEinteilungenAnsicht() }
                .tabItem { Label("Meine Einsätze", systemImage: "person.crop.circle.badge.clock") }
            NavigationStack { EinstellungenAnsicht() }
                .tabItem { Label("Einstellungen", systemImage: "gearshape") }
        }
    }
}

struct OfflineAnsicht: View {
    @Environment(Sitzung.self) private var sitzung
    let text: String

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "wifi.exclamationmark").font(.system(size: 64)).foregroundStyle(.secondary)
            Text("Server nicht erreichbar").font(.title2.bold())
            Text(text).font(.body).multilineTextAlignment(.center).foregroundStyle(.secondary)
            Button("Erneut versuchen") { Task { await sitzung.starten() } }.buttonStyle(GrosserKnopf())
            Button("Abmelden", role: .destructive) { sitzung.abmelden() }.buttonStyle(GrosserKnopf(art: .zweitrangig))
        }
        .padding(24)
    }
}
