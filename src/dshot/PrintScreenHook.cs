using System;
using System.Runtime.InteropServices;
using System.Threading;

namespace dshot;

/// <summary>
/// Catches the plain Print Screen key with a low-level keyboard hook and swallows it, so Windows'
/// "Print screen opens screen capture" (Snipping Tool) never sees it. Print Screen with Alt, Ctrl,
/// Shift or Win is passed through untouched.
/// </summary>
/// <remarks>
/// The hook runs on its own thread with its own message loop: Windows waits for low-level hooks on
/// every key press system-wide, so the callback must never wait behind the UI thread.
/// </remarks>
internal sealed class PrintScreenHook : IDisposable
{
    private const int WhKeyboardLl = 13;
    private const int WmKeyDown = 0x0100;
    private const int WmSysKeyDown = 0x0104;
    private const uint WmQuit = 0x0012;
    private const uint VkSnapshot = 0x2C;
    private static readonly int[] Modifiers = { 0x10, 0x11, 0x12, 0x5B, 0x5C }; // Shift, Ctrl, Alt, LWin, RWin

    private readonly Action _onPressed;
    private readonly LowLevelKeyboardProc _proc; // Kept in a field so the GC never frees the native callback.
    private IntPtr _hook;
    private uint _threadId;

    private PrintScreenHook(Action onPressed)
    {
        _onPressed = onPressed;
        _proc = Callback;
    }

    /// <summary>Installs the hook, or returns null if Windows refuses it.</summary>
    public static PrintScreenHook? TryStart(Action onPressed)
    {
        var hook = new PrintScreenHook(onPressed);
        // Not disposed: if the wait below timed out, the hook thread would still call Set() on it.
        var ready = new ManualResetEventSlim();
        var thread = new Thread(() =>
        {
            hook._threadId = GetCurrentThreadId();
            hook._hook = SetWindowsHookEx(WhKeyboardLl, hook._proc, GetModuleHandle(null), 0);
            ready.Set();
            if (hook._hook == IntPtr.Zero) return;
            while (GetMessage(out _, IntPtr.Zero, 0, 0) > 0) { }
            UnhookWindowsHookEx(hook._hook);
        })
        { IsBackground = true, Name = "dshot Print Screen hook" };
        thread.Start();
        ready.Wait(TimeSpan.FromSeconds(5));
        return hook._hook != IntPtr.Zero ? hook : null;
    }

    private IntPtr Callback(int code, IntPtr wParam, IntPtr lParam)
    {
        if (code >= 0 && Marshal.ReadInt32(lParam) == VkSnapshot && !AnyModifierDown())
        {
            int message = wParam.ToInt32();
            if (message is WmKeyDown or WmSysKeyDown) _onPressed();
            return (IntPtr)1; // Swallow both press and release.
        }
        return CallNextHookEx(_hook, code, wParam, lParam);
    }

    private static bool AnyModifierDown()
    {
        foreach (int key in Modifiers)
            if ((GetAsyncKeyState(key) & 0x8000) != 0) return true;
        return false;
    }

    public void Dispose()
    {
        if (_threadId != 0) PostThreadMessage(_threadId, WmQuit, IntPtr.Zero, IntPtr.Zero);
        _threadId = 0;
    }

    private delegate IntPtr LowLevelKeyboardProc(int code, IntPtr wParam, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct Msg
    {
        public IntPtr Hwnd;
        public uint Message;
        public IntPtr WParam;
        public IntPtr LParam;
        public uint Time;
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetWindowsHookEx(int idHook, LowLevelKeyboardProc callback, IntPtr module, uint threadId);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")]
    private static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")]
    private static extern int GetMessage(out Msg message, IntPtr hwnd, uint filterMin, uint filterMax);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool PostThreadMessage(uint threadId, uint message, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int key);
    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr GetModuleHandle(string? moduleName);
}
