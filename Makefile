.PHONY: install test eval

install:
	pip install -r requirements.txt

test:
	python -m pytest -q

eval:
	python scripts/evaluate.py
