#!/bin/sh
set -e

# run migrations
alembic upgrade head

# print and run image cmd
echo "$@"
exec "$@"
