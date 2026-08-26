#!/usr/bin/env bash
set -euo pipefail

# Ensure we run from project root
cd "$(dirname "$0")/.."

echo "========================================================"
echo " SpendSense MISA Docker End-to-End Test & Verification"
echo "========================================================"

PYTHONPATH=. venv/bin/python scripts/test_misa_docker.py "$@"
