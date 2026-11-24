import AVFoundation
import Capacitor
import Foundation
import Speech
import WhisperKit

/// Spracheingabe auf dem iPhone – gedrückt halten zum Sprechen, loslassen = Text.
///
/// Datenschutz: Die Aufnahme liegt nur im Arbeitsspeicher, wird auf dem Gerät erkannt und danach verworfen – nie gespeichert, nie hochgeladen.
/// Erkennung: WhisperKit (Argmax, MIT) mit einem Modell passend zum iPhone (ab ~8 GB Arbeitsspeicher „Turbo“, sonst „Small“), das beim ersten
/// Nutzen geladen wird. Rückfall: Apples Spracherkennung, aber nur wenn sie auf dem Gerät läuft (requiresOnDeviceRecognition).
@objc(SprachePlugin)
public class SprachePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "SprachePlugin"
    public let jsName = "Sprache"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "modellLaden", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "aufnahmeStarten", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "aufnahmeBeenden", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "aufnahmeAbbrechen", returnType: CAPPluginReturnPromise),
    ]

    private let kern = SprachKern()

    @objc func status(_ call: CAPPluginCall) {
        Task {
            call.resolve(await kern.status())
        }
    }

    @objc func modellLaden(_ call: CAPPluginCall) {
        Task {
            do {
                let modell = try await kern.modellLaden { anteil in
                    self.notifyListeners("fortschritt", data: ["anteil": anteil])
                }
                call.resolve(["modell": modell])
            } catch {
                call.reject(SprachKern.klartext(error))
            }
        }
    }

    @objc func aufnahmeStarten(_ call: CAPPluginCall) {
        Task {
            do {
                try await kern.aufnahmeStarten()
                call.resolve()
            } catch {
                call.reject(SprachKern.klartext(error))
            }
        }
    }

    @objc func aufnahmeBeenden(_ call: CAPPluginCall) {
        Task {
            do {
                let (text, engine) = try await kern.aufnahmeBeenden()
                call.resolve(["text": text, "engine": engine])
            } catch {
                call.reject(SprachKern.klartext(error))
            }
        }
    }

    @objc func aufnahmeAbbrechen(_ call: CAPPluginCall) {
        Task {
            await kern.aufnahmeAbbrechen()
            call.resolve()
        }
    }
}

enum SprachFehler: LocalizedError {
    case keinMikrofon, keineSpracherkennung, nichtsGehoert, laeuftNicht, modellFehlt

    var errorDescription: String? {
        switch self {
        case .keinMikrofon: "Kein Zugriff aufs Mikrofon. Bitte in den iPhone-Einstellungen bei „Stundenzettel Pro“ erlauben."
        case .keineSpracherkennung: "Spracherkennung auf diesem iPhone nicht möglich, ohne die Aufnahme zu versenden. Bitte den Text eintippen."
        case .nichtsGehoert: "Nichts verstanden. Bitte noch einmal deutlich sprechen."
        case .laeuftNicht: "Es läuft keine Aufnahme."
        case .modellFehlt: "Das Sprachmodell ist noch nicht geladen."
        }
    }
}

/// Die eigentliche Arbeit, abgeschirmt in einem Actor (Aufnahme, Modell, Erkennung).
actor SprachKern {
    static let modellKlein = "openai_whisper-small_216MB"
    static let modellTurbo = "openai_whisper-large-v3-v20240930_turbo_632MB"

    /// Neuere iPhones (15 Pro und neuer, ~8 GB) schaffen Turbo flüssig; ältere bekommen Small.
    static var passendesModell: String { ProcessInfo.processInfo.physicalMemory >= 7_000_000_000 ? modellTurbo : modellKlein }
    static var modellGroesseMB: Int { passendesModell == modellTurbo ? 632 : 216 }

    private var whisper: WhisperKit?
    private var motor: AVAudioEngine?
    private var konverter: AVAudioConverter?
    private var proben: [Float] = []           // 16 kHz Mono – nur im Arbeitsspeicher
    private var puffer: [AVAudioPCMBuffer] = []  // Originalformat für den Apple-Rückfall

    static func klartext(_ fehler: Error) -> String {
        (fehler as? LocalizedError)?.errorDescription ?? "Spracheingabe fehlgeschlagen: \(fehler.localizedDescription)"
    }

    private var ablage: URL {
        let basis = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Sprachmodelle", isDirectory: true)
        try? FileManager.default.createDirectory(at: basis, withIntermediateDirectories: true)
        var url = basis
        var werte = URLResourceValues()
        werte.isExcludedFromBackup = true   // Modell nicht in iCloud-Backups (lässt sich jederzeit neu laden)
        try? url.setResourceValues(werte)
        return basis
    }

    private func modellOrdner(_ name: String) -> URL? {
        let fm = FileManager.default
        guard let treffer = fm.enumerator(at: ablage, includingPropertiesForKeys: nil) else { return nil }
        for case let url as URL in treffer where url.lastPathComponent == name && url.hasDirectoryPath {
            if (try? fm.contentsOfDirectory(atPath: url.path))?.contains(where: { $0.hasSuffix(".mlmodelc") }) == true { return url }
        }
        return nil
    }

    func status() -> [String: Any] {
        let mikrofon: String
        switch AVAudioSession.sharedInstance().recordPermission {
        case .granted: mikrofon = "erlaubt"
        case .denied: mikrofon = "verweigert"
        default: mikrofon = "unbekannt"
        }
        let apple = SFSpeechRecognizer(locale: Locale(identifier: "de-DE"))
        return ["plattform": "ios", "engine": "whisperkit", "modell": Self.passendesModell, "modellGroesseMB": Self.modellGroesseMB,
                "modellGeladen": modellOrdner(Self.passendesModell) != nil, "mikrofon": mikrofon,
                "rueckfallAufGeraet": apple?.supportsOnDeviceRecognition == true]
    }

    /// Lädt das passende Modell (einmalig, mit Fortschritt 0…1) und hält es bereit.
    func modellLaden(fortschritt: @escaping @Sendable (Double) -> Void) async throws -> String {
        if whisper != nil { return Self.passendesModell }
        let name = Self.passendesModell
        let ordner: URL
        if let vorhanden = modellOrdner(name) {
            ordner = vorhanden
        } else {
            ordner = try await WhisperKit.download(variant: name, downloadBase: ablage) { p in fortschritt(p.fractionCompleted) }
        }
        fortschritt(1)
        let config = WhisperKitConfig(model: name, downloadBase: ablage, modelFolder: ordner.path, verbose: false, logLevel: .error,
                                      prewarm: true, load: true, download: false)
        whisper = try await WhisperKit(config)
        return name
    }

    func aufnahmeStarten() async throws {
        aufnahmeAbbrechen()
        let erlaubt = await withCheckedContinuation { (fortsetzen: CheckedContinuation<Bool, Never>) in
            AVAudioSession.sharedInstance().requestRecordPermission { fortsetzen.resume(returning: $0) }
        }
        guard erlaubt else { throw SprachFehler.keinMikrofon }
        let sitzung = AVAudioSession.sharedInstance()
        try sitzung.setCategory(.playAndRecord, mode: .measurement, options: [.duckOthers, .defaultToSpeaker])
        try sitzung.setActive(true, options: .notifyOthersOnDeactivation)

        let motor = AVAudioEngine()
        let eingang = motor.inputNode
        let format = eingang.outputFormat(forBus: 0)
        guard let ziel = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16_000, channels: 1, interleaved: false),
              let konverter = AVAudioConverter(from: format, to: ziel) else { throw SprachFehler.keinMikrofon }
        proben = []
        puffer = []
        self.konverter = konverter
        eingang.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            guard let kopie = buffer.kopie() else { return }
            Task { await self?.aufnehmen(kopie, ziel: ziel) }
        }
        motor.prepare()
        try motor.start()
        self.motor = motor
    }

    private func aufnehmen(_ buffer: AVAudioPCMBuffer, ziel: AVAudioFormat) {
        puffer.append(buffer)
        guard let konverter else { return }
        let kapazitaet = AVAudioFrameCount(Double(buffer.frameLength) * ziel.sampleRate / buffer.format.sampleRate) + 32
        guard let aus = AVAudioPCMBuffer(pcmFormat: ziel, frameCapacity: kapazitaet) else { return }
        var geliefert = false
        var fehler: NSError?
        konverter.convert(to: aus, error: &fehler) { _, status in
            if geliefert { status.pointee = .noDataNow; return nil }
            geliefert = true
            status.pointee = .haveData
            return buffer
        }
        if fehler == nil, let kanal = aus.floatChannelData?[0] {
            proben.append(contentsOf: UnsafeBufferPointer(start: kanal, count: Int(aus.frameLength)))
        }
    }

    private func stoppen() {
        motor?.inputNode.removeTap(onBus: 0)
        motor?.stop()
        motor = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    func aufnahmeAbbrechen() {
        stoppen()
        proben = []
        puffer = []
    }

    /// Aufnahme beenden und erkennen. Danach ist die Aufnahme verworfen.
    func aufnahmeBeenden() async throws -> (String, String) {
        guard motor != nil else { throw SprachFehler.laeuftNicht }
        stoppen()
        // kurze Pause, damit die letzten Puffer aus dem Tap ankommen
        try? await Task.sleep(nanoseconds: 120_000_000)
        let audio = proben
        let originale = puffer
        proben = []
        puffer = []
        guard audio.count > 16_000 / 2 else { throw SprachFehler.nichtsGehoert }   // unter einer halben Sekunde
        if whisper == nil, modellOrdner(Self.passendesModell) != nil {
            _ = try? await modellLaden { _ in }
        }
        if let whisper {
            let optionen = DecodingOptions(task: .transcribe, language: "de", temperature: 0, usePrefillPrompt: true, detectLanguage: false,
                                           skipSpecialTokens: true, withoutTimestamps: true)
            let ergebnis = try await whisper.transcribe(audioArray: audio, decodeOptions: optionen)
            let text = ergebnis.map(\.text).joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { throw SprachFehler.nichtsGehoert }
            return (text, "whisperkit")
        }
        return (try await apple(originale), "apple")
    }

    /// Rückfall: Apple-Spracherkennung – nur auf dem Gerät, sonst Fehler (die Aufnahme verlässt das iPhone nie).
    private func apple(_ puffer: [AVAudioPCMBuffer]) async throws -> String {
        let erlaubt = await withCheckedContinuation { (fortsetzen: CheckedContinuation<Bool, Never>) in
            SFSpeechRecognizer.requestAuthorization { fortsetzen.resume(returning: $0 == .authorized) }
        }
        guard erlaubt, let erkenner = SFSpeechRecognizer(locale: Locale(identifier: "de-DE")), erkenner.supportsOnDeviceRecognition else {
            throw SprachFehler.keineSpracherkennung
        }
        let anfrage = SFSpeechAudioBufferRecognitionRequest()
        anfrage.requiresOnDeviceRecognition = true
        anfrage.shouldReportPartialResults = false
        anfrage.taskHint = .dictation
        puffer.forEach { anfrage.append($0) }
        anfrage.endAudio()
        return try await withCheckedThrowingContinuation { fortsetzen in
            var fertig = false
            erkenner.recognitionTask(with: anfrage) { ergebnis, fehler in
                if fertig { return }
                if let ergebnis, ergebnis.isFinal {
                    fertig = true
                    let text = ergebnis.bestTranscription.formattedString.trimmingCharacters(in: .whitespacesAndNewlines)
                    text.isEmpty ? fortsetzen.resume(throwing: SprachFehler.nichtsGehoert) : fortsetzen.resume(returning: text)
                } else if fehler != nil {
                    fertig = true
                    fortsetzen.resume(throwing: SprachFehler.nichtsGehoert)
                }
            }
        }
    }
}

private extension AVAudioPCMBuffer {
    /// Eigene Kopie – der Tap-Puffer wird von AVAudioEngine wiederverwendet.
    func kopie() -> AVAudioPCMBuffer? {
        guard let neu = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameLength) else { return nil }
        neu.frameLength = frameLength
        let kanaele = Int(format.channelCount)
        if let von = floatChannelData, let nach = neu.floatChannelData {
            for k in 0..<kanaele { nach[k].update(from: von[k], count: Int(frameLength)) }
            return neu
        }
        return nil
    }
}
