# Claude Code working instructions: dshot

- Current repository/project/executable name is **dshot** (all lowercase, exactly; formerly danidshot).
- Windows app: `src/dshot/dshot.csproj` (C#/WPF). Linux app: `linux/dshot` (Python 3 + PySide6, Tesseract OCR, xdg-desktop-portal on Wayland), installed with `linux/install.sh`. Keep both at feature parity.
- Linux tests: `cd linux && QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests` (needs tesseract-ocr-eng/spa).
- Windows local build: `build_windows.bat`; output must be `release/dshot.exe`.
- GitHub Actions: `.github/workflows/windows-exe.yml` ("Build dshot"), artifacts `dshot-Windows-x64` and `dshot-Linux`; a release_tag input publishes a release with `dshot.exe` and `dshot-linux.tar.gz`.
- Feature scope: region screenshots, clipboard image, PNG save, annotations (text/rectangles/arrows/pen/undo/color), English/Spanish offline OCR and auto clipboard copy, tray, startup. No other ShareX/PowerToys features.
- Do **not** add cloud access, recording, integrations, OCR history, accounts or subscriptions.
- The code builds on GitHub's Windows runners but interactive behavior is not yet validated on Windows. Run meaningful tests and report real results, particularly on a Windows host.
- Runtime: targets net8.0-windows with RollForward=LatestMajor and is published framework-dependent (~25 MB single exe); keep it that way unless asked.
- Commits are authored by the repository owner only: do not add Co-Authored-By or other Claude attribution lines.
- The Windows app captures the primary screen only; do not claim multi-monitor support there unless you implement and test it. The Linux app shows one overlay per screen; a selection stays within one screen.
- Use public Windows APIs; ShareX can guide UI behavior but avoid copying GPL-covered ShareX code. Only adapt MIT PowerToys code if notices and compatibility are respected. REA is unnecessary.
