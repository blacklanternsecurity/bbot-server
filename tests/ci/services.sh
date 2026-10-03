#!/usr/bin/env bash
docker compose -f compose.yml -f tests/ci/compose.yml up -d --wait mongodb redis
