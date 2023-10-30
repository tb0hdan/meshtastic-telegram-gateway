# meshtastic-telegram-gateway
![Build](https://github.com/tb0hdan/meshtastic-telegram-gateway/actions/workflows/build.yml/badge.svg)
![CodeQL](https://github.com/tb0hdan/meshtastic-telegram-gateway/actions/workflows/codeql-analysis.yml/badge.svg)
![Python versions](https://shields.io/badge/python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12-green)
![Snyk vulnerabilities](https://img.shields.io/snyk/vulnerabilities/github/tb0hdan/meshtastic-telegram-gateway)

*Przeczytaj to w innych językach: [English](README.md), [Polski](README.pl.md), [Português](README.pt.md)*

telegram bot, który przekazuje wiadomości do iz urządzenia Meshtastic

Celem tego bota jest działanie jako pomost między lokalną konferencją Meshtastic a
Pokój czatu telegramu. Nicky (pole Twoje imię i nazwisko dla Meshtastic) są przekazywane w obu kierunkach.

## Obsługiwany sprzęt

[Zobacz oficjalną listę Pythona Meshtastic](https://github.com/meshtastic/python/blob/master/meshtastic/supported_device.py)

### Sklepy internetowe do zakupu HW

[Aliexpress NEO-6M](https://www.aliexpress.com/item/4001178678568.html)

[Aliexpress NEO-8M (better)](https://www.aliexpress.com/item/4001287221970.html)

[Amazon](https://www.amazon.com/TTGO-Meshtastic-T-Beam-Bluetooth-Battery/dp/B08GLDQDW1)

[Banggood](https://www.banggood.com/LILYGO-TTGO-Meshtastic-T-Beam-V1_1-ESP32-433-or-915-or-923Mhz-WiFi-Bluetooth-ESP32-GPS-NEO-6M-SMA-18650-Battery-Holder-With-OLED-p-1727472.html)

[Ebay](https://www.ebay.com/itm/353398290066)

[Tindie](https://www.tindie.com/products/lilygo/lilygo-ttgo-t-beam-v11-esp32/)

[TomTop](https://www.tomtop.com/p-e13012-4.html)

![Meshtastic T-Beam v1.1](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/tbeam_11.jpeg)


## Typowy przypadek użycia

![Meshtastic diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot.drawio.png)

## Połączone miasta

### Używanie MQTT (zalecane)

![Meshtastic cross MQTT diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot-cross-mqtt.drawio.png)

### Korzystanie z wielu botów telegramowych

![Meshtastic cross diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot-cross.drawio.png)



## Obsługiwane oprogramowanie

Python 3.8+ jest wymagany.

## Aplikacja internetowa

Po włączeniu ten bot nasłuchuje na określonym porcie i renderuje mapę urządzenia.

1. Znacznik klastrów

![Znacznik klastrów](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/gmaps.png)

2. Szczegóły urządzenia

![Szczegóły urządzenia](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/gmaps_details.png)

3. Aktualna mapa społeczności Kijowa

[Mapa Kijowa](https://mesh.0x21h.net)

4. Czas trwania ogona

Wartość domyślna to 3600 sekund. Można zmienić za pomocą ciągu zapytania `?tail=xxx`, np.

[https://mesh.0x21h.net/?tail=7200](https://mesh.0x21h.net/?tail=7200)


## Ustawiać

1. Uruchom `cat mesh.ini.example|egrep -v '^#' > mesh.ini`
2. Utwórz nowego bota Telegrama, korzystając z kontaktu [@BotFather](https://t.me/BotFather). Skopiuj token 
do schowka.
3. Umieść token z poprzedniego kroku w `mesh.ini`
4. Umieść identyfikator administratora i identyfikator pokoju w `mesh.ini`
5. Edytuj sekcję `mesh.ini` Meshtastic, aby odzwierciedlić konfigurację twojego urządzenia (zwykle nie jest 
to wymagane, dla Linuksa przynajmniej)
6. Uruchom `sudo pip3 install -r wymagania.txt`
7. Uruchom `gpasswd -a youruser dialout`
8. Zaloguj się ponownie
9. Uruchom `./start.sh`.
10. Ciesz się

## Obsługiwane polecenia bota

### Tylko Telegram

1. `/start` - podstawowe polecenie potwierdzające, że bot działa
2. `/nodes` - zwraca listę znanych węzłów (włączając te osiągalne przez inne przeskoki)
3. `/qr` - zwróć aktywny kod QR do konfiguracji nowych urządzeń Meshtastic
4. `/map` - link zwrotny do mapy

### Tylko Meshtastic

1. `/distance` - odległość wydruku do innych urządzeń Meshtastic (w metrach)
Przykładowa odpowiedź:

```
UR5YBM-aa60: 19m
UT3ULJ: 2,316m
```

2. `/ping` - ping aktualnie podłączonego węzła Meshtastic i uzyskaj odpowiedź.
Przykładowa odpowiedź:

```
Pong from UR5YBM-aa60 at 10.00 SNR time=9.632s
```

3. `/stars` - pobierz statystyki dla bieżącego węzła
Przykładowa odpowiedź:

```
Locations: 1234. Messages: 20
```

### Pospolity

`/reboot` - żądanie ponownego uruchomienia urządzenia Meshtastic. Wymaga odpowiednich uprawnień 
administratora.

`/uptime` - zwraca wersję/czas pracy bota

