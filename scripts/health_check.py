"""
Production health check script
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_db():
    from app_factory import db, create_app
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    with app.app_context():
        try:
            from sqlalchemy import text
            db.session.execute(text("SELECT 1"))
            print("[OK] Database connected")
            return True
        except Exception as e:
            print(f"[FAIL] Database: {e}")
            return False


def check_models():
    from app_factory import create_app
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    with app.app_context():
        try:
            from app.core.tenant.models import Tenant
            from app.core.module.models import ModuleDefinition, TenantModule
            from app.modules.workflows.stock_models import StockMovement
            count = Tenant.query.count()
            print(f"[OK] Models loaded (tenants={count})")
            return True
        except Exception as e:
            print(f"[FAIL] Models: {e}")
            return False


def check_blueprints():
    from app_factory import create_app
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    print(f"[OK] Blueprints={len(app.blueprints)}, Routes={len(list(app.url_map.iter_rules()))}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Azad Medical Platform Health Check")
    parser.add_argument('--strict', action='store_true', help='Exit with non-zero on any failure')
    args = parser.parse_args()

    results = []
    results.append(check_db())
    results.append(check_models())
    results.append(check_blueprints())

    if all(results):
        print("\n[PASS] All checks passed")
        sys.exit(0)
    else:
        print("\n[FAIL] Some checks failed")
        if args.strict:
            sys.exit(1)


if __name__ == '__main__':
    main()
