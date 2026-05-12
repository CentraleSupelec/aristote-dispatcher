#!/bin/sh
set -e

# run migrations
alembic upgrade head

if [ -z "$DO_NOT_UPDATE_CA" ]; then
    update-ca-certificates
fi

# print and run image cmd
echo "$@"
exec "$@"
