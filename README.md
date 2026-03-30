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
```

Reduce journald writes
Edit /etc/systemd/journald.conf:

```
Storage=volatile
```