#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "================================"
echo "  BiliCast Studio - Ubuntu Setup"
echo "================================"
echo ""

log "Checking Python 3..."
if command -v python3 &>/dev/null; then
    log "Python $(python3 --version)"
else
    warn "Installing..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

log "Installing ffmpeg..."
sudo apt update
sudo apt install -y ffmpeg

log "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

log "Installing Python packages..."
pip install --upgrade pip
pip install reportlab yt-dlp faster-whisper

log "Verifying..."
python3 -c "import reportlab; print("  reportlab:", reportlab.Version)" 2>/dev/null && log "reportlab OK"
python3 -c "import yt_dlp; print("  yt-dlp:", yt_dlp.version.__version__)" 2>/dev/null && log "yt-dlp OK"
python3 -c "from faster_whisper import WhisperModel; print("  faster-whisper: OK")" 2>/dev/null && log "faster-whisper OK"
command -v ffmpeg >/dev/null && log "ffmpeg OK" || err "ffmpeg not found"

echo ""
read -p "Setup as systemd service? (y/N): " enable_service
if [[ "$enable_service" =~ ^[Yy]$ ]]; then
    log "Creating systemd service..."
    sudo tee /etc/systemd/system/bilicast.service > /dev/null <<SERVICEEOF
[Unit]
Description=BiliCast Studio
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python server.py --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
Environment=WHISPER_MODEL=small
Environment=WHISPER_DEVICE=cpu

[Install]
WantedBy=multi-user.target
SERVICEEOF
    sudo systemctl daemon-reload
    sudo systemctl enable bilicast
    sudo systemctl start bilicast
    log "Service started"
    sleep 2
    sudo systemctl status bilicast --no-pager | head -10
fi

echo ""
echo "================================"
echo "  Installation Complete!"
echo "================================"
echo ""
echo "Manual start:"
echo "  cd $PROJECT_DIR && source venv/bin/activate && python server.py --host 0.0.0.0 --port 8000"
echo ""
echo "URL: http://YOUR_SERVER_IP:8000"
