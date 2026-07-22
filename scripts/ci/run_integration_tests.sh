#!/usr/bin/env bash
# Runs backend integration tests against testcontainers-managed services.
# See docs/12-testing-strategy.md §3.
set -euo pipefail
cd "$(dirname "$0")/../../backend"
pytest tests/integration
