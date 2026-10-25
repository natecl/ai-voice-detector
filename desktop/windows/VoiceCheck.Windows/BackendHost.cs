using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using VoiceCheck.Core;

namespace VoiceCheck.Windows;

public sealed class BackendHost(string root, DetectorClient detector) : IDisposable
{
    private Process? owned;
    private readonly SemaphoreSlim startup = new(1, 1);
    private readonly object logLock = new();
    public async Task EnsureReady(CancellationToken cancellationToken)
    {
        await startup.WaitAsync(cancellationToken);
        try { await EnsureReadyExclusive(cancellationToken); }
        finally { startup.Release(); }
    }
    private async Task EnsureReadyExclusive(CancellationToken cancellationToken)
    {
        var ready = await detector.Ready(cancellationToken);
        if (ready == true) return;
        // A reachable but still-warming detector is reused rather than replaced.
        if (ready == null && (owned == null || owned.HasExited))
        {
            var python = Path.Combine(root, ".venv", "Scripts", "python.exe");
            if (!File.Exists(python)) throw new InvalidOperationException("Python environment is missing. Run scripts/setup_windows.ps1 first.");
            var start = new ProcessStartInfo(python)
            {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            start.ArgumentList.Add(Path.Combine(root, "app.py"));
            owned?.Dispose();
            owned = new Process { StartInfo = start };
            Directory.CreateDirectory(Path.Combine(root, "work"));
            owned.OutputDataReceived += Log; owned.ErrorDataReceived += Log;
            owned.Start(); owned.BeginOutputReadLine(); owned.BeginErrorReadLine();
        }
        var deadline = DateTime.UtcNow.AddMinutes(5);
        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (owned?.HasExited == true)
                throw new InvalidOperationException("The detector exited. Check work/windows-widget-server.log, or run .venv\\Scripts\\python.exe app.py for the error.");
            if (await detector.Ready(cancellationToken) == true) return;
            await Task.Delay(1000, cancellationToken);
        }
        throw new TimeoutException("Detector startup timed out. Check work/windows-widget-server.log. The first run downloads model weights.");
    }
    private void Log(object sender, DataReceivedEventArgs e)
    {
        if (e.Data == null) return;
        try { lock (logLock) File.AppendAllText(Path.Combine(root, "work", "windows-widget-server.log"), e.Data + Environment.NewLine); }
        catch (IOException) { /* Logging must not terminate a capture or startup callback. */ }
    }
    public void Dispose()
    {
        if (owned != null)
        {
            try { if (!owned.HasExited) owned.Kill(entireProcessTree:true); } catch (InvalidOperationException) { }
            owned.Dispose(); owned = null;
        }
    }
}
