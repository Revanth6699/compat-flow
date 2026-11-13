from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.core.auth import AuthenticatedUser, SupabaseIdentity, get_current_user
from app.core.database import get_db
from app.main import app


class FakeResult:
    def all(self):
        return []


class FakeDB:
    def __init__(self, permission_granted=True):
        self.permission_granted = permission_granted
        self.scalar_calls = 0
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return "permission-row" if self.permission_granted else None
        return None

    def scalars(self, statement):
        self.statements.append(statement)
        return FakeResult()


def install_auth_overrides(organization_id, role, db):
    profile = SimpleNamespace(
        id=uuid4(),
        organization_id=organization_id,
        email="member@example.com",
        role=role,
        is_active=True,
    )
    identity = SupabaseIdentity(
        auth_user_id=uuid4(),
        email="member@example.com",
        access_token="test-token",
    )
    current = AuthenticatedUser(identity=identity, profile=profile)
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: db
    return current


def clear_overrides():
    app.dependency_overrides.clear()


def test_catalog_and_supplier_endpoints_reject_anonymous_requests():
    client = TestClient(app)
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/suppliers").status_code == 401
    assert client.post("/api/v1/products", json={
        "sku": "SKU-1",
        "name": "Part",
        "manufacturer": "Maker",
        "part_number": "P-1",
        "category": "Parts",
    }).status_code == 401
    assert client.post("/api/v1/suppliers", json={
        "name": "Supplier",
        "feed_format": "csv",
    }).status_code == 401


def test_viewer_without_write_grant_cannot_create_products():
    organization_id = uuid4()
    db = FakeDB(permission_granted=False)
    install_auth_overrides(organization_id, "viewer", db)
    try:
        response = TestClient(app).post("/api/v1/products", json={
            "sku": "SKU-1",
            "name": "Part",
            "manufacturer": "Maker",
            "part_number": "P-1",
            "category": "Parts",
        })
        assert response.status_code == 403
    finally:
        clear_overrides()


def test_catalog_read_query_is_scoped_to_authenticated_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get("/api/v1/products")
        assert response.status_code == 200
        statement = db.statements[-1]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "products.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_direct_product_lookup_cannot_cross_organization_boundary():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get(
            "/api/v1/products/00000000-0000-0000-0000-000000000099"
        )
        assert response.status_code == 404
        statement = db.statements[-1]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "products.organization_id" in str(compiled)
    finally:
        clear_overrides()



def test_supplier_read_query_is_scoped_to_authenticated_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get("/api/v1/suppliers")
        assert response.status_code == 200
        statement = db.statements[-1]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "suppliers.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_product_cannot_attach_supplier_from_another_organization():
    organization_id = uuid4()
    foreign_supplier_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).post("/api/v1/products", json={
            "sku": "SKU-FOREIGN",
            "name": "Part",
            "manufacturer": "Maker",
            "part_number": "P-1",
            "category": "Parts",
            "supplier_id": str(foreign_supplier_id),
        })
        assert response.status_code == 404
        supplier_query = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in supplier_query.params.values()
        assert "suppliers.organization_id" in str(supplier_query)
    finally:
        clear_overrides()
