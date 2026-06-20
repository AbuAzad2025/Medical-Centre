#!/usr/bin/env python3
"""
Apply all pending migrations to the database.
This should be run before deploying to production.
"""
import os
import sys
from alembic.config import Config
from alembic import command
from app_factory import create_app

def main():
    # Set environment variables
    os.environ.setdefault('FLASK_ENV', 'production')
    
    # Create app
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    # Configure Alembic
    alembic_cfg = Config('migrations/alembic.ini')
    alembic_cfg.set_main_option('script_location', 'migrations')
    
    # Check current migration head
    print("Current migration status:")
    command.current(alembic_cfg)
    
    # Apply pending migrations
    print("\nApplying pending migrations...")
    command.upgrade(alembic_cfg, 'head')
    
    print("\nAll migrations applied successfully!")
    
    # Verify StaffWorkSchedule fix
    print("\nVerifying StaffWorkSchedule tenant_id fix...")
    from models.user import StaffWorkSchedule
    from app.extensions import db
    
    with app.app_context():
        null_tenant_count = StaffWorkSchedule.query.filter(
            StaffWorkSchedule.tenant_id.is_(None)
        ).count()
        
        if null_tenant_count == 0:
            print(f"✓ All {StaffWorkSchedule.query.count()} StaffWorkSchedule records have tenant_id")
        else:
            print(f"✗ {null_tenant_count} StaffWorkSchedule records still have NULL tenant_id")
            print("  Run the migration script manually: python migrations/versions/fix_staff_work_schedule_tenant_id.py")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)