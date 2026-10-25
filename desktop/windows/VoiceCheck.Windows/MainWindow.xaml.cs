using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Shapes;
using System.Windows.Threading;
using Microsoft.Win32;
using NAudio.CoreAudioApi;
using VoiceCheck.Core;
using Forms = System.Windows.Forms;

namespace VoiceCheck.Windows;

public partial class MainWindow : Window
{
    private readonly HttpClient http = DetectorClient.CreateLocalClient();
    private readonly BackendHost backend;
    private readonly LoopbackSession capture;
    private readonly CancellationTokenSource lifetime = new();
    private readonly DispatcherTimer meterTimer = new() { Interval = TimeSpan.FromMilliseconds(100) };
    private readonly Forms.NotifyIcon tray;
    private readonly Rectangle[] bars;
    private readonly double[] history = new double[7];
    private readonly string preferences = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "VoiceCheck", "position.json");
    private string? deviceId;
    private CancellationTokenSource? startRequest;
    private Point pointerStart, windowStart;
    private bool dragging, pointerHeld, closed;
    private string? lastMessage;
    private readonly DispatcherTimer displayTimer = new() { Interval = TimeSpan.FromMilliseconds(200) };

    public MainWindow(string root)
    {
        InitializeComponent();
        var detector = new DetectorClient(http);
        backend = new(root, detector);
        capture = new(detector, Dispatcher);
        capture.Levels += values => { foreach (var value in values) { Array.Copy(history, 1, history, 0, 6); history[6] = value; } PaintBars(); };
        capture.Changed += CaptureChanged;
        bars = Enumerable.Range(0, 7).Select(_ => new Rectangle
        {
            Width = 2, Height = 2, RadiusX = .5, RadiusY = .5, Margin = new Thickness(1, 0, 1, 0),
            Fill = new SolidColorBrush(Color.FromRgb(222, 221, 215)), VerticalAlignment = VerticalAlignment.Center
        }).ToArray();
        foreach (var bar in bars) Bars.Children.Add(bar);
        tray = new Forms.NotifyIcon { Icon = System.Drawing.SystemIcons.Information, Text = "Voice Check · idle", Visible = true };
        tray.MouseDoubleClick += (_, _) => Show();
        tray.ContextMenuStrip = new Forms.ContextMenuStrip();
        tray.ContextMenuStrip.Opening += (_, _) => RefreshTray();
        Loaded += (_, _) => RestorePosition();
        meterTimer.Tick += (_, _) =>
        {
            if (!capture.Running) return;
            var silentFor = Environment.TickCount64 - capture.LastDataAt;
            if (silentFor > 250) { Array.Clear(history); PaintBars(); }
            if (silentFor > 1000 && BadgeText.Text != "Try again") SetBadge("Waiting");
        };
        meterTimer.Start();
        // Display topology notifications arrive outside the WPF dispatcher.
        SystemEvents.DisplaySettingsChanged += DisplaySettingsChanged;
        displayTimer.Tick += (_, _) => { displayTimer.Stop(); KeepVisible(); };
        Closed += (_, _) => Cleanup();
        UpdatePill();
    }

    private bool Active => capture.Running || startRequest != null;
    private void CaptureChanged(string state, string? message, Verdict? verdict)
    {
        if (closed) return;
        if (message != null) { lastMessage = message; PillTarget.ToolTip = message; }
        if (state == "listening") SetBadge("Listening");
        else if (state == "analyzing" && BadgeText.Text is not ("Human" or "AI")) SetBadge("Checking…");
        else if (state == "result" && verdict != null)
        {
            SetBadge(verdict.Label);
            PillTarget.ToolTip = verdict.Score.HasValue
                ? $"{verdict.Label} · synthetic score {verdict.Score:0.000} (not confidence) · {capture.DeviceName}"
                : "Waiting for clear speech · " + capture.DeviceName;
        }
        else if (state is "error" or "warning") SetBadge(state == "error" ? "Error" : "Try again");
        UpdatePill();
    }
    private async Task Toggle()
    {
        if (Active) { Stop(); return; }
        using var request = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
        startRequest = request;
        SetBadge("Starting…"); UpdatePill();
        PillTarget.ToolTip = "Starting local detector. First use may download model weights. Click to cancel.";
        try
        {
            await backend.EnsureReady(request.Token);
            request.Token.ThrowIfCancellationRequested();
            capture.Start(deviceId);
        }
        catch (OperationCanceledException) when (request.IsCancellationRequested) { }
        catch (Exception exception)
        {
            if (closed) return;
            lastMessage = exception.Message; PillTarget.ToolTip = lastMessage;
            SetBadge("Error");
            tray.ShowBalloonTip(5000, "Voice Check", lastMessage, Forms.ToolTipIcon.Error);
        }
        finally
        {
            if (ReferenceEquals(startRequest, request)) startRequest = null;
            if (!closed) UpdatePill();
        }
    }
    private void Stop()
    {
        startRequest?.Cancel(); startRequest = null;
        capture.Stop(); Array.Clear(history); PaintBars();
        SetBadge(""); lastMessage = null; PillTarget.ToolTip = "Listen to system audio · drag to move";
        UpdatePill();
    }
    private void SetBadge(string text)
    {
        BadgeText.Text = text;
        Badge.Visibility = text.Length == 0 ? Visibility.Collapsed : Visibility.Visible;
        BadgeText.Foreground = new SolidColorBrush(text == "Human" ? Color.FromRgb(185, 222, 160) :
            text == "AI" ? Color.FromRgb(239, 181, 141) : Color.FromRgb(201, 200, 195));
        tray.Text = "Voice Check · " + (text.Length == 0 ? "idle" : text);
    }
    private void UpdatePill()
    {
        var active = Active;
        var hover = PillTarget.IsMouseOver || PillTarget.IsKeyboardFocusWithin;
        var width = active ? 102.5 : hover ? 50 : 40;
        var height = active || hover ? 30 : 8;
        if (SystemParameters.ClientAreaAnimation)
        {
            Pill.BeginAnimation(WidthProperty, new DoubleAnimation(width, TimeSpan.FromMilliseconds(100)));
            Pill.BeginAnimation(HeightProperty, new DoubleAnimation(height, TimeSpan.FromMilliseconds(100)));
        }
        else { Pill.BeginAnimation(WidthProperty, null); Pill.BeginAnimation(HeightProperty, null); Pill.Width = width; Pill.Height = height; }
        Pill.Background = new SolidColorBrush(active ? Color.FromRgb(16, 16, 16) : hover ? Color.FromRgb(36, 36, 36) : Color.FromArgb(128, 0, 0, 0));
        Mark.Visibility = active || hover ? Visibility.Visible : Visibility.Collapsed;
        LeftAction.Visibility = LeftGlyph.Visibility = RightAction.Visibility = RightGlyph.Visibility = active ? Visibility.Visible : Visibility.Hidden;
        Mark.Opacity = startRequest != null ? .4 : 1;
    }
    private void PaintBars()
    {
        for (var i = 0; i < bars.Length; i++) bars[i].Height = 2 + 14 * history[i];
    }
    private void OnHover(object sender, MouseEventArgs e) => UpdatePill();
    private void OnPointerDown(object sender, MouseButtonEventArgs e)
    {
        pointerHeld = true; dragging = false; PillTarget.Focus();
        pointerStart = WindowPlacement.Cursor(); windowStart = WindowPlacement.Origin(this);
        PillTarget.CaptureMouse(); e.Handled = true;
    }
    private void OnPointerMove(object sender, MouseEventArgs e)
    {
        if (!pointerHeld) return;
        var pointer = WindowPlacement.Cursor();
        // WPF positions are DIPs; screen coordinates and monitor bounds are physical pixels.
        var dpi = VisualTreeHelper.GetDpi(this);
        var dx = (pointer.X - pointerStart.X) / dpi.DpiScaleX;
        var dy = (pointer.Y - pointerStart.Y) / dpi.DpiScaleY;
        if (!dragging && Math.Sqrt(dx * dx + dy * dy) >= 4) dragging = true;
        if (dragging) { WindowPlacement.Move(this, windowStart.X + pointer.X - pointerStart.X, windowStart.Y + pointer.Y - pointerStart.Y); PillTarget.Cursor = Cursors.SizeAll; }
    }
    private void OnLostCapture(object sender, MouseEventArgs e)
    {
        if (!pointerHeld) return;
        pointerHeld = false; PillTarget.Cursor = Cursors.Hand;
        if (dragging) { KeepVisible(); SavePosition(); }
    }
    private async void OnPointerUp(object sender, MouseButtonEventArgs e)
    {
        if (!pointerHeld) return;
        pointerHeld = false; PillTarget.ReleaseMouseCapture(); PillTarget.Cursor = Cursors.Hand;
        if (dragging) { KeepVisible(); SavePosition(); }
        else await Toggle();
        e.Handled = true;
    }
    private async void OnKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape) { Stop(); e.Handled = true; }
        else if (e.Key is Key.Space or Key.Enter) { await Toggle(); e.Handled = true; }
    }
    private void RefreshTray()
    {
        var menu = tray.ContextMenuStrip!; foreach (var item in menu.Items.Cast<Forms.ToolStripItem>().ToArray()) item.Dispose(); menu.Items.Clear();
        menu.Items.Add("Show Voice Check", null, (_, _) => Show());
        menu.Items.Add(Active ? "Stop listening" : "Start listening", null, async (_, _) => await Toggle());
        menu.Items.Add("Open upload / microphone app", null, async (_, _) =>
        {
            try { await backend.EnsureReady(lifetime.Token); Process.Start(new ProcessStartInfo("http://127.0.0.1:8765") { UseShellExecute = true }); }
            catch (OperationCanceledException) { }
            catch (Exception exception) { MessageBox.Show(exception.Message, "Voice Check"); }
        });
        var outputs = new Forms.ToolStripMenuItem("Output device");
        outputs.DropDownItems.Add(new Forms.ToolStripMenuItem("Windows default (multimedia)", null, (_, _) => { Stop(); deviceId = null; }) { Checked = deviceId == null });
        try
        {
            using var enumerator = new MMDeviceEnumerator();
            var devices = enumerator.EnumerateAudioEndPoints(DataFlow.Render, DeviceState.Active);
            foreach (var device in devices)
            {
                using (device)
                {
                    var id = device.ID;
                    outputs.DropDownItems.Add(new Forms.ToolStripMenuItem(device.FriendlyName, null, (_, _) => { Stop(); deviceId = id; }) { Checked = deviceId == id });
                }
            }
        }
        catch (Exception exception) { outputs.DropDownItems.Add("Devices unavailable: " + exception.Message); }
        menu.Items.Add(outputs);
        if (lastMessage != null) menu.Items.Add("Show last status", null, (_, _) => MessageBox.Show(lastMessage, "Voice Check"));
        menu.Items.Add("Reset position", null, (_, _) => { DefaultPosition(); SavePosition(); });
        menu.Items.Add("Hide and stop", null, (_, _) => { Stop(); Hide(); });
        menu.Items.Add("Quit Voice Check", null, (_, _) => Close());
    }
    private record Position(double X, double Y);
    private void RestorePosition()
    {
        DefaultPosition();
        try
        {
            var saved = JsonSerializer.Deserialize<Position>(File.ReadAllText(preferences));
            if (saved != null && double.IsFinite(saved.X) && double.IsFinite(saved.Y)) WindowPlacement.Move(this, saved.X, saved.Y);
        }
        catch (Exception exception) when (exception is IOException or JsonException or UnauthorizedAccessException) { }
        KeepVisible();
    }
    private void DefaultPosition()
    {
        var area = SystemParameters.WorkArea;
        Left = area.Left + (area.Width - Width) / 2; Top = area.Bottom - Height - 5;
    }
    private void KeepVisible() => WindowPlacement.KeepVisible(this);
    private void SavePosition()
    {
        try { Directory.CreateDirectory(System.IO.Path.GetDirectoryName(preferences)!); File.WriteAllText(preferences, JsonSerializer.Serialize(new Position(WindowPlacement.Origin(this).X, WindowPlacement.Origin(this).Y))); }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException) { PillTarget.ToolTip = "Position could not be saved: " + exception.Message; }
    }
    private void DisplaySettingsChanged(object? sender, EventArgs e) { if (!closed) Dispatcher.BeginInvoke(() => { if (!closed) displayTimer.Start(); }); }
    private void Cleanup()
    {
        closed = true; lifetime.Cancel(); startRequest?.Cancel();
        meterTimer.Stop(); displayTimer.Stop();
        SystemEvents.DisplaySettingsChanged -= DisplaySettingsChanged;
        capture.Dispose(); backend.Dispose(); http.Dispose(); tray.Dispose(); lifetime.Dispose();
    }
}
