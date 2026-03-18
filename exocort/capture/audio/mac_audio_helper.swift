import Foundation
import ScreenCaptureKit
import CoreMedia
import AudioToolbox

final class AudioCapture: NSObject, SCStreamOutput, SCStreamDelegate {
    private let output = FileHandle.standardOutput
    private var wroteHeader = false
    private let sampleRate: Int
    private let channels: Int

    init(sampleRate: Int, channels: Int) {
        self.sampleRate = sampleRate
        self.channels = channels
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio else { return }
        guard CMSampleBufferDataIsReady(sampleBuffer) else { return }
        guard let formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer) else { return }
        guard let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc)?.pointee else { return }

        if !wroteHeader {
            let header: [String: Any] = [
                "sample_rate": Int(asbd.mSampleRate),
                "channels": Int(asbd.mChannelsPerFrame),
                "format": "s16le",
            ]
            if let data = try? JSONSerialization.data(withJSONObject: header, options: []) {
                output.write(data)
                output.write("\n".data(using: .utf8)!)
            }
            wroteHeader = true
        }

        let bufferList = AudioBufferList.allocate(maximumBuffers: Int(asbd.mChannelsPerFrame))
        defer { bufferList.unsafeMutablePointer.deallocate() }
        var blockBuffer: CMBlockBuffer?
        let bufferListSize = MemoryLayout<AudioBufferList>.size + (MemoryLayout<AudioBuffer>.size * max(1, Int(asbd.mChannelsPerFrame) - 1))
        let status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
            sampleBuffer,
            bufferListSizeNeededOut: nil,
            bufferListOut: bufferList.unsafeMutablePointer,
            bufferListSize: bufferListSize,
            blockBufferAllocator: kCFAllocatorDefault,
            blockBufferMemoryAllocator: kCFAllocatorDefault,
            flags: 0,
            blockBufferOut: &blockBuffer
        )

        if status != noErr {
            return
        }

        let isFloat = (asbd.mFormatFlags & kAudioFormatFlagIsFloat) != 0
        let isSignedInt = (asbd.mFormatFlags & kAudioFormatFlagIsSignedInteger) != 0
        let isNonInterleaved = (asbd.mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0
        let bits = Int(asbd.mBitsPerChannel)
        let frames = Int(CMSampleBufferGetNumSamples(sampleBuffer))
        let channelCount = Int(asbd.mChannelsPerFrame)

        if !isNonInterleaved, isSignedInt, bits == 16 {
            let buffer = bufferList.unsafeMutablePointer.pointee.mBuffers
            if let data = buffer.mData {
                let count = Int(buffer.mDataByteSize)
                output.write(Data(bytes: data, count: count))
            }
            return
        }

        if isFloat && bits == 32 {
            var list = bufferList.unsafeMutablePointer.pointee
            writeFloatBuffer(
                audioBufferList: &list,
                frames: frames,
                channels: channelCount,
                interleaved: !isNonInterleaved
            )
            return
        }
    }

    private func writeFloatBuffer(audioBufferList: inout AudioBufferList, frames: Int, channels: Int, interleaved: Bool) {
        if interleaved {
            let buffer = audioBufferList.mBuffers
            guard let data = buffer.mData else { return }
            let count = Int(buffer.mDataByteSize) / MemoryLayout<Float>.size
            let floatPtr = data.bindMemory(to: Float.self, capacity: count)
            var out = [Int16](repeating: 0, count: count)
            for i in 0..<count {
                let sample = max(-1.0, min(1.0, floatPtr[i]))
                out[i] = Int16(sample * 32767.0)
            }
            out.withUnsafeBytes { raw in
                output.write(Data(raw))
            }
            return
        }

        var out = [Int16](repeating: 0, count: frames * channels)
        let buffers = UnsafeMutableAudioBufferListPointer(&audioBufferList)
        if buffers.count < channels {
            return
        }
        for ch in 0..<channels {
            guard let data = buffers[ch].mData else { continue }
            let count = frames
            let floatPtr = data.bindMemory(to: Float.self, capacity: count)
            for i in 0..<count {
                let sample = max(-1.0, min(1.0, floatPtr[i]))
                out[i * channels + ch] = Int16(sample * 32767.0)
            }
        }
        out.withUnsafeBytes { raw in
            output.write(Data(raw))
        }
    }
}

func parseArg(_ name: String, defaultValue: Int) -> Int {
    let args = CommandLine.arguments
    guard let idx = args.firstIndex(of: name), idx + 1 < args.count else {
        return defaultValue
    }
    return Int(args[idx + 1]) ?? defaultValue
}

let sampleRate = parseArg("--sample-rate", defaultValue: 48000)
let channels = parseArg("--channels", defaultValue: 2)

let semaphore = DispatchSemaphore(value: 0)
var shareableContent: SCShareableContent?

SCShareableContent.getExcludingDesktopWindows(false, onScreenWindowsOnly: true) { content, _ in
    shareableContent = content
    semaphore.signal()
}
_ = semaphore.wait(timeout: .now() + 5.0)

guard let content = shareableContent, let display = content.displays.first else {
    fputs("No display available for ScreenCaptureKit\n", stderr)
    exit(1)
}

let filter = SCContentFilter(display: display, excludingWindows: [])
let config = SCStreamConfiguration()
config.capturesAudio = true
config.sampleRate = sampleRate
config.channelCount = channels
config.minimumFrameInterval = CMTime(value: 1, timescale: 60)

let capture = AudioCapture(sampleRate: sampleRate, channels: channels)
let stream = SCStream(filter: filter, configuration: config, delegate: capture)
let queue = DispatchQueue(label: "mac.audio.capture.queue")
try stream.addStreamOutput(capture, type: .audio, sampleHandlerQueue: queue)

var shouldStop = false
let signalSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
signal(SIGINT, SIG_IGN)
signalSource.setEventHandler {
    shouldStop = true
}
signalSource.resume()

stream.startCapture { error in
    if let error = error {
        fputs("Start capture failed: \(error)\n", stderr)
        exit(1)
    }
}

while !shouldStop {
    RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.1))
}

stream.stopCapture { _ in
    exit(0)
}
