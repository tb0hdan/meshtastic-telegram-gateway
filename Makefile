all: check

check: lint mypy

lint:
	@pylint -r y -j 0 mesh.py

mypy:
	@mypy mesh.py


reboot:
	@meshtastic --port $(shell cat mesh.ini|grep Device|awk -F' = ' '{print $$2}') --reboot

run:
	@while :; do ./mesh.py; sleep 3; done
