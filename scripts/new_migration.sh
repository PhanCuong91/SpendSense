#!/bin/bash
msg=$1
if [ -z "$msg" ]; then
  echo "Usage: ./scripts/new_migration.sh <message>"
  exit 1
fi

alembic revision --autogenerate -m "$msg"