# Supplier Connector Simulators

These containers provide local test endpoints for the REST, SFTP, and SQL Server connectors. They use synthetic records and disposable credentials.

**CI status:** Simulator integration tests are currently disabled and must remain out of normal CI runs. Keep the test setup in the repository for controlled future use; do not start the simulators or run these tests unless they are explicitly re-enabled.

Do not deploy this Compose stack to a public or production network. Never reuse simulator credentials for a real supplier.

## 1. Start the simulators

Run from the repository root.

```bash
export SIMULATOR_READER_PASSWORD="$(python -c 'import secrets,string; print("Aa7" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)))')"
export SIMULATOR_SA_PASSWORD="$(python -c 'import secrets,string; print("Aa7" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25)))')"

docker compose -f backend/tests/connector-simulator/compose.yaml up -d --wait rest-supplier sftp-supplier sql-supplier
docker compose -f backend/tests/connector-simulator/compose.yaml run --rm sql-init

mkdir -p backend/tests/connector-simulator/runtime

docker compose -f backend/tests/connector-simulator/compose.yaml cp rest-supplier:/run/tls/server.crt backend/tests/connector-simulator/runtime/rest-ca.crt
docker compose -f backend/tests/connector-simulator/compose.yaml cp sql-supplier:/tls/sql-ca.crt backend/tests/connector-simulator/runtime/sql-ca.crt
docker compose -f backend/tests/connector-simulator/compose.yaml cp sql-supplier:/tls/sql-server.crt backend/tests/connector-simulator/runtime/sql-server.crt

sudo cp backend/tests/connector-simulator/runtime/sql-ca.crt /usr/local/share/ca-certificates/compatflow-sql-simulator-ca.crt
sudo update-ca-certificates

export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ssh-keyscan -p 2222 localhost > backend/tests/connector-simulator/runtime/known_hosts
```

## 2. Local endpoints

| Connector | Endpoint | Test authentication |
|---|---|---|
| REST | `https://localhost:8443/catalog?page=1` | `X-API-Key: local-test-key` |
| SFTP | `localhost:2222`, user `supplier`, file `/upload/catalog.csv` | Disposable simulator password |
| SQL Server | `localhost:14333`, database `CompatFlowSupplier` | Read-only login `compatflow_reader`; password from `SIMULATOR_READER_PASSWORD` |

The SQL Server SA password is held separately in `SIMULATOR_SA_PASSWORD`. Do not commit either generated password.

## 3. TLS and SQL Server test boundary

The SQL initializer creates a synthetic product table and grants the connector login SELECT permission only.

A disposable local root CA signs a short-lived SQL Server leaf certificate whose SAN covers `localhost` and `sql-supplier`. The SQL Server container forces TLS 1.2. The test client trusts only the simulator root CA. The CA private key and certificates are generated per run and discarded with the Compose volume.

The CI test uses Microsoft ODBC Driver 18 with:
- `Encrypt=yes`
- `TrustServerCertificate=no`
- `HostNameInCertificate=sql-supplier`

The client trust bundle is set through `SSL_CERT_FILE`. Certificate validation is not bypassed. Do not replace this with `TrustServerCertificate=yes`.

Production supplier connections must validate the supplier's real CA chain and hostname. Never trust the simulator CA in production.

The seed step uses the SQL tools image's `-C` option only for initial synthetic database setup. The connector integration test validates the trusted server certificate and hostname.

## 4. Run protocol integration tests

Install Microsoft ODBC Driver 18 and backend requirements first.

```bash
cd backend

PYTHONPATH=. COMPATFLOW_CONNECTOR_SIMULATOR=1 \
SIMULATOR_REST_CERT=tests/connector-simulator/runtime/rest-ca.crt \
SIMULATOR_SFTP_KNOWN_HOSTS=tests/connector-simulator/runtime/known_hosts \
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
SIMULATOR_SQLSERVER_URL="mssql+pyodbc://compatflow_reader:${SIMULATOR_READER_PASSWORD}@localhost:14333/CompatFlowSupplier?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&HostNameInCertificate=sql-supplier" \
python -m pytest -q tests/test_connector_simulator_integration.py
```

## 5. Stop and remove simulator resources

```bash
docker compose -f backend/tests/connector-simulator/compose.yaml down -v
```

## 6. Test isolation notes

- The REST integration test bypasses DNS policy only for this disposable localhost target because the connector rejects private and loopback targets.
- The unit suite remains responsible for SSRF and host-allowlist rejection tests.
- SFTP uses a generated known-hosts file and rejects unknown host keys.
- Simulator success does not prove compatibility with a live supplier system.
