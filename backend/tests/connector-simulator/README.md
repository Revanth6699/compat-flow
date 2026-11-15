# Disposable supplier connector simulators

These services are for local development and CI only. They use synthetic records
and intentionally weak, fixed credentials. Never deploy this Compose stack to
a public or production network and never reuse its credentials for a real supplier.

## Start

From the repository root:

```bash
docker compose -f backend/tests/connector-simulator/compose.yaml up -d --wait rest-supplier sftp-supplier sql-supplier
docker compose -f backend/tests/connector-simulator/compose.yaml run --rm sql-init
mkdir -p backend/tests/connector-simulator/runtime
docker compose -f backend/tests/connector-simulator/compose.yaml cp rest-supplier:/run/tls/server.crt backend/tests/connector-simulator/runtime/rest-ca.crt
ssh-keyscan -p 2222 localhost > backend/tests/connector-simulator/runtime/known_hosts
```

Endpoints:
- REST: `https://localhost:8443/catalog?page=1`; header `X-API-Key: local-test-key`.
- SFTP: `localhost:2222`, user `supplier`, password `Supplier-ReadOnly-2026!`, file `/upload/catalog.csv`.
- SQL Server: `localhost:14333`, database `CompatFlowSupplier`; read-only login `compatflow_reader`, password `Simulator-ReadOnly-2026!`.

The SQL initializer creates a synthetic product table and grants the connector login
SELECT permission only. The container uses a development TLS certificate. The SQL
connector requires Microsoft ODBC Driver 18, encryption enabled, and certificate
validation enabled; do not set `TrustServerCertificate=yes` just to force a test
through. A trusted SQL Server test certificate must be configured before running
the SQL connector against this simulator. Until then, the automated protocol job
executes live REST and SFTP tests and retains SQL Server policy/query tests in the
unit suite; it does not claim a live SQL Server connector pass.

## Run REST and SFTP protocol tests

Install backend requirements, then run:

```bash
cd backend
PYTHONPATH=. COMPATFLOW_CONNECTOR_SIMULATOR=1 \
SIMULATOR_REST_CERT=tests/connector-simulator/runtime/rest-ca.crt \
SIMULATOR_SFTP_KNOWN_HOSTS=tests/connector-simulator/runtime/known_hosts \
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
