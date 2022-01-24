all: lint

lint:
	@pylint -r y -j 0 mesh.py
