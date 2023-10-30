# meshtastic-telegram-gateway
![Build](https://github.com/tb0hdan/meshtastic-telegram-gateway/actions/workflows/build.yml/badge.svg)
![CodeQL](https://github.com/tb0hdan/meshtastic-telegram-gateway/actions/workflows/codeql-analysis.yml/badge.svg)
![Python versions](https://shields.io/badge/python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12-green)
![Snyk vulnerabilities](https://img.shields.io/snyk/vulnerabilities/github/tb0hdan/meshtastic-telegram-gateway)

*Leia isto em outros idiomas: [English](README.md), [Polski](README.pl.md), [Português](README.pt.md)*

bot de telegrama que encaminha mensagens de e para o dispositivo Meshtastic

O objetivo deste bot é atuar como uma ponte entre a conferência Meshtastic local e
Sala de bate-papo do telegrama. Nicks (seu campo de nome para Meshtastic) são passados em ambas as direções.

## Hardware suportado

[Veja a lista oficial do Meshtastic Python](https://github.com/meshtastic/python/blob/master/meshtastic/supported_device.py)

### Lojas online para compra de HW

[Aliexpress NEO-6M](https://www.aliexpress.com/item/4001178678568.html)

[Aliexpress NEO-8M (better)](https://www.aliexpress.com/item/4001287221970.html)

[Amazon](https://www.amazon.com/TTGO-Meshtastic-T-Beam-Bluetooth-Battery/dp/B08GLDQDW1)

[Banggood](https://www.banggood.com/LILYGO-TTGO-Meshtastic-T-Beam-V1_1-ESP32-433-or-915-or-923Mhz-WiFi-Bluetooth-ESP32-GPS-NEO-6M-SMA-18650-Battery-Holder-With-OLED-p-1727472.html)

[Ebay](https://www.ebay.com/itm/353398290066)

[Tindie](https://www.tindie.com/products/lilygo/lilygo-ttgo-t-beam-v11-esp32/)

[TomTop](https://www.tomtop.com/p-e13012-4.html)

![Meshtastic T-Beam v1.1](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/tbeam_11.jpeg)


## Caso de uso típico

![Meshtastic diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot.drawio.png)

## Cidades interligadas

### Usando MQTT (recomendado)

![Meshtastic cross MQTT diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot-cross-mqtt.drawio.png)

### Usando vários bots de telegrama

![Meshtastic cross diagram](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/MeshtasticBot-cross.drawio.png)



## Software suportado

Python 3.8+ é obrigatório

## Aplicativo web

Quando habilitado, este bot escuta na porta especificada e renderiza o mapa do dispositivo.

1. Marcador de cluster

![Marcador de cluster](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/gmaps.png)

2. Detalhes do dispositivo

![Detalhes do dispositivo](https://raw.githubusercontent.com/tb0hdan/meshtastic-telegram-gateway/master/doc/img/gmaps_details.png)

3. Mapa real da comunidade de Kyiv

[Mapa real da comunidade de Kyiv](https://mesh.0x21h.net)

4. Duração da cauda

O valor padrão é 3600 segundos. Pode ser alterado usando a string de consulta `?tail=xxx`, por exemplo

[https://mesh.0x21h.net/?tail=7200](https://mesh.0x21h.net/?tail=7200)


## Configurar

1. Execute `cat mesh.ini.example|egrep -v '^#' > mesh.ini`
2. Crie um novo bot do Telegram usando o contato [@BotFather](https://t.me/BotFather). Copie o token para a 
área de transferência.
3. Coloque o token da etapa anterior em `mesh.ini`
4. Coloque o ID do administrador e o ID da sala em `mesh.ini`
5. Edite a seção Meshtastic `mesh.ini` para refletir a configuração do seu dispositivo (geralmente não é 
necessário, pelo menos para Linux)
6. Execute `sudo pip3 install -r requirements.txt`
7. Execute `gpasswd -a youruser dialout`
8. Relogue
9. Execute `./start.sh`
10. Aproveite

## Comandos de bot suportados

### Somente Telegram

1. `/start` - comando básico para confirmar que o bot está funcionando
2. `/nodes` - lista de retorno de nós conhecidos (incluindo aqueles acessíveis por outros saltos)
3. `/qr` - retorna o código QR ativo para configurar novos dispositivos Meshtastic
4. `/map` - link de retorno ao mapa

### Somente Meshtastic

1. `/distance` - distância de impressão para outros dispositivos Meshtastic (em metros)
Exemplo de resposta:

```
UR5YBM-aa60: 19m
UT3ULJ: 2,316m
```

2. `/ping` - ping no nó Meshtastic atualmente conectado e obter resposta.
Exemplo de resposta:

```
Pong from UR5YBM-aa60 at 10.00 SNR time=9.632s
```

3. `/stars` - obtenha algumas estatísticas para o nó atual
Exemplo de resposta:

```
Locations: 1234. Messages: 20
```

### Comum

`/reboot` - solicita a reinicialização do dispositivo Meshtastic. Requer os respectivos privilégios de 
administrador.

`/uptime` - retorna a versão/tempo de atividade do bot
