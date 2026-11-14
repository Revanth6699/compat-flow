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
        self.subscription = SimpleNamespace(
            id=uuid4(), plan_code="growth", status="active",
            current_period_end=None, created_at=None,
        )
        self.plan = SimpleNamespace(
            code="growth", is_active=True,
            entitlements={"supplier_catalogs": True},
        )

    def scalar(self, statement):
        self.statements.append(statement)
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return "permission-row" if self.permission_granted else None
        if self.scalar_calls == 2:
            return self.subscription
        return None

    def get(self, model, key):
        return self.plan

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
        "sku": "SKU-1", "name": "Part", "manufacturer": "Maker",
        "part_number": "P-1", "category": "Parts",
    }).status_code == 401
    assert client.post("/api/v1/suppliers", json={
        "name": "Supplier", "feed_format": "csv",
    }).status_code == 401


def test_viewer_without_write_grant_cannot_create_products():
    organization_id = uuid4()
    db = FakeDB(permission_granted=False)
    install_auth_overrides(organization_id, "viewer", db)
    try:
        response = TestClient(app).post("/api/v1/products", json={
            "sku": "SKU-1", "name": "Part", "manufacturer": "Maker",
            "part_number": "P-1", "category": "Parts",
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
        response = TestClient(app).get("/api/v1/products/00000000-0000-0000-0000-000000000099")
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
            "sku": "SKU-FOREIGN", "name": "Part", "manufacturer": "Maker",
            "part_number": "P-1", "category": "Parts",
            "supplier_id": str(foreign_supplier_id),
        })
        assert response.status_code == 404
        supplier_query = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in supplier_query.params.values()
        assert "suppliers.organization_id" in str(supplier_query)
    finally:
        clear_overrides()



def test_new_catalog_record_endpoints_require_authentication():
    client = TestClient(app)
    for path in ("/api/v1/product-variants", "/api/v1/supplier-offers", "/api/v1/inventory-snapshots", "/api/v1/product-identifiers"):
        assert client.get(path).status_code == 401


def test_product_variant_read_is_scoped_to_authenticated_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get("/api/v1/product-variants")
        assert response.status_code == 200
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "product_variants.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_supplier_offer_read_is_scoped_to_authenticated_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get("/api/v1/supplier-offers")
        assert response.status_code == 200
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "supplier_offers.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_inventory_snapshot_read_is_scoped_to_authenticated_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get("/api/v1/inventory-snapshots")
        assert response.status_code == 200
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "inventory_snapshots.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_variant_cannot_reference_product_from_another_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).post("/api/v1/product-variants", json={
            "product_id": str(uuid4()),
            "variant_sku": "VAR-1",
            "attributes": {"color": "blue", "size": "M"},
        })
        assert response.status_code == 404
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "products.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_supplier_offer_cannot_reference_supplier_from_another_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).post("/api/v1/supplier-offers", json={
            "supplier_id": str(uuid4()),
            "supplier_sku": "SUP-1",
            "unit_price": "12.50",
            "currency": "USD",
        })
        assert response.status_code == 404
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "suppliers.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_inventory_snapshot_cannot_reference_product_from_another_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).post("/api/v1/inventory-snapshots", json={
            "product_id": str(uuid4()),
            "warehouse_code": "WH-01",
            "quantity_on_hand": "10",
            "quantity_reserved": "2",
            "quantity_available": "8",
        })
        assert response.status_code == 404
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "products.organization_id" in str(compiled)
    finally:
        clear_overrides()



def test_product_identifier_read_is_scoped_to_authenticated_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).get("/api/v1/product-identifiers")
        assert response.status_code == 200
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "product_identifiers.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_product_identifier_cannot_reference_product_from_another_organization():
    organization_id = uuid4()
    db = FakeDB(permission_granted=True)
    install_auth_overrides(organization_id, "member", db)
    try:
        response = TestClient(app).post("/api/v1/product-identifiers", json={
            "product_id": str(uuid4()),
            "identifier_type": "gtin",
            "namespace": "global",
            "value": "00012345678905",
        })
        assert response.status_code == 404
        compiled = db.statements[-1].compile(dialect=postgresql.dialect())
        assert organization_id in compiled.params.values()
        assert "products.organization_id" in str(compiled)
    finally:
        clear_overrides()


def test_postgres_enforces_live_tenant_isolation_and_viewer_permissions():
    """Exercise real PostgreSQL rows through the API, not only compiled SQL."""
    from app.core.database import SessionLocal
    from app.models import Organization, Product, Subscription, SubscriptionPlan, User

    db = SessionLocal()
    organization_a = Organization(name=f"Tenant A {uuid4().hex[:8]}")
    organization_b = Organization(name=f"Tenant B {uuid4().hex[:8]}")
    plan_code = f"tenant_test_{uuid4().hex[:12]}"
    owner = User(
        organization_id=organization_a.id,
        auth_user_id=uuid4(),
        email=f"tenant-owner-{uuid4().hex[:8]}@example.test",
        role="member",
        is_active=True,
        account_type="subscriber",
    )
    plan = SubscriptionPlan(
        code=plan_code,
        name=f"Tenant test plan {uuid4().hex[:8]}",
        currency="USD",
        is_active=True,
        entitlements={"supplier_catalogs": True},
    )
    product_a = Product(
        organization_id=organization_a.id,
        sku=f"A-{uuid4().hex[:8]}",
        name="Tenant A product",
        manufacturer="Maker A",
        part_number="A-100",
        category="Test",
    )
    product_b = Product(
        organization_id=organization_b.id,
        sku=f"B-{uuid4().hex[:8]}",
        name="Tenant B product",
        manufacturer="Maker B",
        part_number="B-100",
        category="Test",
    )
    try:
        db.add_all([organization_a, organization_b, plan])
        db.flush()
        owner.organization_id = organization_a.id
        product_a.organization_id = organization_a.id
        product_b.organization_id = organization_b.id
        db.add_all([owner, product_a, product_b])
        db.flush()
        db.add(Subscription(
            organization_id=organization_a.id,
            user_id=owner.id,
            plan_code=plan_code,
            status="active",
            billing_interval="month",
        ))
        db.commit()

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            identity=SupabaseIdentity(owner.auth_user_id, owner.email, "integration-test-token"),
            profile=owner,
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)

        listed = client.get("/api/v1/products")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [str(product_a.id)]
        assert listed.json()[0]["sku"] == product_a.sku

        foreign_lookup = client.get(f"/api/v1/products/{product_b.id}")
        assert foreign_lookup.status_code == 404

        viewer = User(
            organization_id=organization_a.id,
            auth_user_id=uuid4(),
            email=f"tenant-viewer-{uuid4().hex[:8]}@example.test",
            role="viewer",
            is_active=True,
            account_type="subscriber",
        )
        db.add(viewer)
        db.commit()
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            identity=SupabaseIdentity(viewer.auth_user_id, viewer.email, "integration-test-token"),
            profile=viewer,
        )

        viewer_read = client.get("/api/v1/products")
        assert viewer_read.status_code == 200
        assert [row["id"] for row in viewer_read.json()] == [str(product_a.id)]
        viewer_write = client.post("/api/v1/products", json={
            "sku": f"DENIED-{uuid4().hex[:8]}",
            "name": "Should not be created",
            "manufacturer": "Maker",
            "part_number": "DENIED-1",
            "category": "Test",
        })
        assert viewer_write.status_code == 403
    finally:
        clear_overrides()
        try:
            db.rollback()
            db.delete(organization_a)
            db.delete(organization_b)
            db.delete(plan)
            db.commit()
        finally:
            db.close()



def test_postgres_enforces_tenant_isolation_for_all_catalog_record_types():
    """Verify every catalog collection and cross-tenant reference against PostgreSQL."""
    from decimal import Decimal

    from app.core.database import SessionLocal
    from app.models import (
        InventorySnapshot,
        Organization,
        Product,
        ProductIdentifier,
        ProductVariant,
        Subscription,
        SubscriptionPlan,
        Supplier,
        SupplierOffer,
        User,
    )

    db = SessionLocal()
    organization_a = Organization(name=f"Catalog tenant A {uuid4().hex[:8]}")
    organization_b = Organization(name=f"Catalog tenant B {uuid4().hex[:8]}")
    plan_code = f"catalog_test_{uuid4().hex[:12]}"
    plan = SubscriptionPlan(
        code=plan_code,
        name=f"Catalog test plan {uuid4().hex[:8]}",
        currency="USD",
        is_active=True,
        entitlements={"supplier_catalogs": True},
    )
    try:
        db.add_all([organization_a, organization_b, plan])
        db.flush()

        owner = User(
            organization_id=organization_a.id,
            auth_user_id=uuid4(),
            email=f"catalog-owner-{uuid4().hex[:8]}@example.test",
            role="member",
            is_active=True,
            account_type="subscriber",
        )
        db.add(owner)
        db.flush()

        supplier_a = Supplier(
            organization_id=organization_a.id,
            name=f"Tenant A supplier {uuid4().hex[:6]}",
            feed_format="csv",
        )
        supplier_b = Supplier(
            organization_id=organization_b.id,
            name=f"Tenant B supplier {uuid4().hex[:6]}",
            feed_format="csv",
        )
        db.add_all([supplier_a, supplier_b])
        db.flush()

        product_a = Product(
            organization_id=organization_a.id,
            supplier_id=supplier_a.id,
            sku=f"CAT-A-{uuid4().hex[:8]}",
            name="Tenant A catalog product",
            manufacturer="Maker A",
            part_number="A-200",
            category="Test",
        )
        product_b = Product(
            organization_id=organization_b.id,
            supplier_id=supplier_b.id,
            sku=f"CAT-B-{uuid4().hex[:8]}",
            name="Tenant B catalog product",
            manufacturer="Maker B",
            part_number="B-200",
            category="Test",
        )
        db.add_all([product_a, product_b])
        db.flush()

        variant_a = ProductVariant(
            organization_id=organization_a.id,
            product_id=product_a.id,
            variant_sku=f"VAR-A-{uuid4().hex[:6]}",
            attributes={"color": "blue"},
        )
        variant_b = ProductVariant(
            organization_id=organization_b.id,
            product_id=product_b.id,
            variant_sku=f"VAR-B-{uuid4().hex[:6]}",
            attributes={"color": "red"},
        )
        offer_a = SupplierOffer(
            organization_id=organization_a.id,
            supplier_id=supplier_a.id,
            product_id=product_a.id,
            supplier_sku=f"OFFER-A-{uuid4().hex[:6]}",
            unit_price=Decimal("12.5000"),
            currency="USD",
        )
        offer_b = SupplierOffer(
            organization_id=organization_b.id,
            supplier_id=supplier_b.id,
            product_id=product_b.id,
            supplier_sku=f"OFFER-B-{uuid4().hex[:6]}",
            unit_price=Decimal("15.0000"),
            currency="USD",
        )
        identifier_a = ProductIdentifier(
            organization_id=organization_a.id,
            product_id=product_a.id,
            identifier_type="gtin",
            namespace="global",
            value=f"000{uuid4().int % 10**11:011d}",
        )
        identifier_b = ProductIdentifier(
            organization_id=organization_b.id,
            product_id=product_b.id,
            identifier_type="gtin",
            namespace="global",
            value=f"000{uuid4().int % 10**11:011d}",
        )
        db.add_all([
            variant_a, variant_b, offer_a, offer_b, identifier_a, identifier_b,
        ])
        db.flush()

        snapshot_a = InventorySnapshot(
            organization_id=organization_a.id,
            product_id=product_a.id,
            supplier_offer_id=offer_a.id,
            warehouse_code="A-WH",
            quantity_on_hand=Decimal("20"),
            quantity_reserved=Decimal("2"),
            quantity_available=Decimal("18"),
        )
        snapshot_b = InventorySnapshot(
            organization_id=organization_b.id,
            product_id=product_b.id,
            supplier_offer_id=offer_b.id,
            warehouse_code="B-WH",
            quantity_on_hand=Decimal("30"),
            quantity_reserved=Decimal("3"),
            quantity_available=Decimal("27"),
        )
        db.add_all([snapshot_a, snapshot_b, owner])
        db.flush()
        db.add(Subscription(
            organization_id=organization_a.id,
            user_id=owner.id,
            plan_code=plan_code,
            status="active",
            billing_interval="month",
        ))
        db.commit()

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            identity=SupabaseIdentity(owner.auth_user_id, owner.email, "catalog-integration-token"),
            profile=owner,
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)

        collection_expectations = (
            ("/api/v1/product-variants", variant_a.id, variant_b.id),
            ("/api/v1/supplier-offers", offer_a.id, offer_b.id),
            ("/api/v1/inventory-snapshots", snapshot_a.id, snapshot_b.id),
            ("/api/v1/product-identifiers", identifier_a.id, identifier_b.id),
        )
        for path, own_id, foreign_id in collection_expectations:
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
            returned_ids = {row["id"] for row in response.json()}
            assert returned_ids == {str(own_id)}, (path, returned_ids)
            assert str(foreign_id) not in returned_ids

        foreign_variant = client.post("/api/v1/product-variants", json={
            "product_id": str(product_b.id),
            "variant_sku": f"DENIED-VAR-{uuid4().hex[:6]}",
            "attributes": {"color": "black"},
        })
        assert foreign_variant.status_code == 404

        foreign_supplier_offer = client.post("/api/v1/supplier-offers", json={
            "supplier_id": str(supplier_b.id),
            "product_id": str(product_a.id),
            "supplier_sku": f"DENIED-OFFER-{uuid4().hex[:6]}",
            "unit_price": "9.99",
            "currency": "USD",
        })
        assert foreign_supplier_offer.status_code == 404

        foreign_product_offer = client.post("/api/v1/supplier-offers", json={
            "supplier_id": str(supplier_a.id),
            "product_id": str(product_b.id),
            "supplier_sku": f"DENIED-PRODUCT-{uuid4().hex[:6]}",
            "unit_price": "9.99",
            "currency": "USD",
        })
        assert foreign_product_offer.status_code == 404

        foreign_product_snapshot = client.post("/api/v1/inventory-snapshots", json={
            "product_id": str(product_b.id),
            "warehouse_code": "DENIED-WH",
            "quantity_on_hand": "1",
        })
        assert foreign_product_snapshot.status_code == 404

        foreign_offer_snapshot = client.post("/api/v1/inventory-snapshots", json={
            "product_id": str(product_a.id),
            "supplier_offer_id": str(offer_b.id),
            "warehouse_code": "DENIED-OFFER-WH",
            "quantity_on_hand": "1",
        })
        assert foreign_offer_snapshot.status_code == 404

        foreign_identifier = client.post("/api/v1/product-identifiers", json={
            "product_id": str(product_b.id),
            "identifier_type": "gtin",
            "namespace": "global",
            "value": f"999{uuid4().int % 10**11:011d}",
        })
        assert foreign_identifier.status_code == 404
    finally:
        clear_overrides()
        try:
            db.rollback()
            db.delete(organization_a)
            db.delete(organization_b)
            db.delete(plan)
            db.commit()
        finally:
            db.close()


def test_postgres_role_permission_matrix_for_catalog_read_and_write():
    """Verify seeded role grants against real PostgreSQL and the product API."""
    from app.core.database import SessionLocal
    from app.models import Organization, Product, Subscription, SubscriptionPlan, User

    db = SessionLocal()
    organization = Organization(name=f"Role matrix {uuid4().hex[:8]}")
    plan_code = f"role_test_{uuid4().hex[:12]}"
    plan = SubscriptionPlan(
        code=plan_code,
        name=f"Role matrix plan {uuid4().hex[:8]}",
        currency="USD",
        is_active=True,
        entitlements={"supplier_catalogs": True},
    )
    users = []
    try:
        db.add_all([organization, plan])
        db.flush()
        for role in ("owner", "admin", "member", "viewer"):
            user = User(
                organization_id=organization.id,
                auth_user_id=uuid4(),
                email=f"role-{role}-{uuid4().hex[:8]}@example.test",
                role=role,
                is_active=True,
                account_type="subscriber",
            )
            users.append(user)
        db.add_all(users)
        db.flush()
        db.add(Subscription(
            organization_id=organization.id,
            user_id=users[0].id,
            plan_code=plan_code,
            status="active",
            billing_interval="month",
        ))
        # Build detached-safe auth snapshots before commit expires ORM attributes.
        role_identities = [
            (
                user.role,
                SupabaseIdentity(user.auth_user_id, user.email, "role-matrix-token"),
                SimpleNamespace(
                    id=user.id,
                    organization_id=user.organization_id,
                    email=user.email,
                    role=user.role,
                    is_active=user.is_active,
                ),
            )
            for user in users
        ]
        db.commit()

        client = TestClient(app)
        for role, identity, profile in role_identities:
            app.dependency_overrides[get_current_user] = lambda identity=identity, profile=profile: AuthenticatedUser(
                identity=identity,
                profile=profile,
            )
            read_response = client.get("/api/v1/products")
            assert read_response.status_code == 200, (role, read_response.text)

            write_response = client.post("/api/v1/products", json={
                "sku": f"ROLE-{role.upper()}-{uuid4().hex[:8]}",
                "name": f"Created by {role}",
                "manufacturer": "CompatFlow test",
                "part_number": f"{role}-{uuid4().hex[:6]}",
                "category": "Security test",
            })
            expected_status = 403 if role == "viewer" else 201
            assert write_response.status_code == expected_status, (
                role, write_response.status_code, write_response.text
            )

        persisted_products = db.query(Product).filter(
            Product.organization_id == organization.id
        ).all()
        assert len(persisted_products) == 3
    finally:
        clear_overrides()
        try:
            db.rollback()
            db.delete(organization)
            db.delete(plan)
            db.commit()
        finally:
            db.close()
