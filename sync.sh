#!/bin/bash
set -euo pipefail
set -a && . ".env" && set +a
: "${SYNC_TARGET:?SYNC_TARGET must be set in .env (e.g. pi@192.168.0.81:~/frame/)}"
rsync -avz --progress --exclude=.env src/ "$SYNC_TARGET"
