#!/bin/sh
set -e

update-ca-certificates

# print and run image cmd
echo "$@"
exec "$@"
