using System;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Threading;
using NAudio.CoreAudioApi;
using NAudio.Wave;
using VoiceCheck.Core;

namespace VoiceCheck.Windows;

public sealed class LoopbackSession(DetectorClient detector, Dispatcher dispatcher) : IDisposable
{
    private sealed class Session
    {
        public readonly CancellationTokenSource Cancellation = new();
        public required WasapiLoopbackCapture Capture;
        public required MMDevice Device;
        public required AudioPipeline Pipeline;
        public long LastDataAt = Environment.TickCount64;
        public int InFlight;
        public int Epoch;
    }
    private volatile Session? current;
    public event Action<string, string?, Verdict?>? Changed;
    public event Action<double[]>? Levels;
    public bool Running => current != null;
    public long LastDataAt => current == null ? 0 : Interlocked.Read(ref current.LastDataAt);
    public string DeviceName { get; private set; } = "Default output";

    public void Start(string? deviceId)
    {
        Stop();
        MMDevice? device = null;
        WasapiLoopbackCapture? capture = null;
        try
        {
            using var enumerator = new MMDeviceEnumerator();
            device = deviceId == null ? enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia) : enumerator.GetDevice(deviceId);
            capture = new WasapiLoopbackCapture(device);
            var format = capture.WaveFormat;
            if (format.Encoding is not (WaveFormatEncoding.IeeeFloat or WaveFormatEncoding.Pcm))
                throw new InvalidOperationException("Unsupported output format. Choose a standard PCM playback device.");
            var pipeline = new AudioPipeline(format.SampleRate, format.Channels, format.BitsPerSample, format.Encoding == WaveFormatEncoding.IeeeFloat);
            var session = new Session { Capture = capture, Device = device, Pipeline = pipeline };
            current = session;
            DeviceName = device.FriendlyName;
            pipeline.Levels += values => Post(session, () => Levels?.Invoke(values));
            pipeline.Window += wav =>
            {
                if (Interlocked.CompareExchange(ref session.InFlight, 1, 0) == 0)
                    _ = Analyze(session, wav, Volatile.Read(ref session.Epoch)); // Never queue a backlog of old speech.
            };
            capture.DataAvailable += (_, args) =>
            {
                if (!ReferenceEquals(current, session) || args.BytesRecorded == 0) return;
                try
                {
                    var now = Environment.TickCount64;
                    // NAudio may emit no packets during silence. Never join speech across a long gap.
                    if (now - Interlocked.Read(ref session.LastDataAt) > 500)
                    {
                        Interlocked.Increment(ref session.Epoch);
                        pipeline.Reset();
                    }
                    Interlocked.Exchange(ref session.LastDataAt, now);
                    pipeline.Feed(args.Buffer.AsSpan(0, args.BytesRecorded));
                }
                catch (Exception exception) { Post(session, () => Fail(exception.Message)); }
            };
            capture.RecordingStopped += (_, args) => Post(session, () => Fail(args.Exception?.Message ?? "The output device stopped. Select an available output and start again."));
            capture.StartRecording();
            Changed?.Invoke("listening", "Listening to " + DeviceName, null);
        }
        catch
        {
            if (current != null) Stop();
            else { capture?.Dispose(); device?.Dispose(); }
            throw;
        }
    }

    private void Post(Session session, Action action) => dispatcher.BeginInvoke(() =>
    {
        if (ReferenceEquals(current, session) && !session.Cancellation.IsCancellationRequested) action();
    });

    private async Task Analyze(Session session, byte[] wav, int epoch)
    {
        try
        {
            Post(session, () => Changed?.Invoke("analyzing", null, null));
            var result = await detector.Analyze(wav, session.Cancellation.Token).ConfigureAwait(false);
            Post(session, () =>
            {
                if (epoch != Volatile.Read(ref session.Epoch)) return;
                if (Environment.TickCount64 - Interlocked.Read(ref session.LastDataAt) > 1000) result = new("Waiting");
                Changed?.Invoke("result", null, result);
            });
        }
        catch (OperationCanceledException) when (session.Cancellation.IsCancellationRequested) { }
        catch (Exception exception) { Post(session, () => Changed?.Invoke("warning", exception.Message, null)); }
        finally { Interlocked.Exchange(ref session.InFlight, 0); }
    }

    private void Fail(string message) { Stop(); Changed?.Invoke("error", message, null); }
    public void Stop()
    {
        var previous = current;
        current = null; // Invalidate queued UI updates before releasing native resources.
        if (previous == null) return;
        previous.Cancellation.Cancel();
        try { previous.Capture.StopRecording(); }
        finally
        {
            try { previous.Capture.Dispose(); }
            finally { previous.Device.Dispose(); previous.Cancellation.Dispose(); }
        }
    }
    public void Dispose() => Stop();
}
