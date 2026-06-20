"""
Phase 2: ProductBundle model + ResourceUsage extended columns.
Phase 3: Owner API backing tables.

Revision ID: phase_2_3_product_bundles
Revises: phase_0_tenant_isolation
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase_2_3_product_bundles'
down_revision = 'phase_0_tenant_isolation'
branch_labels = None
depends_on = None

# Module-level so downgrade() can access it too
_resource_columns = [
    ('total_users', sa.Integer, 0),
    ('total_patients', sa.Integer, 0),
    ('total_visits', sa.Integer, 0),
    ('total_prescriptions', sa.Integer, 0),
    ('total_lab_requests', sa.Integer, 0),
    ('total_radiology_requests', sa.Integer, 0),
    ('total_appointments', sa.Integer, 0),
    ('total_invoices', sa.Integer, 0),
]


def upgrade():
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. product_bundles table
    # ------------------------------------------------------------------
    op.create_table(
        'product_bundles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('name_ar', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('description_ar', sa.Text(), nullable=True),
        sa.Column('monthly_price', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('yearly_price', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('setup_fee', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('currency', sa.String(3), default='SAR', nullable=False),
        sa.Column('modules', sa.Text(), nullable=False),
        sa.Column('max_users', sa.Integer(), nullable=True),
        sa.Column('max_patients', sa.Integer(), nullable=True),
        sa.Column('storage_gb', sa.Integer(), nullable=True),
        sa.Column('api_calls_per_month', sa.Integer(), nullable=True),
        sa.Column('is_public', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('profile_code', sa.String(50), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # 2. Add extended columns to resource_usage (if not exist)
    # ------------------------------------------------------------------
    inspector = sa.inspect(conn)
    if 'resource_usage' in [t for (t,) in conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).fetchall()] or \
       'resource_usage' in [r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='resource_usage'")).fetchall()]:
        ru_columns = [c['name'] for c in inspector.get_columns('resource_usage')]
        for col_name, col_type, col_default in _resource_columns:
            if col_name not in ru_columns:
                op.add_column('resource_usage',
                    sa.Column(col_name, col_type(), default=col_default, nullable=False, server_default=str(col_default))
                )
    else:
        # Create resource_usage table if it doesn't exist
        op.create_table(
            'resource_usage',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('recorded_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('db_size_mb', sa.Numeric(12, 2), default=0, nullable=False),
            sa.Column('storage_mb', sa.Numeric(12, 2), default=0, nullable=False),
            sa.Column('api_calls_24h', sa.Integer(), default=0, nullable=False),
            sa.Column('active_users_24h', sa.Integer(), default=0, nullable=False),
        )
        for col_name, col_type, col_default in _resource_columns:
            op.add_column('resource_usage',
                sa.Column(col_name, col_type(), default=col_default, nullable=False, server_default=str(col_default))
            )

    # ------------------------------------------------------------------
    # 3. Seed default ProductBundles (matching seed_default_bundles())
    # ------------------------------------------------------------------
    existing = conn.execute(sa.text("SELECT slug FROM product_bundles")).fetchall()
    existing_slugs = {row[0] for row in existing}

    bundles_data = [
        {"slug": "private_doctor_clinic", "name": "Private Doctor Clinic", "name_ar": "عيادة طبيب خاص",
         "description_ar": "منصة مخصصة للطبيب المنفرد", "monthly_price": 299, "yearly_price": 2999,
         "setup_fee": 0, "modules": '["doctor", "appointments"]', "max_users": 3, "max_patients": 500,
         "storage_gb": 5, "api_calls_per_month": 10000, "profile_code": "private_doctor_clinic"},
        {"slug": "small_clinic", "name": "Small Clinic", "name_ar": "عيادة صغيرة",
         "description_ar": "استقبال + طبيب + فوترة + مواعيد", "monthly_price": 799, "yearly_price": 7999,
         "setup_fee": 500, "modules": '["reception", "doctor", "billing", "appointments"]',
         "max_users": 10, "max_patients": 2000, "storage_gb": 20, "api_calls_per_month": 50000,
         "profile_code": "small_clinic"},
        {"slug": "standalone_lab", "name": "Standalone Lab", "name_ar": "مختبر مستقل",
         "description_ar": "إدارة التحاليل والتقارير والجودة", "monthly_price": 599, "yearly_price": 5999,
         "setup_fee": 300, "modules": '["lab", "billing", "reporting"]', "max_users": 5, "max_patients": 1000,
         "storage_gb": 10, "api_calls_per_month": 20000, "profile_code": "standalone_lab"},
        {"slug": "standalone_radiology", "name": "Standalone Radiology", "name_ar": "أشعة مستقلة",
         "description_ar": "طلبات الأشعة والتقارير والصور", "monthly_price": 799, "yearly_price": 7999,
         "setup_fee": 500, "modules": '["radiology", "billing", "reporting"]', "max_users": 5, "max_patients": 1000,
         "storage_gb": 50, "api_calls_per_month": 20000, "profile_code": "standalone_radiology"},
        {"slug": "standalone_pharmacy", "name": "Standalone Pharmacy", "name_ar": "صيدلية مستقلة",
         "description_ar": "إدارة الأدوية والمخزون والصرف", "monthly_price": 499, "yearly_price": 4999,
         "setup_fee": 300, "modules": '["pharmacy", "inventory", "billing"]', "max_users": 5, "max_patients": 1000,
         "storage_gb": 10, "api_calls_per_month": 30000, "profile_code": "standalone_pharmacy"},
        {"slug": "multi_department_center", "name": "Multi-Department Medical Center", "name_ar": "مركز طبي متعدد الأقسام",
         "description_ar": "منصة طبية متكاملة بجميع الأقسام", "monthly_price": 2499, "yearly_price": 24999,
         "setup_fee": 2000, "modules": '["reception", "doctor", "nursing", "billing", "appointments", "queue", "lab", "radiology", "pharmacy", "emergency", "reporting", "inventory"]',
         "max_users": 50, "max_patients": 10000, "storage_gb": 100, "api_calls_per_month": 200000,
         "profile_code": "multi_department_center"},
        {"slug": "custom", "name": "Custom Bundle", "name_ar": "حزمة مخصصة",
         "description_ar": "اختر الموديولز التي تناسبك", "monthly_price": 0, "yearly_price": 0,
         "setup_fee": 0, "modules": '[]', "max_users": None, "max_patients": None,
         "storage_gb": None, "api_calls_per_month": None, "profile_code": "custom"},
    ]

    for bd in bundles_data:
        if bd["slug"] not in existing_slugs:
            conn.execute(
                sa.text("""
                    INSERT INTO product_bundles
                        (slug, name, name_ar, description_ar,
                         monthly_price, yearly_price, setup_fee, currency,
                         modules, max_users, max_patients, storage_gb, api_calls_per_month, profile_code,
                         is_public, is_active, created_at, updated_at)
                    VALUES
                        (:slug, :name, :name_ar, :description_ar,
                         :monthly_price, :yearly_price, :setup_fee, 'SAR',
                         :modules, :max_users, :max_patients, :storage_gb, :api_calls_per_month, :profile_code,
                         True, True, NOW(), NOW())
                """),
                bd
            )


def downgrade():
    op.drop_table('product_bundles')
    for col_name, _, _ in _resource_columns:
        try:
            op.drop_column('resource_usage', col_name)
        except Exception:
            pass
