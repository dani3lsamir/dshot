<p align="center"><img src="assets/dshot-logo.png" width="128" alt="dshot logo"></p>

# dshot — minimalist screenshot and OCR for Windows

Source project for the standalone **`dshot.exe`** Windows utility.

## Download

Get `dshot.exe` from the [Releases](../../releases) page. It is a single portable file (no installer) for Windows 10/11 x64 and needs the **Microsoft Windows Desktop Runtime 8 or newer (x64)**.

## Strict feature scope
- Region screenshot via **Print Screen** (or **Ctrl+Alt+S**) and an unobtrusive floating toolbar.
- **Annotate** selected screenshot: text typed directly on the image (Lightshot style), rectangles, arrows, freehand pen, undo, color change.
- **Copy** annotated image to clipboard or **save** as PNG.
- **OCR (text extraction)**: select region -> click **OCR** -> copy recognized English or Spanish text to clipboard automatically.
- Tray icon; optional launch with Windows. Entirely local, no login, uploads, telemetry or paid APIs.

Explicitly excluded: other ShareX/PowerToys features, recording, GIFs, scrolling screenshots, image upload, cloud links, translation, summarization, and history.

## Build on Windows 10/11 x64

1. Install .NET 10 SDK: https://dotnet.microsoft.com/download/dotnet/10.0
2. Open PowerShell in this directory.
3. Run `cmd /c build_windows.bat`.
4. After a successful build, launch `release\dshot.exe`. If other files are present in release, keep them.

**Runtime requirement:** `dshot.exe` (~25 MB) does not bundle .NET. It needs the **Microsoft Windows Desktop Runtime 8 or newer (x64)** and automatically uses the newest one installed (8, 9, 10…). If none is installed, Windows shows a download link on first start. .NET 8 and 9 reach end of support in November 2026, so installing the .NET 10 Desktop Runtime is recommended; no rebuild is needed.

Alternative command:

```powershell
dotnet publish .\src\dshot\dshot.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:DebugType=none -o .\release
```

## Build on GitHub (Windows runner)

1. Go to **Actions -> Build dshot.exe -> Run workflow**.
2. Leave **release_tag** empty to only build: download the artifact **dshot-Windows-x64** containing `dshot.exe`.
3. Or enter a tag such as `v0.4.0` to publish `dshot.exe` as a prerelease on the Releases page. Pushing a `v*` tag does the same.

GitHub Actions can compile the executable, but cannot prove physical shortcut/clipboard/OCR behavior on your desktop. Test those locally on Windows.

## First use

1. Start `dshot.exe` (portable, no installer; needs the Windows Desktop Runtime 8+); it stays in your notification area/system tray.
2. Press **Print Screen** (or **Ctrl+Alt+S**), **left-click the tray icon**, or open `dshot.exe` again while it is running — all start a capture, as in Lightshot.
3. Drag a selection on your **primary monitor**.
4. Floating bar: **Copiar** / **OCR** / **▭** rectangle / **➜** arrow / **✎** pen / **T** text / color / undo / **Guardar** / cancel.
5. **OCR** copies the extracted plain text to the clipboard; paste via Ctrl+V.

Keyboard shortcuts in the capture (as in Lightshot):

| Key | Action |
| --- | --- |
| **Ctrl+C** | Copy the selected region (with annotations) to the clipboard |
| **Ctrl+S** | Save as PNG |
| **Ctrl+Z** | Undo the last annotation |
| **Esc** | Finish the text being typed; press again to cancel the capture |

With the **T** tool, click on the image and type: the text appears directly over the screenshot in the current color. **Enter** starts a new line; click elsewhere (or press Esc) to finish it.

**Print Screen on Windows 11/10:** Windows can reserve the key for Snipping Tool. If dshot shows a "Impr Pant no disponible" notice, turn off *Settings > Accessibility > Keyboard > Use the Print screen key to open Snipping Tool* (Windows 10: *Ease of Access > Keyboard*) and restart dshot. Ctrl+Alt+S keeps working meanwhile.

For Windows OCR in Spanish and English, install matching Windows OCR language capabilities via system language settings. Automatic language selection is heuristic, and may not recognize mixed-language text perfectly.

## Known limitations and validation status

The build is verified on GitHub's Windows runners; interactive behavior (shortcuts, clipboard, OCR) still needs manual testing on Windows. Region selection is limited to the **primary monitor**, not arbitrary multi-monitor layouts. Windows native OCR may fail on protected screen areas or when language capabilities are missing.

## Licenses

The project implements its own functions using Windows APIs. It does not include ShareX or PowerToys code. ShareX is GPL-3.0; avoid copying its source without following the license. PowerToys is MIT; follow notices if any actual MIT-covered code is incorporated later.
