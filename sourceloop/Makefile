.PHONY: install test lint serve demo frontend docker

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

serve:
	uvicorn sourceloop.api:app --host 0.0.0.0 --port 8000 --reload

demo:
	sourceloop demo --kind facilities_quote

frontend:
	npm --prefix frontend install
	npm --prefix frontend run dev

docker:
	docker compose up --build
