.PHONY: install test lint demo up down logs sandbox sandbox-smoke sandbox-down doctor

install:
	python -m pip install -e ".[dev]"

lint:
	python -m compileall -q src
	ruff check src tests

test:
	pytest

# Credential-free, deterministic local demo.
demo:
	sourceloop demo --kind facilities_quote

# Production-shaped stack, with outbound delivery and mailbox access disabled by default.
up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

doctor:
	docker compose exec api sourceloop doctor

# Fully local SMTP/IMAP integration. GreenMail never relays to the public internet.
sandbox:
	docker compose -f docker-compose.yml -f docker-compose.sandbox.yml up --build -d

sandbox-smoke: sandbox
	python scripts/sandbox_smoke.py

sandbox-down:
	docker compose -f docker-compose.yml -f docker-compose.sandbox.yml down -v --remove-orphans
