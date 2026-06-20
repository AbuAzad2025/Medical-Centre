"""
Fix StaffWorkSchedule records with NULL tenant_id

This migration ensures that all existing StaffWorkSchedule records have a valid tenant_id.
It assigns the tenant_id from the associated User record.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from app_factory import create_app

# Create a connection to the database
connection = op.get_bind()
Session = sessionmaker(bind=connection)
session = Session()

def get_user_tenant_map():
    """Get mapping of user_id to tenant_id from User table."""
    from models.user import User
    user_tenant_map = {}
    for user in session.query(User.id, User.tenant_id).all():
        user_tenant_map[user.id] = user.tenant_id
    return user_tenant_map

def fix_staff_work_schedule_tenant_ids():
    """Update StaffWorkSchedule records with NULL tenant_id."""
    from models.user import StaffWorkSchedule
    
    # Get user tenant mapping
    user_tenant_map = get_user_tenant_map()
    
    # Find all StaffWorkSchedule records with NULL tenant_id
    records = session.query(StaffWorkSchedule).filter(
        StaffWorkSchedule.tenant_id.is_(None)
    ).all()
    
    if not records:
        print("No StaffWorkSchedule records with NULL tenant_id found.")
        return 0
    
    updated_count = 0
    for record in records:
        user_id = record.user_id
        if user_id in user_tenant_map:
            record.tenant_id = user_tenant_map[user_id]
            updated_count += 1
    
    if updated_count > 0:
        session.commit()
        print(f"Updated {updated_count} StaffWorkSchedule records with tenant_id.")
    
    return updated_count

def upgrade():
    """Apply the migration."""
    print("Starting StaffWorkSchedule tenant_id fix migration...")
    
    # First, ensure the StaffWorkSchedule table has the tenant_id column
    # (it should already have it from phase_2_5)
    
    # Fix the records
    updated = fix_staff_work_schedule_tenant_ids()
    
    if updated == 0:
        print("No updates needed - all records already have tenant_id.")
    else:
        print(f"Migration completed: {updated} records updated.")


def downgrade():
    """Revert the migration (not recommended for production)."""
    print("Downgrade not supported for this migration.")
    print("To revert, manually set tenant_id back to NULL for affected records.")