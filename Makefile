SHELL := /bin/bash -O globstar

test:
	:
	#python3 -m pytest --cov-report term-missing --cov-report html --cov-branch \
	#       --cov housekeeper_tg_bot/

lint:
	@echo
	ruff .
	@echo
	blue --check --diff --color .
	@echo
	mypy .
	@echo
	pip-audit


format:
	ruff --silent --exit-zero --fix .
	blue .


install_hooks:
	@ scripts/install_hooks.sh
