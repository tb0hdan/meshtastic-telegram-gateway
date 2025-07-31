VERSION=$(shell cat ./VERSION)
ifndef BOT_CONFIG_PATH
    BOT_CONFIG_PATH=./mesh.ini
endif

all: check

check: lint mypy

lint:
	@pylint -r y -j 0 mesh.py mtg/

mypy:
	@mypy mesh.py


reboot:
	@meshtastic --port $(shell cat mesh.ini|grep Device|awk -F' = ' '{print $$2}') --reboot

run:
	@while :; do ./mesh.py run -c $(BOT_CONFIG_PATH); sleep 3; done

tag:
	@git tag -a v$(VERSION) -m v$(VERSION)
	@git push --tags

test:
	@pytest --cov mtg

docker-up:
	@docker compose up --build -d --remove-orphans

docker-down:
	@docker compose down

docker-restart:
	@docker compose restart meshtastic-telegram-gateway

docker-stop:
	@docker compose stop meshtastic-telegram-gateway

docker-start:
	@docker compose start meshtastic-telegram-gateway
