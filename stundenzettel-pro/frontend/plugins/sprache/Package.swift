// swift-tools-version: 5.10
// Nativer Baustein „Sprache“ der App: Spracheingabe auf dem Gerät. iPhone: WhisperKit (Argmax, MIT), Rückfall Apple-Spracherkennung.
// Wird von `npx cap sync` in ios/App/CapApp-SPM eingebunden (Abhängigkeit "stundenzettel-sprache": "file:plugins/sprache").
import PackageDescription

let package = Package(
    name: "StundenzettelSprache",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "StundenzettelSprache", targets: ["SprachePlugin"])
    ],
    dependencies: [
        .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", from: "8.0.0"),
        .package(url: "https://github.com/argmaxinc/argmax-oss-swift.git", from: "1.1.0")
    ],
    targets: [
        .target(
            name: "SprachePlugin",
            dependencies: [
                .product(name: "Capacitor", package: "capacitor-swift-pm"),
                .product(name: "Cordova", package: "capacitor-swift-pm"),
                .product(name: "WhisperKit", package: "argmax-oss-swift")
            ],
            path: "ios/Sources/SprachePlugin")
    ]
)
