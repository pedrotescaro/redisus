PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest

.PHONY: install-ci install-dev lint lint-full format-check typecheck test test-smoke coverage web-install web-lint web-typecheck web-build artifact-check

install-ci:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-ci.txt

install-dev:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	pre-commit install

lint:
	$(PYTHON) -m ruff check apps packages src tests scripts main.py heal_platform.py realtime_app.py

lint-full:
	$(PYTHON) -m ruff check --select E,F,I,UP,B,SIM apps packages src tests scripts main.py heal_platform.py realtime_app.py

format-check:
	$(PYTHON) -m ruff format --check apps packages src tests scripts main.py heal_platform.py realtime_app.py

typecheck:
	$(PYTHON) -m mypy apps packages src

test:
	$(PYTEST)

test-smoke:
	$(PYTEST) tests/test_clinical_api_contracts.py tests/test_fhir_client.py tests/test_risk_stratification.py tests/test_official_api_factory.py tests/test_api_security.py -q

coverage:
	$(PYTEST) --cov=apps --cov=packages --cov=src/interoperability --cov=src/risk --cov-report=term-missing --cov-report=xml

web-install:
	cd web/redisus-frontend && npm ci

web-lint:
	cd web/redisus-frontend && npm run lint

web-typecheck:
	cd web/redisus-frontend && npx tsc --noEmit

web-build:
	cd web/redisus-frontend && npm run build

artifact-check:
	git ls-files dataset models runs tmp_images '*.pt' '*.pth' '*.keras' '*.h5' '*.ckpt' '*.onnx' '*.tflite' '*.task' '*.db' '*.docx' '*.mp4'
