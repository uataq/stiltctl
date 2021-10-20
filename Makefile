.PHONY: help ci clean dependencies install format lint test infra

help:  ## Print available options.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


ci: install format lint test ## Run all checks.

clean:  ## Remove development assets.
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
	find . -name '.mypy_cache' -exec rm -fr {} +
	find . -name '.pytest_cache' -exec rm -fr {} +
	find . -name '.coverage*' -exec rm -fr {} +
	find . -name '*.icloud' -exec rm -fr {} +
	rm -fr .venv
	rm -fr .cloudstorage
	rm -rf prof
	docker compose rm --force

dependencies:  ## Run local services in current shell for development.
	docker compose rm --force
	docker compose up --remove-orphans --force-recreate

install:  ## Create virtual environment and install dev dependencies.
	poetry install

format:  # Check formatting.
	poetry run isort --check stiltctl tests
	poetry run black --check stiltctl tests
	poetry run autoflake --check --recursive stiltctl tests

lint:  ## Run mypy.
	poetry run mypy stiltctl tests

test: ## Run tests.
	time poetry run pytest \
		--cov-report=term-missing \
		--cov=stiltctl \
		--durations=10 \
		--profile \
		tests

infra: ## Deploy infrastructure from terraform config.
	./scripts/deploy_infra.sh

deploy: ## Deploy services to k8s.
	./scripts/deploy.sh