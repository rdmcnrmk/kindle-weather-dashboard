PYTHON ?= python3

.PHONY: test build check preview source

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

build:
	$(PYTHON) scripts/build.py

check:
	$(PYTHON) scripts/build.py --check

preview:
	$(PYTHON) tests/render_preview.py

source:
	$(PYTHON) scripts/build.py --source
