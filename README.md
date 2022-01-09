# meshtastic-telegram-gateway
telegram bot that forwards messages to and from meshtastic device

The purpose of this bot is to act as a bridge between local Meshtastic conference and
Telegram chat room. Nicks (Your Name field for Meshtastic) are passed through in both directions.

## Supported Hardware

Meshtastic T-Beam v1.1

![Meshtastic T-Beam v1.1](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/img/tbeam_11.jpeg)

## Setup

1. Create new Telegram bot using @BotFather contact. Copy token to clipboard.
2. Run `cp mesh.ini.example mesh.ini`
3. Run `sudo pip3 install -r requirements.txt`
4. Put token from previous step into `mesh.ini`
5. Put admin id and room id into `mesh.ini`
6. Edit `mesh.ini` Meshtastic section to reflect your device configuration (usually not required, for Linux at least)
7. Run `gpasswd -a youruser dialout`
8. Relogin
9. Run `./mesh.py`
10. Enjoy
