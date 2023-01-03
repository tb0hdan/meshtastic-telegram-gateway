# meshtastic-telegram-gateway
![Build](https://github.com/tb0hdan/meshtastic-telegram-gateway/actions/workflows/build.yml/badge.svg)
![CodeQL](https://github.com/tb0hdan/meshtastic-telegram-gateway/actions/workflows/codeql-analysis.yml/badge.svg)
![Python versions](https://shields.io/badge/python-3.7%20|%203.8%20|%203.9%20|%203.10%20|%203.11-green)
![Snyk vulnerabilities](https://img.shields.io/snyk/vulnerabilities/github/tb0hdan/meshtastic-telegram-gateway)

*Read this in other languages: [English](README.md), [Polski](README.pl.md), [Português](README.pt.md)*

telegram bot that forwards messages to and from Meshtastic device

The purpose of this bot is to act as a bridge between local Meshtastic conference and
Telegram chat room. Nicks (Your Name field for Meshtastic) are passed through in both directions.

## Supported Hardware

[See official Meshtastic Python list](https://github.com/meshtastic/python/blob/master/meshtastic/supported_device.py)

### Online stores for HW purchase

[Aliexpress NEO-6M](https://www.aliexpress.com/item/4001178678568.html)

[Aliexpress NEO-8M (better)](https://www.aliexpress.com/item/4001287221970.html)

[Amazon](https://www.amazon.com/TTGO-Meshtastic-T-Beam-Bluetooth-Battery/dp/B08GLDQDW1)

[Banggood](https://www.banggood.com/LILYGO-TTGO-Meshtastic-T-Beam-V1_1-ESP32-433-or-915-or-923Mhz-WiFi-Bluetooth-ESP32-GPS-NEO-6M-SMA-18650-Battery-Holder-With-OLED-p-1727472.html)

[Ebay](https://www.ebay.com/itm/353398290066)

[Tindie](https://www.tindie.com/products/lilygo/lilygo-ttgo-t-beam-v11-esp32/)

[TomTop](https://www.tomtop.com/p-e13012-4.html)

![Meshtastic T-Beam v1.1](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/tbeam_11.jpeg)

## Typical use case

![Meshtastic diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot.drawio.png)

### Interconnecting cities

![Meshtastic cross diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot-cross.drawio.png)

## Supported software

Python 3.7+ is required.

## Webapp

When enabled, this bot listens on specified port and renders device map.

1. Cluster markerer

![Cluster Markerer](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/gmaps.png)

2. Device details

![Device Details](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/gmaps_details.png)

3. Actual Kyiv community map

[Kyiv map](https://mesh.0x21h.net)

4. Tail duration

Default value is 3600 seconds. Can be changed using `?tail=xxx` query string, e.g.

[https://mesh.0x21h.net/?tail=7200](https://mesh.0x21h.net/?tail=7200)


## Setup

1. Run `cat mesh.ini.example|egrep -v '^#' > mesh.ini`
2. Create new Telegram bot using [@BotFather](https://t.me/BotFather) contact. Copy token to clipboard.
3. Put token from previous step into `mesh.ini`
4. Put admin id and room id into `mesh.ini`
5. Edit `mesh.ini` Meshtastic section to reflect your device configuration (usually not required, for Linux at least)
6. Run `sudo pip3 install -r requirements.txt`
7. Run `gpasswd -a youruser dialout`
8. Relogin
9. Run `make run`
10. Enjoy


## Supported bot commands

### Telegram only

1. `/start` - basic command to confirm that bot is up and running
2. `/nodes` - return list of known nodes (including those reachable via other hops)
3. `/qr` - return active QR code for configuring new Meshtastic devices
4. `/map` - return link to map

### Meshtastic only

1. `/distance` - print distance to other Meshtastic devices (in meters)
Sample answer:

```
UR5YBM-aa60: 19m
UT3ULJ: 2,316m
```


2. `/ping` - ping currently connected Meshtastic node and get response.
Sample answer:

```
Pong from UR5YBM-aa60 at 10.00 SNR time=9.632s
```

3. `/stats` - get some stats for current node
Sample anwser:

```
Locations: 1234. Messages: 20
```

### Common

`/reboot` - request Meshtastic device reboot. Requires respective admin privileges.

`/uptime` - returns bot version/uptime
