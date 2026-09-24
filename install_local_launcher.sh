#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APP_DIR/anitoon-local-bot.desktop"
REPO_DIR="$HOME/Rename_Bot"

mkdir -p "$APP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=AniToon Local Bot
Comment=Start AniToon bot, health server, and Cloudflare tunnel
Exec=bash -lc 'cd "$REPO_DIR" && bash start_local.sh'
Terminal=true
Categories=Development;Network;
StartupNotify=true
EOF

chmod 644 "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "AniToon Local Bot launcher installed."
echo "Open the ChromeOS Launcher and search for:"
echo "  AniToon Local Bot"
echo
echo "You can pin it to the shelf for one-click startup."
