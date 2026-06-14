import sys
import os
from app_factory import create_app, db
from models.branding import BrandingSettings
from models.user import User

app = create_app()

with app.app_context():
    # Find a system user to associate with
    admin = User.query.filter_by(role='super_admin').first()
    user_id = admin.id if admin else None
    
    branding = BrandingSettings.get_active_settings()
    if not branding:
        print("Creating new branding settings...")
        branding = BrandingSettings(
            organization_name='المركز الطبي المتطور',
            organization_name_en='Advanced Medical Center',
            organization_address='غزة، فلسطين',
            organization_phone='+970 59 123 4567',
            organization_email='info@med-center.com',
            organization_website='www.med-center.com',
            created_by=user_id,
            updated_by=user_id,
            is_active=True
        )
        db.session.add(branding)
    else:
        print("Updating existing branding settings...")
        branding.organization_name = 'المركز الطبي المتطور'
        branding.organization_name_en = 'Advanced Medical Center'
        branding.organization_address = 'غزة، فلسطين'
        branding.organization_phone = '+970 59 123 4567'
        branding.organization_email = 'info@med-center.com'
        branding.organization_website = 'www.med-center.com'
        branding.updated_by = user_id
    
    db.session.commit()
    print("Branding settings updated successfully!")
