#!/bin/sh
set -eu
apk add --no-cache openssl >/dev/null
umask 077
rm -f /tls/ca.crt /tls/sql-server.key /tls/sql-server.crt /tls/sql-server.csr
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /tmp/compatflow-simulator-ca.key \
  -out /tls/ca.crt \
  -days 7 -sha256 \
  -subj "/CN=CompatFlow Disposable Simulator CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"
openssl genrsa -out /tls/sql-server.key 2048
openssl req -new -key /tls/sql-server.key -out /tmp/sql-server.csr \
  -subj "/CN=sql-supplier"
cat > /tmp/sql-server.ext <<'EOF'
[server_cert]
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,DNS:sql-supplier,IP:127.0.0.1
EOF
openssl x509 -req -in /tmp/sql-server.csr \
  -CA /tls/ca.crt -CAkey /tmp/compatflow-simulator-ca.key \
  -CAcreateserial -out /tls/sql-server.crt -days 7 -sha256 \
  -extfile /tmp/sql-server.ext -extensions server_cert
chmod 755 /tls
chmod 644 /tls/ca.crt /tls/sql-server.crt
chmod 640 /tls/sql-server.key
rm -f /tmp/compatflow-simulator-ca.key /tmp/compatflow-simulator-ca.srl \
  /tmp/sql-server.csr /tmp/sql-server.ext
