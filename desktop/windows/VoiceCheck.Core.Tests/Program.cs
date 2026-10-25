using System.Buffers.Binary;
using System.Net;
using System.Text;
using VoiceCheck.Core;

static void Check(bool condition, string message) { if (!condition) throw new Exception(message); }
static byte[] Floats(int frames, int channels, float value)
{
    var bytes = new byte[frames * channels * 4];
    for (var i = 0; i < frames * channels; i++) BinaryPrimitives.WriteSingleLittleEndian(bytes.AsSpan(i * 4), value);
    return bytes;
}

// Stereo device-rate audio is downmixed and segmented into exact 5-second PCM WAVs.
List<byte[]> windows = []; List<double> levels = [];
var audio = new AudioPipeline(48000, 2, 32, true);
audio.Window += windows.Add; audio.Levels += batch => levels.AddRange(batch);
var input = Floats(48000 * 10, 2, .125f);
// Uneven buffer boundaries must not change meter or inference segmentation.
for (var start = 0; start < input.Length; start += 193 * 8)
    audio.Feed(input.AsSpan(start, Math.Min(193 * 8, input.Length - start)));
Check(windows.Count == 2 && levels.Count == 200, "Device-rate segmentation or 20 Hz envelope failed.");
var wav = windows[0];
Check(Encoding.ASCII.GetString(wav, 0, 4) == "RIFF" && Encoding.ASCII.GetString(wav, 8, 4) == "WAVE", "Invalid WAV header.");
Check(BinaryPrimitives.ReadInt32LittleEndian(wav.AsSpan(24)) == 48000, "WAV rate must match the capture device.");
Check(BinaryPrimitives.ReadInt16LittleEndian(wav.AsSpan(22)) == 1 && wav.Length == 44 + 48000 * 5 * 2, "Expected five-second mono PCM.");
Check(Math.Abs(BinaryPrimitives.ReadInt16LittleEndian(wav.AsSpan(44)) / 32767.0 - .125) < .0001, "Downmix changed sample amplitude.");
Check(levels.All(level => level > 0 && level <= 1), "Invalid meter levels.");

// Reset prevents joining old partial speech to audio after a silence or session gap.
windows.Clear(); audio.Feed(Floats(48000 * 4, 2, .1f)); audio.Reset();
audio.Feed(Floats(48000, 2, .1f)); Check(windows.Count == 0, "Reset retained a partial window.");

foreach (var bits in new[] { 16, 24, 32 })
{
    List<double> pcmLevels = [];
    var pipeline = new AudioPipeline(16000, 1, bits, false);
    pipeline.Levels += values => pcmLevels.AddRange(values);
    pipeline.Feed(new byte[800 * bits / 8]);
    Check(pcmLevels.Count == 1 && pcmLevels[0] == 0, "PCM silence should have a zero level.");
    byte[]? encoded = null; pipeline.Window += value => encoded = value;
    var negativeFullScale = new byte[80000 * bits / 8];
    for (var i = bits / 8 - 1; i < negativeFullScale.Length; i += bits / 8) negativeFullScale[i] = 128;
    pipeline.Reset(); pipeline.Feed(negativeFullScale);
    Check(encoded != null && BinaryPrimitives.ReadInt16LittleEndian(encoded.AsSpan(44)) == -32767, "Signed PCM conversion failed.");
}
var finite = new AudioPipeline(16000, 1, 32, true);
List<double> safe = []; finite.Levels += values => safe.AddRange(values);
finite.Feed(Floats(800, 1, float.NaN)); finite.Feed(Floats(800, 1, float.PositiveInfinity)); finite.Feed(Floats(800, 1, 4));
Check(safe.SequenceEqual(new double[] { 0, 0, 1 }), "Non-finite/clipped input corrupted meter.");

var stub = new StubHandler();
using var client = new HttpClient(stub);
var detector = new DetectorClient(client);
foreach (var (prediction, label, score) in new[] { ("HUMAN", "Human", .1), ("AI", "AI", .9) })
{
    stub.Json = $$"""{"status":"ok","prediction":"{{prediction}}","synthetic_score":{{score.ToString(System.Globalization.CultureInfo.InvariantCulture)}}} """;
    var verdict = await detector.Analyze(wav, CancellationToken.None);
    Check(verdict.Label == label && verdict.Score == score, "Wrong verdict mapping.");
    Check(stub.LastUri == "http://127.0.0.1:8765/analyze/live" && stub.Audio!.SequenceEqual(wav), "Audio must be raw WAV to the loopback-only endpoint.");
}
stub.Json = """{"status":"insufficient_speech"}""";
Check((await detector.Analyze(wav, CancellationToken.None)).Label == "Waiting", "Silence produced a verdict.");
stub.Json = """{"status":"ok","prediction":"AI","synthetic_score":2}""";
try { await detector.Analyze(wav, CancellationToken.None); throw new Exception("Invalid prediction accepted."); }
catch (InvalidOperationException) { }
stub.Status = HttpStatusCode.ServiceUnavailable; stub.Json = """{"error":"model unavailable"}""";
try { await detector.Analyze(wav, CancellationToken.None); throw new Exception("HTTP failure accepted."); }
catch (InvalidOperationException exception) { Check(exception.Message == "model unavailable", "Backend error lost."); }
stub.Status = HttpStatusCode.OK; stub.Json = """{"local":true,"ready":true}""";
Check(await detector.Ready(CancellationToken.None) == true, "Health contract rejected.");
stub.Json = """{"ready":true}""";
try { await detector.Ready(CancellationToken.None); throw new Exception("Unexpected service accepted."); }
catch (InvalidOperationException) { }
using var canceled = new CancellationTokenSource(); canceled.Cancel();
try { await detector.Analyze(wav, canceled.Token); throw new Exception("Canceled session accepted."); }
catch (OperationCanceledException) { }
// Optional real-model integration: two 48 kHz stereo PCM16 fixture files, human then AI.
if (args.Length == 3 && args[0] == "--integration")
{
    using var liveHttp = DetectorClient.CreateLocalClient();
    var live = new DetectorClient(liveHttp);
    Check(await live.Ready(CancellationToken.None) == true, "Start app.py before integration checks.");
    for (var i = 1; i <= 2; i++)
    {
        var raw = File.ReadAllBytes(args[i]);
        byte[]? segment = null;
        var pipeline = new AudioPipeline(48000, 2, 16, false);
        pipeline.Window += bytes => segment ??= bytes;
        pipeline.Feed(raw);
        Check(segment != null, "Fixture must contain at least five seconds of speech.");
        var result = await live.Analyze(segment!, CancellationToken.None);
        var expected = i == 1 ? "Human" : "AI";
        Check(result.Label == expected, $"Real model integration: expected {expected}, got {result.Label}.");
        Console.WriteLine($"Integration: {expected} fixture -> {result.Label}, synthetic score {result.Score:0.000}");
    }
}
Console.WriteLine("PASS: device-rate WAV, downmix, chunk boundaries, reset, PCM formats, RMS/silence/non-finite input, local API, verdicts, errors, cancellation.");

sealed class StubHandler : HttpMessageHandler
{
    public string Json = "{}";
    public HttpStatusCode Status = HttpStatusCode.OK;
    public string? LastUri;
    public byte[]? Audio;
    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        LastUri = request.RequestUri!.ToString();
        if (request.Content != null) Audio = await request.Content.ReadAsByteArrayAsync(cancellationToken);
        return new(Status) { Content = new StringContent(Json, Encoding.UTF8, "application/json") };
    }
}
