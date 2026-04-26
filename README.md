## Installation

sudo raspi-confi
- Enable SPI

```sh
sudo apt update
sudo apt upgrade
sudo apt install -y python3-pip python3-pil python3-opencv python3-smbus python3-numba
sudo swapoff -a
sudo systemctl mask swap.target
sudo systemctl disable --now bluetooth

sudo nmcli c modify netplan-wlan0-HiddenPlace 802-11-wireless.powersave 2
```

Execute `sudo crontab -e` reland add
```
@reboot /usr/sbin/iw wlan0 set power_save off
*/5 * * * * /home/andras/frame/wifi-check.sh >> /home/andras/wifi.log 2>&1
```

Execute `crontab -e` and add
```
*/15 * * * * cd ~/frame && python3 display.py -o 90 >> ~/frame.log 2>&1
```


Reduce journald writes
Edit /etc/systemd/journald.conf:
```
Storage=volatile
```
