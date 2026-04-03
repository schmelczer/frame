#!/bin/bash

if ! ping -c 1 -W 5 192.168.0.1 > /dev/null 2>&1; then
    logger "WiFi check: no connectivity, restarting wlan0"
    ip link set wlan0 down
    sleep 2
    ip link set wlan0 up
fi
