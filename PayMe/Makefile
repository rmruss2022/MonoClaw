.PHONY: up down api-test web-test

up:
	docker compose up --build

down:
	docker compose down -v

api-test:
	cd apps/api && . .venv/bin/activate && pytest -q

web-test:
	cd apps/web && npm run test
