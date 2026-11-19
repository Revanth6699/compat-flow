#!/bin/bash
set -euo pipefail
: "${SIMULATOR_READER_PASSWORD:?SIMULATOR_READER_PASSWORD is required}"
: "${SIMULATOR_SA_PASSWORD:?SIMULATOR_SA_PASSWORD is required}"

for attempt in $(seq 1 30); do
  if /opt/mssql-tools/bin/sqlcmd -S sql-supplier -U sa -P "$SIMULATOR_SA_PASSWORD" -C -b -Q "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

/opt/mssql-tools/bin/sqlcmd -S sql-supplier -U sa -P "$SIMULATOR_SA_PASSWORD" -C -b \
  -Q "CREATE LOGIN compatflow_reader WITH PASSWORD = '$SIMULATOR_READER_PASSWORD';"
/opt/mssql-tools/bin/sqlcmd -S sql-supplier -U sa -P "$SIMULATOR_SA_PASSWORD" -C -b \
  -i /seed/init.sql
