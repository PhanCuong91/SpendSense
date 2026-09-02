# ============================================================
# SpendSense — Makefile
# ============================================================

# ---- Local development (no Docker) -------------------------

# Run poller worker locally (continuous)
poller:
	python -m app.workers.poller_worker

# Run poller in one-shot mode (poll once, then exit)
poller-once:
	POLL_ONCE=true python -m app.workers.poller_worker

# Run MISA importer (dry-run by default; set MISA_ARGS for real run)
# Example: make misa MISA_ARGS="--start-date 2024-01-01 --end-date 2024-01-31"
misa:
	python -m app.misa.runner --dry-run $(MISA_ARGS)

# ---- Docker ------------------------------------------------

# Build Docker image
build:
	docker-compose build

# Start all services (with logs)
up:
	docker-compose up

# Start without tailing logs
upd:
	docker-compose up -d

# Stop all containers
down:
	docker-compose down

# Reset database volume completely
reset-db:
	docker-compose down -v

# ---- Database migrations (Alembic) -------------------------

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "update"

# ---- Tests -------------------------------------------------

test:
	pytest -q --disable-warnings --maxfail=1

# ---- Code quality ------------------------------------------

lint:
	flake8 app

fmt:
	black app tests

# ---- MISA setup --------------------------------------------

# Install Playwright Chromium browser (required for misa.runner)
misa-setup:
	playwright install chromium

.PHONY: poller poller-once misa build up upd down reset-db migrate revision test lint fmt misa-setup
