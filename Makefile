VERSION = $(shell cat ./VERSION)

all: check

check: lint mypy test

lint:
	@pylint -r y -j 0 mesh.py mtg/

mypy:
	@mypy mesh.py


reboot:
	@DEVICE=$$(grep '^Device' mesh.ini | cut -d'=' -f2 | tr -d ' '); \
	if [ -n "$$DEVICE" ]; then \
		meshtastic --port "$$DEVICE" --reboot; \
	else \
		echo "Error: Device not found in mesh.ini"; \
		exit 1; \
	fi

run:
	@while :; do ./mesh.py; sleep 3; done

tag:
	@git tag -a v$(VERSION) -m v$(VERSION)
	@git push --tags

test:
	@pytest --cov mtg
