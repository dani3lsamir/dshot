# Claude Code working instructions: dshot

- Current repository/project/executable name is **dshot** (all lowercase, exactly; formerly danidshot).
- Main project: `src/dshot/dshot.csproj`.
- Windows local build: `build_windows.bat`; output must be `release/dshot.exe`.
- GitHub Actions: `.github/workflows/windows-exe.yml`, artifact `dshot-Windows-x64`.
- Feature scope: region screenshots, clipboard image, PNG save, annotations (text/rectangles/arrows/pen/undo/color), English/Spanish offline OCR and auto clipboard copy, tray, startup. No other ShareX/PowerToys features.
- Do **not** add cloud access, recording, integrations, OCR history, accounts or subscriptions.
- The code builds on GitHub's Windows runners but interactive behavior is not yet validated on Windows. Run meaningful tests and report real results, particularly on a Windows host.
- Runtime: targets net8.0-windows with RollForward=LatestMajor and is published framework-dependent (~25 MB single exe); keep it that way unless asked.
- Commits are authored by the repository owner only: do not add Co-Authored-By or other Claude attribution lines.
- Current app selects the primary screen only; do not claim multi-monitor support unless you actually implement and test it.
- Use public Windows APIs; ShareX can guide UI behavior but avoid copying GPL-covered ShareX code. Only adapt MIT PowerToys code if notices and compatibility are respected. REA is unnecessary.
