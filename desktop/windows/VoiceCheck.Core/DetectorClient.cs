using System.Net.Http.Json;
using System.Text.Json;

namespace VoiceCheck.Core;

public record Verdict(string Label, double? Score = null);

public sealed class DetectorClient(HttpClient http)
{
    public static readonly Uri BaseAddress = new("http://127.0.0.1:8765/");

    public static HttpClient CreateLocalClient() => new(new HttpClientHandler
    {
        UseProxy = false, AllowAutoRedirect = false
    }) { BaseAddress = BaseAddress, Timeout = TimeSpan.FromSeconds(20) };

    // null means no listener yet; an unexpected service on this port is an error.
    public async Task<bool?> Ready(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await http.GetAsync(new Uri(BaseAddress, "health"), cancellationToken);
            response.EnsureSuccessStatusCode();
            var data = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken);
            if (!data.TryGetProperty("local", out var local) || local.ValueKind != JsonValueKind.True ||
                !data.TryGetProperty("ready", out var ready) || ready.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                throw new InvalidOperationException("Port 8765 is occupied by an unexpected service. Close it or use the browser to investigate.");
            return ready.GetBoolean();
        }
        catch (HttpRequestException exception) when (exception.StatusCode == null) { return null; }
    }

    public async Task<Verdict> Analyze(byte[] wav, CancellationToken cancellationToken)
    {
        using var body = new ByteArrayContent(wav);
        body.Headers.ContentType = new("application/octet-stream");
        using var response = await http.PostAsync(new Uri(BaseAddress, "analyze/live"), body, cancellationToken);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellationToken));
        var data = json.RootElement;
        if (!response.IsSuccessStatusCode)
            throw new InvalidOperationException(data.TryGetProperty("error", out var error) ? error.GetString() : "Local analysis failed.");
        if (data.GetProperty("status").GetString() == "insufficient_speech") return new("Waiting");
        var prediction = data.GetProperty("prediction").GetString();
        var score = data.GetProperty("synthetic_score").GetDouble();
        if (data.GetProperty("status").GetString() != "ok" || prediction is not ("AI" or "HUMAN") ||
            !double.IsFinite(score) || score < 0 || score > 1)
            throw new InvalidOperationException("The local detector returned an invalid prediction.");
        return new(prediction == "AI" ? "AI" : "Human", score);
    }
}
