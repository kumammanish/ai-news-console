#!/usr/bin/env bash
set -euo pipefail

MACOS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$MACOS_DIR")"
APP_NAME="AI News"
APP_PATH="$HOME/Desktop/${APP_NAME}.app"
ICNS_PATH="$MACOS_DIR/AppNews.icns"

if [ ! -f "$ICNS_PATH" ]; then
  echo "Icon not found — generating it first…"
  python3 "$MACOS_DIR/generate_icon.py"
fi

echo "Installing '${APP_NAME}.app' to Desktop, pointing at ${PROJECT_DIR} …"

rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"

cat > "$APP_PATH/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>local.ai-news-console.launcher</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppNews</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

cp "$ICNS_PATH" "$APP_PATH/Contents/Resources/AppNews.icns"

cat > "$APP_PATH/Contents/MacOS/launcher" <<LAUNCHER
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR}"
URL="http://localhost:8000"

is_up() {
  curl -sf "\$URL" >/dev/null 2>&1
}

refresh_then_open() {
  # Best-effort, TTL-respecting refresh so the tab opens with current items
  # instead of whatever was last cached. Never blocks opening the app.
  curl -s -m 45 -X POST "\$URL/api/refresh?force=false" >/dev/null 2>&1 || true
  open "\$URL"
}

if is_up; then
  refresh_then_open
  exit 0
fi

mkdir -p "\$PROJECT_DIR/data"
NO_AUTO_OPEN=1 nohup "\$PROJECT_DIR/run.sh" >>"\$PROJECT_DIR/data/launcher.log" 2>&1 &

for i in \$(seq 1 60); do
  if is_up; then
    refresh_then_open
    exit 0
  fi
  sleep 1
done

osascript -e 'display alert "AI News" message "The server did not start within 60 seconds. Check data/launcher.log in the project folder."'
exit 1
LAUNCHER

chmod +x "$APP_PATH/Contents/MacOS/launcher"

echo "Done. '${APP_NAME}.app' is on your Desktop."
echo "If you move the ${PROJECT_DIR##*/} folder, re-run this script to refresh the baked-in path."
