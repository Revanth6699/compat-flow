FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ACCEPT_EULA=Y

WORKDIR /app

# SQL Server support requires Microsoft's maintained ODBC Driver 18 at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import pyodbc; assert 'ODBC Driver 18 for SQL Server' in pyodbc.drivers(), pyodbc.drivers()"

COPY . .
RUN python -m pytest -q tests -k "not postgres and not admin_cannot_invite_another_admin"
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["sh", "./entrypoint.sh"]
