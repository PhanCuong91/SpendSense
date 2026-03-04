# Run API locally (no Docker)
run:
    uvicorn app.main:app --reload --port 8000

# Build Docker image
build:
    docker-compose build

# Start all services
up:
    docker-compose up

# Start without logs tailing
upd:
    docker-compose up -d

# Stop all containers
down:
    docker-compose down

# Reset database completely
reset-db:
    docker-compose down -v

# Run Alembic migrations
migrate:
    alembic upgrade head

revision:
    alembic revision --autogenerate -m "update"

# Run tests
test:
    pytest -q --disable-warnings --maxfail=1

# Lint (optional)
lint:
    flake8 app

# Format with Black
fmt:
    black app tests


migrate:
    alembic upgrade head

revision:
    alembic revision --autogenerate -m "update
