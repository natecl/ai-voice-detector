import Foundation
import ScreenCaptureKit
import AVFoundation
import CoreMedia

// PCM WAV encoding is shared with the capture self-test.
func pcmWAV(_ samples: [Float], sampleRate: Int = 16000) -> Data {
    var data = Data()
    func text(_ value: String) { data.append(value.data(using: .ascii)!) }
    func u16(_ value: UInt16) { var x = value.littleEndian; withUnsafeBytes(of: &x) { data.append(contentsOf: $0) } }
    func u32(_ value: UInt32) { var x = value.littleEndian; withUnsafeBytes(of: &x) { data.append(contentsOf: $0) } }
    text("RIFF"); u32(UInt32(36 + samples.count * 2)); text("WAVEfmt "); u32(16)
    u16(1); u16(1); u32(UInt32(sampleRate)); u32(UInt32(sampleRate * 2)); u16(2); u16(16)
    text("data"); u32(UInt32(samples.count * 2))
    for sample in samples { u16(UInt16(bitPattern: Int16(max(-1, min(1, sample.isFinite ? sample : 0)) * 32767))) }
    return data
}


// A 50 ms RMS envelope from the original PCM, before detector normalization.
struct AudioLevelMeter {
    private var energy: Double = 0
    private var count = 0
    mutating func consume(_ input: UnsafeBufferPointer<Float>) -> [Double] {
        var levels: [Double] = []
        for raw in input {
            let sample = raw.isFinite ? Double(raw) : 0
            energy += sample * sample
            count += 1
            if count == 800 {
                let rms = sqrt(energy / Double(count))
                let db = 20 * log10(max(rms, 0.000001))
                levels.append(max(0, min(1, (db + 60) / 48)))
                count = 0; energy = 0
            }
        }
        return levels
    }
}

@available(macOS 13.0, *)
final class SystemAudioCapture: NSObject, SCStreamOutput, SCStreamDelegate {
    private var stream: SCStream?
    private let queue = DispatchQueue(label: "voicecheck.audio")
    private var samples: [Float] = []
    private var active = false
    private var meter = AudioLevelMeter()
    private var activeStreamID: ObjectIdentifier?
    private var captureToken = UUID()
    private var token = UUID()
    private var request: URLSessionDataTask?
    private var busy = false
    private(set) var running = false
    var onEvent: (([String: Any]) -> Void)?

    func start() {
        guard !running else { return }
        running = true; token = UUID()
        let session = token
        onEvent?(["state":"starting", "message":"Requesting system-audio access…"])
        Task { @MainActor in
            do {
                let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
                guard running && token == session else { return }
                guard let display = content.displays.first else {
                    throw NSError(domain:"VoiceCheck", code:1, userInfo:[NSLocalizedDescriptionKey:"No display is available for system-audio capture."])
                }
                let excluded = content.applications.filter { $0.bundleIdentifier == Bundle.main.bundleIdentifier }
                let filter = SCContentFilter(display:display, excludingApplications:excluded, exceptingWindows:[])
                let config = SCStreamConfiguration()
                config.capturesAudio = true
                config.excludesCurrentProcessAudio = true
                config.sampleRate = 16000
                config.channelCount = 1
                config.width = 2; config.height = 2
                config.minimumFrameInterval = CMTime(value:1,timescale:1)
                // Only an audio output is registered; no screen frames are consumed or saved.
                let capture = SCStream(filter:filter, configuration:config, delegate:self)
                try capture.addStreamOutput(self, type:.audio, sampleHandlerQueue:queue)
                stream = capture
                queue.sync { samples.removeAll(); meter = AudioLevelMeter(); activeStreamID = ObjectIdentifier(capture); captureToken = session; active = true }
                try await capture.startCapture()
                guard running && token == session else { try? await capture.stopCapture(); return }
                onEvent?(["state":"listening", "message":"Listening to system audio · first result after 5 seconds of speech."])
            } catch {
                guard token == session else { return }
                stop()
                onEvent?(["state":"error", "message":"System audio could not start. Allow Voice Check in System Settings → Privacy & Security → Screen & System Audio Recording, then reopen the app. " + error.localizedDescription])
            }
        }
    }

    func stop() {
        running = false; token = UUID(); request?.cancel(); request = nil; busy = false
        queue.sync { active = false; activeStreamID = nil; meter = AudioLevelMeter(); samples.removeAll() }
        let previous = stream; stream = nil
        Task { try? await previous?.stopCapture() }
        onEvent?(["state":"stopped", "message":"System listening stopped."])
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        DispatchQueue.main.async {
            guard self.stream === stream else { return }
            self.stop()
            self.onEvent?(["state":"error", "message":"System capture stopped: " + error.localizedDescription])
        }
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, active, activeStreamID == ObjectIdentifier(stream), sampleBuffer.isValid,
              let description = sampleBuffer.formatDescription else { return }
        let format = AVAudioFormat(cmAudioFormatDescription:description)
        guard format.sampleRate == 16000, format.channelCount == 1 else { return }
        let frames = sampleBuffer.numSamples
        guard let pcm = AVAudioPCMBuffer(pcmFormat:format, frameCapacity:AVAudioFrameCount(frames)) else { return }
        pcm.frameLength = AVAudioFrameCount(frames)
        guard CMSampleBufferCopyPCMDataIntoAudioBufferList(sampleBuffer, at:0, frameCount:Int32(frames), into:pcm.mutableAudioBufferList) == noErr,
              let channels = pcm.floatChannelData else { return }
        let input = UnsafeBufferPointer(start:channels[0],count:frames)
        let levels = meter.consume(input)
        if !levels.isEmpty {
            let session = captureToken
            DispatchQueue.main.async { [weak self] in
                guard let self = self, self.running, self.token == session else { return }
                self.onEvent?(["state":"levels", "values":levels])
            }
        }
        samples.append(contentsOf:input)
        while samples.count >= 80000 {
            let segment = Array(samples.prefix(80000)); samples.removeFirst(80000)
            let wav = pcmWAV(segment)
            let session = captureToken
            DispatchQueue.main.async { [weak self] in
                guard let self = self, self.token == session else { return }
                self.analyze(wav)
            }
        }
    }

    private func analyze(_ wav: Data) {
        guard running, !busy else { return } // No stale backlog if inference slows down.
        busy = true
        let session = token
        onEvent?(["state":"analyzing", "message":"Analyzing the latest 5 seconds…"])
        var http = URLRequest(url:URL(string:"http://127.0.0.1:8765/analyze/live")!)
        http.httpMethod = "POST"; http.httpBody = wav; http.timeoutInterval = 15
        http.setValue("application/octet-stream",forHTTPHeaderField:"Content-Type")
        request = URLSession.shared.dataTask(with:http) { data,response,error in
            DispatchQueue.main.async {
                guard self.running && self.token == session else { return }
                self.busy = false; self.request = nil
                if let error = error {
                    self.onEvent?(["state":"warning", "message":"No result: " + error.localizedDescription]); return
                }
                guard let data = data, let result = (try? JSONSerialization.jsonObject(with:data)) as? [String:Any] else {
                    self.onEvent?(["state":"warning", "message":"The local detector returned an invalid response."]); return
                }
                guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                    self.onEvent?(["state":"warning", "message":result["error"] as? String ?? "Analysis failed."]); return
                }
                self.onEvent?(["state":"result", "result":result])
            }
        }
        request?.resume()
    }
}
