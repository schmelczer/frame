# Pi setup

Flash an image using the [Raspberry Pi imager](https://www.raspberrypi.com/software/), I picked the Raspberry Pi OS Lite (based on debian trixie) and set up WiFi & SSH from the Customisation settings.

## First commands

```sh
sudo raspi-config   # Then select: Interface Options -> SPI -> Enable

sudo apt update && sudo apt upgrade
sudo apt install -y python3-pip python3-pil python3-smbus python3-numba

sudo systemctl mask swap.target
sudo systemctl disable --now bluetooth
sudo nmcli c modify <your-connection> 802-11-wireless.powersave 2
```

Reduce SD card writes by setting `Storage=volatile` in `/etc/systemd/journald.conf`.

## Deploying

Ensure [.env](src/.env) has the correct paths and then run:

`./sync.sh`

> That rsyncs `src/` over.

## Setting up cron

In `crontab -e`, add:

```
*/15 * * * * cd ~/frame && python3 display.py -o 90 >> ~/frame.log 2>&1
```

### Optionally, to monitor the wifi connection:

In `sudo crontab -e`, add:

```
@reboot /usr/sbin/iw wlan0 set power_save off*/5 * * * * /home/<user>/frame/wifi-check.sh >> /home/<user>/wifi.log 2>&1
```

## Hardware notes

The driver in `src/lib/waveshare_epd/` is adapted from Waveshare's [PhotoPainter](https://www.waveshare.com/wiki/PhotoPainter) project. That wikipage has the wiring, init sequence, and 6-colour palette docs.
