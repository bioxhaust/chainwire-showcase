import Foundation
import Vision

let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
let files = try FileManager.default.contentsOfDirectory(at: input, includingPropertiesForKeys: nil)
    .filter { $0.pathExtension.lowercased() == "jpg" }
    .sorted { (Int($0.deletingPathExtension().lastPathComponent) ?? 0) < (Int($1.deletingPathExtension().lastPathComponent) ?? 0) }
var rows: [String] = []
for file in files {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ru-RU", "en-US"]
    request.usesLanguageCorrection = true
    do {
        try VNImageRequestHandler(url: file, options: [:]).perform([request])
        let found = (request.results ?? []).compactMap { $0.topCandidates(1).first }
        let record: [String: Any] = ["file": file.lastPathComponent, "text": found.map { $0.string }.joined(separator: "\n"), "min_confidence": found.map { $0.confidence }.min() ?? 0]
        let data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
        rows.append(String(data: data, encoding: .utf8)!)
        print("\(file.lastPathComponent): \(found.count) lines")
    } catch {
        let data = try JSONSerialization.data(withJSONObject: ["file": file.lastPathComponent, "error": String(describing: error)], options: [.sortedKeys])
        rows.append(String(data: data, encoding: .utf8)!)
        print("\(file.lastPathComponent): OCR error")
    }
}
try (rows.joined(separator: "\n") + "\n").write(to: output, atomically: true, encoding: .utf8)
