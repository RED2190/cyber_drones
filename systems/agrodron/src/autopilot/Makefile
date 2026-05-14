.PHONY: docker-build docker-up unit-test

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml

docker-build:
	@docker build -t autopilot_component -f docker/Dockerfile ../..

docker-up:
	@docker run --rm --name autopilot_component -e COMPONENT_ID=autopilot_standalone autopilot_component

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/ -v

