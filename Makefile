.PHONY: help install test lint clean build deploy deploy-dev deploy-prod local-test

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linter"
	@echo "  make build        - Build SAM application"
	@echo "  make deploy-dev   - Deploy to dev environment"
	@echo "  make deploy-prod  - Deploy to production"
	@echo "  make local-test   - Test Lambda locally"
	@echo "  make clean        - Remove build artifacts"

install:
	pip install -r requirements.txt
	pip install pytest pytest-cov flake8

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

clean:
	rm -rf .aws-sam/
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '.coverage' -delete

build:
	sam build

deploy-dev: build
	sam deploy \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		--stack-name alphaback-verify-dev \
		--parameter-overrides Environment=dev \
		--capabilities CAPABILITY_IAM

deploy-prod: build
	@echo "⚠️  Deploying to PRODUCTION. Are you sure? [y/N]" && read ans && [ $${ans:-N} = y ]
	sam deploy \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		--stack-name alphaback-verify-prod \
		--parameter-overrides Environment=prod \
		--capabilities CAPABILITY_IAM

local-test:
	@echo "Testing with valid model..."
	sam local invoke VerifyFunction -e tests/events/valid_model_event.json
	@echo ""
	@echo "Testing with invalid model..."
	sam local invoke VerifyFunction -e tests/events/invalid_model_event.json

package: build
	sam package --output-template-file packaged.yaml --s3-bucket your-deployment-bucket

validate:
	sam validate

logs-dev:
	sam logs -n VerifyFunction --stack-name alphaback-verify-dev --tail

logs-prod:
	sam logs -n VerifyFunction --stack-name alphaback-verify-prod --tail
