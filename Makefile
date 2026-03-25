VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

.PHONY: venv run test demo clean test-no-venv

venv:
	python3 -m venv $(VENV)
	$(PIP) install -e .

run:
	$(PYTHON) -m emotiond.main

test:
	$(PYTHON) -m pytest tests/

test-no-venv:
	python3 -m pytest tests/

demo:
	$(PYTHON) scripts/demo_cli.py

clean:
	rm -rf $(VENV)
	rm -rf __pycache__
	rm -rf */__pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info