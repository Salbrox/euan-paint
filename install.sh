#!/usr/bin/env bash
# Adds Euan Paint to the desktop app menu for the current user.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
icons="$HOME/.local/share/icons"
apps="$HOME/.local/share/applications"
mkdir -p "$icons" "$apps"
python3 "$here/euan_paint.py" --make-icon "$icons/euan-paint.png"
cat > "$apps/euan-paint.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Euan Paint
Comment=Painting for little ones
Exec=python3 "$here/euan_paint.py"
Icon=$icons/euan-paint.png
Terminal=false
Categories=Graphics;
DESKTOP
echo "Installed: look for 'Euan Paint' in your app menu."
