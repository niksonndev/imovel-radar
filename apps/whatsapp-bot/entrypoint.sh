#!/bin/sh
set -eu
mkdir -p /data
chown -R app:app /data
exec gosu app /usr/local/bin/whatsapp-bot
