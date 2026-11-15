#!/bin/sh
set -eu
apk add --no-cache openssl >/dev/null
umask 077

rm -f /tls/sql-ca.key /tls/sql-ca.crt /tls/sql-ca.srl \
  /tls/sql-server.key /tls/sql-server.csr /tls/sql-server.crt /tls/sql-server.ext

# Disposable test-only root CA. The CI client trusts this CA, not the leaf.
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /tls/sql-ca.key \
  -out /tls/sql-ca.crt \
  -days 7 -sha256 \
  -subj "/CN=CompatFlow SQL Simulator Root CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"

openssl req -new -newkey rsa:2048 -nodes \
  -keyout /tls/sql-server.key \
  -out /tls/sql-server.csr \
  -sha256 \
  -subj "/CN=sql-supplier"

cat > /tls/sql-server.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:sql-supplier,DNS:localhost,IP:127.0.0.1
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

openssl x509 -req \
  -in /tls/sql-server.csr \
  -CA /tls/sql-ca.crt \
  -CAkey /tls/sql-ca.key \
  -CAcreateserial \
  -out /tls/sql-server.crt \
  -days 7 -sha256 \
  -extfile /tls/sql-server.ext

chmod 755 /tls
chmod 644 /tls/sql-ca.crt /tls/sql-server.crt
chmod 640 /tls/sql-server.key
chmod 600 /tls/sql-ca.key
