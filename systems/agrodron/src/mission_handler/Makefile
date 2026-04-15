.PHONY: docker-build docker-up unit-test

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml

docker-build:
\t@docker build -t mission_handler_component -f docker/Dockerfile ../..

docker-up:
\t@docker run --rm --name mission_handler_component -e COMPONENT_ID=mission_handler_standalone mission_handler_component

unit-test:
\t@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/ -v

