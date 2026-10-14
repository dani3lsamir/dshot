#!/usr/bin/env bash
# Removes dshot for the current user and restores the Print Screen key. Distro packages
# (PySide6, Tesseract...) are left installed because other apps may use them.
set -uo pipefail

DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
PREFIX="$DATA/dshot"
LAUNCHER="$HOME/.local/bin/dshot"

"$LAUNCHER" --quit >/dev/null 2>&1 || true

if [ -f "$PREFIX/cinnamon-screenshot-binding.bak" ] && command -v gsettings >/dev/null; then
  schema=org.cinnamon.desktop.keybindings
  gsettings set $schema.media-keys screenshot "$(cat "$PREFIX/cinnamon-screenshot-binding.bak")"
  gsettings reset-recursively "$schema.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/dshot/" 2>/dev/null
  list="$(gsettings get $schema custom-list)"
  list="$(python3 -c 'import ast,sys; v=sys.argv[1].replace("@as ",""); print([x for x in ast.literal_eval(v) if x!="dshot"])' "$list")"
  gsettings set $schema custom-list "$list"
  echo "Restored Cinnamon's Print Screen binding."
fi

if [ -f "$PREFIX/kde-spectacle-binding.bak" ]; then
  kw="$(command -v kwriteconfig6 || command -v kwriteconfig5 || true)"
  if [ -n "$kw" ]; then
    "$kw" --file kglobalshortcutsrc --group services --group dshot.desktop --key Capture --delete
    previous="$(cat "$PREFIX/kde-spectacle-binding.bak")"
    if [ -n "$previous" ]; then
      "$kw" --file kglobalshortcutsrc --group services --group org.kde.spectacle.desktop --key _launch "$previous"
    else
      "$kw" --file kglobalshortcutsrc --group services --group org.kde.spectacle.desktop --key _launch --delete
    fi
    echo "Restored KDE's Print Screen shortcut (log out and back in to apply)."
  fi
fi

rm -f "$LAUNCHER" "$DATA/applications/dshot.desktop" "$DATA/icons/hicolor/256x256/apps/dshot.png" \
  "$CONFIG/autostart/dshot.desktop"
rm -rf "$PREFIX"
echo "dshot removed."
