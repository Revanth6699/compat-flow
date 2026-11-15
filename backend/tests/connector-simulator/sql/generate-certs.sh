#!/bin/sh
set -eu
apk add --no-cache openssl >/dev/null
umask 077
rm -f /tls/sql-server.key /tls/sql-server.crt
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout /tls/sql-server.key \
  -out /tls/sql-server.crt \
  -days 7 -sha256 \
  -subj "/CN=sql-supplier" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign,cRLSign" \
  -addext "extendedKeyUsage=serverAuth" \
  -addext "subjectAltName=DNS:sql-supplier,DNS:localhost,IP:127.0.0.1"
chmod 755 /tls
chmod 644 /tls/sql-server.crt
chmod 640 /tls/sql-server.key
