.PHONY: docker-build docker-up unit-test

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml

docker-build:
	@docker build -t security_monitor -f docker/Dockerfile ../..

docker-up:
	@docker run --rm --name security_monitor -e COMPONENT_ID=security_monitor_standalone security_monitor

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/ -v

