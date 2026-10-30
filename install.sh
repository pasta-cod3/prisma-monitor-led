#!/bin/bash
set -e
cd "$(dirname "$0")"
DEST=~/.local/share/monitor-led
URL=http://127.0.0.1:7878

command -v python3 >/dev/null || { echo "Serve python3 (3.8 o successivo)."; exit 1; }

echo "=== Regola udev (accesso ai controller del monitor senza root) ==="
sudo install -m 644 60-msi-monitor-led.rules /etc/udev/rules.d/60-msi-monitor-led.rules
sudo rm -f /etc/udev/rules.d/60-mpg27cq-led.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --subsystem-match=hidraw

echo "=== File del servizio in $DEST ==="
rm -rf "$DEST/msiled" "$DEST/mpg27cq.py"
mkdir -p "$DEST/msiled" "$DEST/dashboard/fonts" ~/.config/systemd/user ~/.local/share/applications
install -m 644 ledd.py diag.py "$DEST/"
install -m 644 msiled/*.py "$DEST/msiled/"
install -m 644 dashboard/index.html dashboard/manifest.json "$DEST/dashboard/"
install -m 644 dashboard/fonts/instrument-sans.woff2 "$DEST/dashboard/fonts/"
install -m 644 monitor-led.service ~/.config/systemd/user/

echo "=== Avvio automatico (anche prima del login grafico) ==="
systemctl --user daemon-reload
systemctl --user enable monitor-led.service
systemctl --user restart monitor-led.service
loginctl enable-linger "$USER" || true

BROWSER_CMD="xdg-open $URL"
for b in google-chrome google-chrome-stable chromium chromium-browser brave-browser microsoft-edge; do
    if command -v "$b" >/dev/null; then BROWSER_CMD="$b --app=$URL"; break; fi
done
cat > ~/.local/share/applications/monitor-led.desktop <<DESK
[Desktop Entry]
Name=Prisma Control
Comment=Illuminazione dei monitor MSI
Exec=$BROWSER_CMD
Icon=preferences-desktop-display
Terminal=false
Type=Application
Categories=Settings;HardwareSettings;
DESK

sleep 2
systemctl --user --no-pager status monitor-led.service | head -3
echo
(cd "$DEST" && python3 -m msiled --detect)
echo
echo "Dashboard: $URL  (oppure 'Prisma Control' nel menu applicazioni)"
