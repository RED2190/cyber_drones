.PHONY: docker-build docker-up unit-test

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml

docker-build:
	@docker build -t journal_component -f docker/Dockerfile ../..

docker-up:
	@docker run --rm --name journal_component -e COMPONENT_ID=journal_standalone journal_component

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/ -v

