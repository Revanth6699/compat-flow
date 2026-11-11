from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Organization, Supplier


DEV_ORGANIZATION_NAME = "CompatFlow Development"
DEV_SUPPLIER_NAME = "Development Supplier"


def seed_development_tenant(db: Session) -> tuple[Organization, Supplier]:
    if settings.app_env.lower() != "development":
        raise RuntimeError(
            "Development tenant seeding is only allowed in development mode."
        )

    organization = db.scalar(
        select(Organization).where(
            Organization.name == DEV_ORGANIZATION_NAME
        )
    )

    if organization is None:
        organization = Organization(name=DEV_ORGANIZATION_NAME)
        db.add(organization)
        db.flush()

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.organization_id == organization.id,
            Supplier.name == DEV_SUPPLIER_NAME,
        )
    )

    if supplier is None:
        supplier = Supplier(
            organization_id=organization.id,
            name=DEV_SUPPLIER_NAME,
            feed_format="csv",
        )
        db.add(supplier)
        db.flush()

    db.commit()
    db.refresh(organization)
    db.refresh(supplier)

    return organization, supplier


def main() -> None:
    db = SessionLocal()
    try:
        organization, supplier = seed_development_tenant(db)
        print(f"Organization: {organization.id} | {organization.name}")
        print(f"Supplier: {supplier.id} | {supplier.name}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
