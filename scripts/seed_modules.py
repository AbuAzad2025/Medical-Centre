"""
Seed ModuleDefinition table from MODULE_REGISTRY
Usage: python scripts/seed_modules.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app, db
from app.core.module.registry import MODULE_REGISTRY
from app.core.module.models import ModuleDefinition


def seed():
    app = create_app()
    with app.app_context():
        existing = {m.name for m in ModuleDefinition.query.all()}
        created = 0
        for key, meta in MODULE_REGISTRY.items():
            if key in existing:
                continue
            md = ModuleDefinition(
                name=meta.name,
                name_ar=meta.name_ar,
                category=meta.category,
                description=meta.description_ar,
                is_active=True,
            )
            db.session.add(md)
            created += 1
        if created:
            db.session.commit()
            print(f"Seeded {created} module definitions.")
        else:
            print("All module definitions already present.")


if __name__ == "__main__":
    seed()
