#!/bin/bash
# Probe what actually matters (DNS to a real target) and escalate recovery
# steps until something works. `ip link down/up` alone can't unwedge the
# brcmfmac chip on the Pi Zero 2W.

CONNECTION="netplan-wlan0-HiddenPlace"
PROBE_HOST="homeassistant.example.com"

probe() {
    ping -c 1 -W 5 192.168.0.1 >/dev/null 2>&1 \
        && getent hosts "$PROBE_HOST" >/dev/null 2>&1
}

probe && exit 0

logger "wifi-check: probe failed, reconnecting via nmcli"
nmcli device disconnect wlan0
sleep 2
nmcli connection up "$CONNECTION"
sleep 10
probe && exit 0

logger "wifi-check: nmcli failed, cycling rfkill"
rfkill block wifi
sleep 3
rfkill unblock wifi
sleep 15
probe && exit 0

logger "wifi-check: rfkill failed, reloading brcmfmac"
modprobe -r brcmfmac brcmutil
sleep 3
modprobe brcmfmac
sleep 20
probe && exit 0

logger "wifi-check: all recovery failed, rebooting"
/sbin/reboot
