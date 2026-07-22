#!/usr/bin/env bash
# Resets the local dev database (native PostgreSQL install — no containers).
set -euo pipefail
dropdb --if-exists campushub
createdb campushub
cd "$(dirname "$0")/../../backend"
alembic upgrade head
echo "Database reset. Run 'make seed' next."
