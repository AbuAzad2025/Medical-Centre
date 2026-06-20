import os
for line in open('.env'):
    if not line or line.startswith('#'): continue
    if '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())
os.environ['ENABLE_SAAS_MODE'] = 'true'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from sqlalchemy import text
    db.session.execute(text("DELETE FROM tenants WHERE slug IN ('tenant_b','tenantb')"))
    db.session.commit()
    print('cleaned up bad tenants')
