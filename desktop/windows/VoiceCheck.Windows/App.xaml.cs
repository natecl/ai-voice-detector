using System;
using System.IO;
using System.Linq;
using System.Windows.Threading;
using System.Threading;
using System.Windows;

namespace VoiceCheck.Windows;

public partial class App : Application
{
    private Mutex? instance;
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        instance = new Mutex(true, @"Local\VoiceCheck.Windows", out var first);
        if (!first) { MessageBox.Show("Voice Check is already running. Look for its waveform tray icon.", "Voice Check"); Shutdown(); return; }
        try
        {
            string? root = null;
            for (var i = 0; i + 1 < e.Args.Length; i++) if (e.Args[i] == "--project") root = Path.GetFullPath(e.Args[i + 1]);
            root ??= FindRoot(AppContext.BaseDirectory) ?? FindRoot(Environment.CurrentDirectory);
            if (root == null || !File.Exists(Path.Combine(root, "app.py")))
                throw new InvalidOperationException("Start with scripts/start_windows.ps1, or pass --project followed by the repository path.");
            MainWindow = new MainWindow(root);
            if (e.Args.Contains("--smoke-test"))
            {
                ShutdownMode = ShutdownMode.OnExplicitShutdown;
                MainWindow.Loaded += (_, _) => Dispatcher.BeginInvoke(new Action(() =>
                {
                    // Prove WPF, native window creation, tray setup, and XAML loading work on Windows.
                    var valid = MainWindow.IsVisible && MainWindow.ActualWidth == 188 &&
                        MainWindow.FindName("PillTarget") != null && MainWindow.FindName("BadgeText") != null;
                    MainWindow.Close();
                    Shutdown(valid ? 0 : 2);
                }), DispatcherPriority.ApplicationIdle);
            }
            MainWindow.Show();
        }
        catch (Exception exception) { if (!e.Args.Contains("--smoke-test")) MessageBox.Show(exception.Message, "Voice Check could not start"); Shutdown(1); }
    }
    private static string? FindRoot(string path)
    {
        for (var directory = new DirectoryInfo(path); directory != null; directory = directory.Parent)
            if (File.Exists(Path.Combine(directory.FullName, "app.py")) && Directory.Exists(Path.Combine(directory.FullName, "ui"))) return directory.FullName;
        return null;
    }
    protected override void OnExit(ExitEventArgs e) { instance?.Dispose(); base.OnExit(e); }
}
