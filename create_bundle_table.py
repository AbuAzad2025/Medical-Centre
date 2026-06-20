import os
for line in open('.env'):
    if not line or line.startswith('#'): continue
    if '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from sqlalchemy import text
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS product_bundles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            name_ar VARCHAR(100) NOT NULL,
            slug VARCHAR(50) UNIQUE NOT NULL,
            description_ar TEXT,
            monthly_price NUMERIC(12,2) DEFAULT 0 NOT NULL,
            yearly_price NUMERIC(12,2) DEFAULT 0 NOT NULL,
            setup_fee NUMERIC(12,2) DEFAULT 0 NOT NULL,
            currency VARCHAR(3) DEFAULT 'SAR' NOT NULL,
            modules TEXT NOT NULL,
            max_users INTEGER,
            max_patients INTEGER,
            storage_gb INTEGER,
            api_calls_per_month INTEGER,
            is_public BOOLEAN DEFAULT TRUE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            profile_code VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_product_bundles_slug ON product_bundles(slug);
        CREATE INDEX IF NOT EXISTS ix_product_bundles_profile_code ON product_bundles(profile_code);
    """))
    db.session.commit()
    print('product_bundles table created')