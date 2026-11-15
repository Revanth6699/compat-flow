#!/bin/sh
set -eu
apk add --no-cache openssl >/dev/null
umask 077
rm -f /tls/sql-server.key /tls/sql-server.crt
openssl req -x509 -nodes -newkey rsa:2048 \
  -subj "/CN=sql-supplier" \
  -keyout /tls/sql-server.key \
  -out /tls/sql-server.crt \
  -days 7
chmod 755 /tls
chmod 644 /tls/sql-server.crt
chmod 640 /tls/sql-server.key
