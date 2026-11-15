# Disposable supplier connector simulators

These services are for local development and CI only. They use synthetic records
and intentionally weak, fixed credentials. Never deploy this Compose stack to
a public or production network and never reuse its credentials for a real supplier.

## Start

From the repository root:

```bash
export SIMULATOR_READER_PASSWORD="$(python -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters + string.digits + "!@#%") for _ in range(28)))')"
docker compose -f backend/tests/connector-simulator/compose.yaml up -d --wait rest-supplier sftp-supplier sql-supplier
docker compose -f backend/tests/connector-simulator/compose.yaml run --rm sql-init
mkdir -p backend/tests/connector-simulator/runtime
docker compose -f backend/tests/connector-simulator/compose.yaml cp rest-supplier:/run/tls/server.crt backend/tests/connector-simulator/runtime/rest-ca.crt
ssh-keyscan -p 2222 localhost > backend/tests/connector-simulator/runtime/known_hosts
```

Endpoints:
- REST: `https://localhost:8443/catalog?page=1`; header `X-API-Key: local-test-key`.
- SFTP: `localhost:2222`, user `supplier`, password `Supplier-ReadOnly-2026!`, file `/upload/catalog.csv`.
- SQL Server: `localhost:14333`, database `CompatFlowSupplier`; read-only login `compatflow_reader`, with a fresh per-run password in `SIMULATOR_READER_PASSWORD`.

The SQL initializer creates a synthetic product table and grants the connector login
SELECT permission only. A disposable local CA signs a SQL Server certificate whose
SAN covers `localhost` and `sql-supplier`; the SQL Server container forces TLS 1.2.
The CA private key is generated outside the shared volume and discarded after signing.
Install only the CA certificate into the local test machine's trust store as shown
above. The connector test uses Microsoft ODBC Driver 18 with `Encrypt=yes` and
`TrustServerCertificate=no`; do not disable certificate verification to make a
test pass. The seed step uses the SQL tools image's `-C` option only for initial
synthetic database setup; the actual connector integration test performs normal
certificate-chain and hostname verification.

## Run REST, SFTP and SQL Server protocol tests

Install backend requirements, then run:

```bash
cd backend
PYTHONPATH=. COMPATFLOW_CONNECTOR_SIMULATOR=1 \
SIMULATOR_REST_CERT=tests/connector-simulator/runtime/rest-ca.crt \\
SIMULATOR_SFTP_KNOWN_HOSTS=tests/connector-simulator/runtime/known_hosts \\
SIMULATOR_SQLSERVER_URL="mssql+pyodbc://compatflow_reader:${SIMULATOR_READER_PASSWORD}@localhost:14333/CompatFlowSupplier?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no" \\
python -m pytest -q tests/test_connector_simulator_integration.py
```

Stop and remove all simulator containers and volumes:

```bash
docker compose -f backend/tests/connector-simulator/compose.yaml down -v
```

The REST integration test bypasses DNS policy only for this disposable localhost
target because the connector correctly rejects private and loopback targets.
The existing unit suite remains responsible for testing SSRF and host allowlist
rejections. SFTP uses a generated known-hosts file and rejects unknown host keys.
