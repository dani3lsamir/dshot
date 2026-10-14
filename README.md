<p align="center"><img src="assets/dshot-logo.png" width="128" alt="dshot logo"></p>

# dshot

Minimal screenshot, annotation and OCR tool for Windows 10/11 and Linux, in the spirit of Lightshot. Everything runs locally: no account, no uploads, no telemetry.

## Download

From the [latest release](../../releases/latest):

- **Windows:** `dshot.exe`, a single portable file (~26 MB, no installer).
- **Linux:** `dshot-linux.tar.gz`, see [Linux](#linux) below.

**Windows requirements:** Windows 10/11 x64 and the [Microsoft Windows Desktop Runtime](https://dotnet.microsoft.com/download/dotnet) 8 or newer (x64). dshot uses the newest one installed. If none is installed, Windows shows a download link on first start. .NET 8 and 9 reach end of support in November 2026, so the .NET 10 Desktop Runtime is recommended.

The exe is not code-signed, so SmartScreen may warn on first launch: choose **More info > Run anyway**.

## Features

- Region capture with **Print Screen**, **Ctrl+Alt+S**, a **left click on the tray icon**, or by opening `dshot.exe` again while it runs.
- Lightshot-style selection: everything outside the region is dimmed.
- Icon-only toolbar: rectangle, arrow, pen, text, color, undo, OCR, copy, save, close.
- Text typed directly over the screenshot in the current color.
- Copy the annotated image to the clipboard or save it as PNG.
- Offline OCR (English and Spanish) with Windows' built-in engine; the text goes straight to the clipboard.
- Tray icon that adapts to light and dark taskbars, optional start with Windows, single instance.

Out of scope by design: recording, GIFs, scrolling capture, uploads or share links, translation, history and other ShareX/PowerToys features.

## Usage

1. Start `dshot.exe`. It stays in the system tray.
2. Start a capture (see above) and drag over the area you want, on the **primary monitor**.
3. Annotate with the toolbar (hover an icon for its name), then copy, save or OCR.

| Key | Action |
| --- | --- |
| **Ctrl+C** | Copy the region (with annotations) |
| **Ctrl+S** | Save as PNG |
| **Ctrl+Z** | Undo the last annotation |
| **Esc** | Finish the text being typed; press again to close |

With the **text** tool, click on the image and type. **Enter** adds a line; click elsewhere or press **Esc** to finish.

### Start with Windows

Keep `dshot.exe` in a fixed folder (for example `%LOCALAPPDATA%\dshot`), then right-click the tray icon and check **Start with Windows**. If you move the exe later, uncheck and check it again.

## Linux

Works on CachyOS/Arch and Linux Mint/Ubuntu (other distributions with Python 3, PySide6 and Tesseract should work too), on X11 and Wayland (KDE Plasma, Cinnamon, GNOME).

```sh
tar xzf dshot-linux.tar.gz
cd dshot-linux
./install.sh
```

The installer (asks for your password to install packages):

- installs Qt for Python (PySide6), jeepney and Tesseract with English and Spanish data via `pacman` or `apt`; on Mint/Ubuntu, where PySide6 is not packaged, it puts PySide6 in a private environment under `~/.local/share/dshot`;
- installs dshot for your user only: `~/.local/bin/dshot`, an app-menu entry and the icon;
- optionally starts dshot at login and binds **Print Screen** to it. On Cinnamon (Mint) this applies immediately; on KDE Plasma (CachyOS) after you log out and back in. Elsewhere it prints the command to bind: `~/.local/bin/dshot --capture`.

Everything else works as on Windows: left-click the tray icon to capture, same toolbar and shortcuts, and running `dshot` again while it runs starts a capture. On Wayland the screen is read through the desktop's screenshot portal, which may ask for permission the first time.

Uninstall with `~/.local/share/dshot/uninstall.sh`; it also restores the desktop's own Print Screen binding.

## Troubleshooting

- **Windows, Print Screen opens another tool:** dshot catches Print Screen before Windows does (since v0.8.1), even while *Settings > Bluetooth & devices > Keyboard > Use the Print screen key to open screen capture* is on. If another tool still opens, close other screenshot apps (Lightshot, ShareX...) and restart dshot. Ctrl+Alt+S always works.
- **Windows, OCR says no language packs are installed:** add English and/or Spanish in *Settings > Time & language > Language & region*. Mixed-language text is recognized on a best-effort basis.
- **Linux, Print Screen still opens the desktop's screenshot tool:** on KDE, log out and back in after installing, or set it in *System Settings > Keyboard > Shortcuts* (add the command `~/.local/bin/dshot --capture` and remove Print from Spectacle). On Cinnamon, check *Keyboard > Shortcuts > Custom shortcuts*.
- **Linux, no tray icon:** GNOME needs the "AppIndicator and KStatusNotifierItem Support" extension. Without a tray, run `dshot` (or press the bound key) to capture.

## Build from source

### Windows

Requires the [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0) on Windows.

```powershell
cmd /c build_windows.bat
```

The result is `release\dshot.exe`. The equivalent command is:

```powershell
dotnet publish .\src\dshot\dshot.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:DebugType=none -o .\release
```

### Linux

The Linux app is plain Python in `linux/dshot` (no build step). Run it from the checkout with `cd linux && python3 -m dshot`, and the tests with:

```sh
cd linux && QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
```

### GitHub Actions

**Actions > Build dshot > Run workflow** builds the Windows exe, tests and packages the Linux app, and uploads both as artifacts. Enter a **release_tag** such as `v0.9.0` to also publish a release with both files. Pushing a `v*` tag does the same.

## Status

As of October 2026 (v0.8.0): the Windows build compiles on GitHub's Windows runners and is being tested by hand. The Linux app passes automated tests on every build (capture, copy, OCR in English and Spanish on X11, and the Wayland portal protocol), but has not yet been tried on a real KDE or Cinnamon desktop. Known limits: on Windows, capture covers the primary monitor only; on Linux every monitor is captured, but a selection stays within one monitor, and mixed per-monitor scaling on Wayland may be slightly off. Windows OCR can fail on protected content or without the language packs.

## Third-party code

dshot implements its features with public Windows APIs, and on Linux with Qt (PySide6, LGPL), jeepney (MIT) and Tesseract (Apache-2.0), which are installed separately and not bundled. It contains no ShareX (GPL-3.0) or PowerToys (MIT) code.
