
#!/bin/bash
echo "Resetting environment…"
echo "$(pwd)"
rm -f app_1.log
docker-compose down -v
docker compose up -d db
PYTHONPATH="$(pwd)" alembic upgrade head

echo "Environment reset complete."
