using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using Microsoft.Win32;
using Forms = System.Windows.Forms;

namespace dshot;

internal sealed class DshotApp : System.Windows.Application
{
    private const int HotkeyId = 0x5A18;
    private const int PrintScreenHotkeyId = 0x5A19;
    private const int WmHotkey = 0x0312;
    private const uint ModAlt = 0x0001;
    private const uint ModControl = 0x0002;
    private const uint ModNoRepeat = 0x4000;
    private const uint KeyS = 0x53;
    private const uint KeyPrintScreen = 0x2C; // VK_SNAPSHOT
    private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string RunEntry = "dshot";
    private const string CaptureRequestEvent = "Local\\dshotCaptureRequest";

    private readonly System.Threading.Mutex _mutex;
    private readonly bool _firstInstance;
    private readonly EventWaitHandle _captureRequest;
    private RegisteredWaitHandle? _captureRequestWait;
    private HwndSource? _hotkeyWindow;
    private Forms.NotifyIcon? _tray;
    private OverlayWindow? _overlay;
    private bool _hotkeyRegistered;
    private bool _printScreenRegistered;

    private DshotApp(System.Threading.Mutex mutex, bool firstInstance, EventWaitHandle captureRequest)
    {
        _mutex = mutex;
        _firstInstance = firstInstance;
        _captureRequest = captureRequest;
        ShutdownMode = ShutdownMode.OnExplicitShutdown;
    }

    [STAThread]
    public static void Main()
    {
        var mutex = new System.Threading.Mutex(true, "Local\\dshotSingleInstance", out bool first);
        if (!first)
        {
            // Like Lightshot: opening dshot again while it runs starts a capture in the running instance.
            if (EventWaitHandle.TryOpenExisting(CaptureRequestEvent, out var request))
            {
                using (request) request.Set();
            }
            else
            {
                MessageBox.Show("dshot ya está abierto en la bandeja del sistema.", "dshot", MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
            mutex.Dispose();
            return;
        }

        using var captureRequest = new EventWaitHandle(false, EventResetMode.AutoReset, CaptureRequestEvent);
        try { new DshotApp(mutex, first, captureRequest).Run(); }
        finally { mutex.ReleaseMutex(); mutex.Dispose(); }
    }

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        // Message-only Win32 window to receive a system-wide shortcut while no WPF window is visible.
        var parameters = new HwndSourceParameters("dshotShortcut")
        {
            ParentWindow = new IntPtr(-3), // HWND_MESSAGE
            Width = 1,
            Height = 1
        };
        _hotkeyWindow = new HwndSource(parameters);
        _hotkeyWindow.AddHook(HotkeyHook);
        _hotkeyRegistered = RegisterHotKey(_hotkeyWindow.Handle, HotkeyId, ModAlt | ModControl | ModNoRepeat, KeyS);
        // Plain Print Screen, like Lightshot. Fails when Windows (Snipping Tool) or another app already owns the key.
        _printScreenRegistered = RegisterHotKey(_hotkeyWindow.Handle, PrintScreenHotkeyId, ModNoRepeat, KeyPrintScreen);

        var menu = new Forms.ContextMenuStrip();
        menu.Items.Add("Capturar (Impr Pant / Ctrl + Alt + S)", null, (_, _) => Dispatcher.BeginInvoke(Capture));
        var startupItem = new Forms.ToolStripMenuItem("Iniciar con Windows") { Checked = IsStartupEnabled(), CheckOnClick = true };
        startupItem.Click += (_, _) =>
        {
            try { SetStartupEnabled(startupItem.Checked); }
            catch (Exception ex)
            {
                startupItem.Checked = !startupItem.Checked;
                MessageBox.Show(ex.Message, "Inicio automático", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        };
        menu.Items.Add(startupItem);
        menu.Items.Add(new Forms.ToolStripSeparator());
        menu.Items.Add("Salir", null, (_, _) => Dispatcher.BeginInvoke(() => Shutdown()));

        _tray = new Forms.NotifyIcon
        {
            Icon = SystemIcons.Application,
            Text = "dshot — clic para capturar",
            ContextMenuStrip = menu,
            Visible = true
        };
        // Left click on the tray icon captures (as in Lightshot); right click keeps the menu.
        _tray.MouseClick += (_, e) =>
        {
            if (e.Button == Forms.MouseButtons.Left) Dispatcher.BeginInvoke(Capture);
        };
        _captureRequestWait = ThreadPool.RegisterWaitForSingleObject(_captureRequest,
            (_, _) => Dispatcher.BeginInvoke(Capture), null, Timeout.Infinite, executeOnlyOnce: false);
        if (!_hotkeyRegistered && !_printScreenRegistered)
        {
            MessageBox.Show("Impr Pant y Ctrl + Alt + S están ocupados por otras aplicaciones. Usa el icono de dshot en la bandeja para capturar.",
                "Atajo no disponible", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
        else if (!_printScreenRegistered)
        {
            // A balloon instead of a dialog: this can repeat on every sign-in until the Windows setting is changed.
            _tray.ShowBalloonTip(10000, "Impr Pant no disponible",
                "Windows u otra app usa Impr Pant. Desactiva \"Usar la tecla Imprimir pantalla para abrir la herramienta Recortes\" " +
                "en Configuración > Accesibilidad > Teclado y reinicia dshot. Mientras tanto usa Ctrl + Alt + S.",
                Forms.ToolTipIcon.Warning);
        }
    }

    private void Capture()
    {
        if (_overlay is not null) return;
        try
        {
            _overlay = new OverlayWindow();
            _overlay.Closed += (_, _) => _overlay = null;
            _overlay.Show();
            _overlay.Activate();
        }
        catch (Exception ex)
        {
            _overlay = null;
            MessageBox.Show($"No se pudo capturar: {ex.Message}", "dshot", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private IntPtr HotkeyHook(IntPtr hwnd, int message, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (message == WmHotkey && wParam.ToInt32() is HotkeyId or PrintScreenHotkeyId)
        {
            handled = true;
            Dispatcher.BeginInvoke(Capture);
        }
        return IntPtr.Zero;
    }

    private static bool IsStartupEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKeyPath);
        return key?.GetValue(RunEntry) is string;
    }

    private static void SetStartupEnabled(bool enabled)
    {
        using var key = Registry.CurrentUser.CreateSubKey(RunKeyPath);
        if (enabled) key.SetValue(RunEntry, $"\"{Environment.ProcessPath}\"");
        else key.DeleteValue(RunEntry, false);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _captureRequestWait?.Unregister(null);
        if (_hotkeyRegistered && _hotkeyWindow is not null) UnregisterHotKey(_hotkeyWindow.Handle, HotkeyId);
        if (_printScreenRegistered && _hotkeyWindow is not null) UnregisterHotKey(_hotkeyWindow.Handle, PrintScreenHotkeyId);
        _hotkeyWindow?.Dispose();
        if (_tray is not null) { _tray.Visible = false; _tray.Dispose(); }
        base.OnExit(e);
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hwnd, int id, uint modifiers, uint virtualKey);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr hwnd, int id);
}
