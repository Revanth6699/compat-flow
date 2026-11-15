# Disposable supplier connector simulators

These services are for local development and CI only. They use synthetic records
and intentionally weak, fixed credentials. Never deploy this Compose stack to
a public or production network and never reuse its credentials for a real supplier.

## Start

From the repository root:

```bash
docker compose -f backend/tests/connector-simulator/compose.yaml up -d --wait
mkdir -p backend/tests/connector-simulator/runtime
docker compose -f backend/tests/connector-simulator/compose.yaml cp rest-supplier:/run/tls/server.crt backend/tests/connector-simulator/runtime/rest-ca.crt
ssh-keyscan -p 2222 localhost > backend/tests/connector-simulator/runtime/known_hosts
```

Endpoints:
- REST: `https://localhost:8443/catalog?page=1`; header `X-API-Key: local-test-key`.
- SFTP: `localhost:2222`, user `supplier`, password `Supplier-ReadOnly-2026!`, file `/upload/catalog.csv`.
- SQL Server: `localhost:14333`, database `CompatFlowSupplier`. The seeded read-only SQL login is `compatflow_reader`; use Microsoft ODBC Driver 18, encryption enabled, and certificate validation enabled.

The SQL Server container is provided with a synthetic database. The checked-in SQL
login is SELECT-only. The connector's SQL Server integration test runs only when
`SIMULATOR_SQLSERVER_URL` points to a SQL Server instance whose TLS certificate
is trusted by the test runner. The default SQL Server container uses its own
development certificate, so do not set `TrustServerCertificate=yes` merely to
force the test through: that would bypass a production security requirement.
Configure a trusted test certificate before enabling that assertion.

## Run protocol tests

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
