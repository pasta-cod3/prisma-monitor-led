#!/bin/bash
systemctl --user disable --now monitor-led.service 2>/dev/null
rm -rf ~/.local/share/monitor-led ~/.config/systemd/user/monitor-led.service ~/.local/share/applications/monitor-led.desktop
systemctl --user daemon-reload
sudo rm -f /etc/udev/rules.d/60-msi-monitor-led.rules /etc/udev/rules.d/60-mpg27cq-led.rules
sudo udevadm control --reload-rules
[ "$1" = "--purge" ] && rm -rf ~/.config/monitor-led
echo "Disinstallato. I LED restano con l'ultima impostazione salvata nel monitor."
