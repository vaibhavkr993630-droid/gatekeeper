#!/bin/sh
# Run pending migrations before serving. Fine for a single-instance demo;
# at scale, migrations should be a separate release step so N replicas
# booting together don't race each other applying the same revision.
set -e
alembic upgrade head
exec "$@"
