# Simple, evaluator-friendly Makefile
# Usage:
#   make run           # run the agent once on ICICI
#   make test          # run tests quietly
#   make cov           # run tests with coverage (terminal table)
#   make htmlcov       # build HTML coverage report
#   make regen         # delete generated parser and re-run agent
#   make clean         # remove caches, debug, coverage artifacts

PYTHON ?= python

run:
	$(PYTHON) agent.py --target icici --max-iters 1

test:
	pytest -q

cov:
	pytest --cov=agent --cov=custom_parsers --cov-report=term-missing -q

htmlcov:
	pytest --cov=agent --cov=custom_parsers --cov-report=html -q
	@echo
	@echo "Open htmlcov/index.html in your browser to view the report."

regen:
	@rm -f custom_parsers/icici_parser.py
	$(PYTHON) agent.py --target icici --max-iters 1

clean:
	@rm -rf __pycache__ .pytest_cache .coverage htmlcov debug
