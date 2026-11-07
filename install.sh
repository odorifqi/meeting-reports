#!/bin/bash
# Installer Meeting Notes untuk macOS (Apple Silicon).
# Jalankan dari Terminal:  bash install.sh
set -euo pipefail

APP_NAME="Meeting Notes"
SUPPORT="$HOME/Library/Application Support/MeetingNotes"
APP="$HOME/Applications/$APP_NAME.app"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

say() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Aplikasi ini butuh Mac dengan chip Apple Silicon (M1 ke atas)."
  exit 1
fi

say "Cek Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  else
    echo "Homebrew belum terpasang. Pasang dulu dari https://brew.sh lalu jalankan ulang installer ini."
    exit 1
  fi
fi

say "Pasang ffmpeg dan uv (kalau belum ada)"
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v uv >/dev/null 2>&1 || brew install uv

say "Salin aplikasi ke $SUPPORT"
mkdir -p "$SUPPORT/app"
cp -R "$SRC_DIR/app/." "$SUPPORT/app/"

say "Siapkan Python 3.12 dan library"
if [[ ! -x "$SUPPORT/venv/bin/python" ]]; then
  uv venv --python 3.12 "$SUPPORT/venv"
fi
uv pip install --python "$SUPPORT/venv/bin/python" -r "$SUPPORT/app/requirements.txt"

say "Cek Tk (tampilan aplikasi)"
"$SUPPORT/venv/bin/python" -c "import tkinter; tkinter.Tcl().eval('info patchlevel')" \
  || { echo "tkinter tidak tersedia di Python ini."; exit 1; }

say "Unduh model Whisper large-v3-turbo (~1,6 GB, sekali saja)"
"$SUPPORT/venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')"

say "Buat $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Meeting Notes</string>
  <key>CFBundleDisplayName</key><string>Meeting Notes</string>
  <key>CFBundleIdentifier</key><string>app.meetingreport.desktop</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>MeetingNotes</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>CFBundleDocumentTypes</key>
  <array>
    <dict>
      <key>CFBundleTypeName</key><string>Audio</string>
      <key>CFBundleTypeRole</key><string>Viewer</string>
      <key>LSItemContentTypes</key>
      <array><string>public.audio</string><string>public.movie</string></array>
    </dict>
  </array>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/MeetingNotes" <<LAUNCHER
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
mkdir -p "$SUPPORT/logs"
exec "$SUPPORT/venv/bin/python" "$SUPPORT/app/main.py" "\$@" 2>>"$SUPPORT/logs/error.log"
LAUNCHER
chmod +x "$APP/Contents/MacOS/MeetingNotes"

say "Selesai"
echo "Aplikasi: $APP"
echo "Buka dari Finder > Applications (folder pribadi), atau jalankan: open \"$APP\""
echo "Hasil rapat disimpan di: ~/Documents/Meeting Notes/"
