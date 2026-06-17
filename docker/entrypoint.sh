#!/bin/bash
set -e

if [ -f /scripts/download-models.sh ]; then
    /scripts/download-models.sh
fi

mkdir -p ~/.cerebro/db ~/.cerebro/state ~/.cerebro/models

exec "$@"
