all: check

check: lint mypy

lint:
	@pylint -r y -j 0 mesh.py

mypy:
	@mypy mesh.py

run:
	@while :; do ./mesh.py; sleep 3; done
