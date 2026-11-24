// swift-tools-version: 6.0
// Kern der iPhone-App: Datenmodelle, Server-Zugriff, Schlüsselbund, Datumsregeln. Ohne Oberfläche, damit alles mit `swift test` auf dem Mac
// prüfbar ist (kein Simulator nötig). Keine fremden Abhängigkeiten.
import PackageDescription

let package = Package(
    name: "StundenzettelKern",
    defaultLocalization: "de",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "StundenzettelKern", targets: ["StundenzettelKern"])],
    targets: [
        .target(name: "StundenzettelKern"),
        .testTarget(name: "StundenzettelKernTests", dependencies: ["StundenzettelKern"], resources: [.copy("Beispiele")]),
    ]
)
