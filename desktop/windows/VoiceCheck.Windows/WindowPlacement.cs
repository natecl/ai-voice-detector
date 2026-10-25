using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using Forms = System.Windows.Forms;

namespace VoiceCheck.Windows;

// Keep monitor coordinates in physical pixels. WPF's DIPs vary by monitor DPI.
internal static class WindowPlacement
{
    [StructLayout(LayoutKind.Sequential)] private struct Rect { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] private struct NativePoint { public int X, Y; }
    [DllImport("user32.dll")] private static extern bool GetWindowRect(IntPtr window, out Rect rect);
    [DllImport("user32.dll")] private static extern bool GetCursorPos(out NativePoint point);
    [DllImport("user32.dll")] private static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int cx, int cy, uint flags);
    private static IntPtr Handle(Window window) => new WindowInteropHelper(window).Handle;
    public static Point Origin(Window window) { GetWindowRect(Handle(window), out var rect); return new(rect.Left, rect.Top); }
    public static Point Cursor() { GetCursorPos(out var point); return new(point.X, point.Y); }
    public static void Move(Window window, double x, double y)
    {
        if (!double.IsFinite(x) || !double.IsFinite(y)) return;
        SetWindowPos(Handle(window), IntPtr.Zero, (int)Math.Clamp(x, int.MinValue, int.MaxValue),
            (int)Math.Clamp(y, int.MinValue, int.MaxValue), 0, 0, 0x0001 | 0x0004 | 0x0010); // NOSIZE | NOZORDER | NOACTIVATE
    }
    public static void KeepVisible(Window window)
    {
        var handle = Handle(window);
        GetWindowRect(handle, out var rect);
        var area = Forms.Screen.FromHandle(handle).WorkingArea;
        Move(window, Math.Clamp(rect.Left, area.Left, Math.Max(area.Left, area.Right - (rect.Right - rect.Left))),
            Math.Clamp(rect.Top, area.Top, Math.Max(area.Top, area.Bottom - (rect.Bottom - rect.Top))));
    }
}
