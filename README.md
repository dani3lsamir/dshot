<p align="center"><img src="assets/dshot-logo.png" width="128" alt="dshot logo"></p>

# dshot

Minimal screenshot, annotation and OCR tool for Windows 10/11, in the spirit of Lightshot. Everything runs locally: no account, no uploads, no telemetry.

## Download

Get **`dshot.exe`** from the [latest release](../../releases/latest). It is a single portable file (~26 MB, no installer).

**Requirements:** Windows 10/11 x64 and the [Microsoft Windows Desktop Runtime](https://dotnet.microsoft.com/download/dotnet) 8 or newer (x64). dshot uses the newest one installed. If none is installed, Windows shows a download link on first start. .NET 8 and 9 reach end of support in November 2026, so the .NET 10 Desktop Runtime is recommended.

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

## Troubleshooting

- **"Print Screen unavailable" notice:** another app owns the key. Close other screenshot tools (Lightshot, ShareX...) and turn off *Settings > Accessibility > Keyboard > Use the Print screen key to open screen capture*, then restart dshot. Ctrl+Alt+S works meanwhile.
- **OCR says no language packs are installed:** add English and/or Spanish in *Settings > Time & language > Language & region*. Mixed-language text is recognized on a best-effort basis.

## Build from source

Requires the [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0) on Windows.

```powershell
cmd /c build_windows.bat
```

The result is `release\dshot.exe`. The equivalent command is:

```powershell
dotnet publish .\src\dshot\dshot.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:DebugType=none -o .\release
```

### GitHub Actions

**Actions > Build dshot.exe > Run workflow** builds on a Windows runner. Leave **release_tag** empty to get the `dshot-Windows-x64` artifact, or enter a tag such as `v0.8.0` to publish a prerelease. Pushing a `v*` tag does the same.

## Status

As of October 2026 (v0.7.0), every release builds on GitHub's Windows runners, but interactive behavior (shortcuts, clipboard, OCR) is still being tested by hand. Known limits: capture covers the primary monitor only, and Windows OCR can fail on protected content or without the language packs.

## Third-party code

dshot implements its features with public Windows APIs and contains no ShareX (GPL-3.0) or PowerToys (MIT) code.
