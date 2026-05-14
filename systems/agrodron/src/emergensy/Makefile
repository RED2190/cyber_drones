.PHONY: docker-build docker-up unit-test

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml

docker-build:
	@docker build -t emergensy_component -f docker/Dockerfile ../..

docker-up:
	@docker run --rm --name emergensy_component -e COMPONENT_ID=emergensy_standalone emergensy_component

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/ -v

