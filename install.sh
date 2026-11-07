#!/bin/bash
# Installer Meeting Report v1.3 untuk macOS (Apple Silicon).
# Jalankan dari Terminal di folder repo:  ./install.sh
# Aman diulang. Versi v1 (Tkinter) disimpan sebagai cadangan di app-v1/.
set -euo pipefail

APP_NAME="Meeting Report"
OLD_APP="$HOME/Applications/Meeting Notes.app"
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

say "Hentikan server yang sedang jalan (kalau ada)"
pkill -f "$SUPPORT/app/server.py" 2>/dev/null || true

mkdir -p "$SUPPORT"
if [[ -f "$SUPPORT/app/main.py" ]] && grep -q "tkinter" "$SUPPORT/app/main.py" && [[ ! -d "$SUPPORT/app-v1" ]]; then
  say "Simpan aplikasi v1 sebagai cadangan di $SUPPORT/app-v1"
  mv "$SUPPORT/app" "$SUPPORT/app-v1"
fi

say "Salin aplikasi ke $SUPPORT/app"
mkdir -p "$SUPPORT/app"
rsync -a --delete --exclude "__pycache__" "$SRC_DIR/app/" "$SUPPORT/app/"

say "Siapkan Python 3.12 dan library"
if [[ ! -x "$SUPPORT/venv/bin/python" ]]; then
  uv venv --python 3.12 "$SUPPORT/venv"
fi
uv pip install --python "$SUPPORT/venv/bin/python" -r "$SUPPORT/app/requirements.txt"

say "Cek model Whisper large-v3-turbo (~1,6 GB, diunduh sekali saja; model Akurat large-v3 ~3,1 GB diunduh saat pertama dipilih)"
"$SUPPORT/venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')"

say "Buat $APP"
rm -rf "$APP"
if [[ -d "$OLD_APP" ]]; then
  echo "Aplikasi lama \"Meeting Notes.app\" dipindah ke Trash (diganti \"Meeting Report.app\")."
  osascript -e "tell application \"Finder\" to delete POSIX file \"$OLD_APP\"" >/dev/null 2>&1 || rm -rf "$OLD_APP"
fi
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# one version source: APP_VERSION in app/server.py (also shown in the app's sidebar)
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "$SRC_DIR/app/server.py")"
VERSION="${VERSION:-0}"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Meeting Report</string>
  <key>CFBundleDisplayName</key><string>Meeting Report</string>
  <key>CFBundleIdentifier</key><string>app.meetingreport.desktop</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>MeetingNotes</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
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

if [[ -d "$SRC_DIR/app/icon/AppIcon.iconset" ]]; then
  iconutil -c icns "$SRC_DIR/app/icon/AppIcon.iconset" -o "$APP/Contents/Resources/AppIcon.icns" || echo "Ikon gagal dibuat (aplikasi tetap jalan)."
fi
touch "$APP"

say "Selesai"
echo "Aplikasi: $APP"
echo "Buka dari Finder > Applications (folder pribadi), atau jalankan: open \"$APP\""
echo "Hasil rapat di: ~/Documents/Meeting Report/ (isi ~/Documents/Meeting Notes dipindah ke sana saat aplikasi pertama dibuka)"
echo "Cadangan v1: $SUPPORT/app-v1 (kalau ada)"
