"""Add specialty forms tables

Revision ID: dfdad7fc3407
Revises: f0ca021c3e4f
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dfdad7fc3407'
down_revision = 'f0ca021c3e4f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('specialty_forms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('specialty', sa.String(length=80), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('latest_published_version_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_specialty_form_tenant_slug')
    )
    with op.batch_alter_table('specialty_forms', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_specialty_forms_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('specialty_form_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('form_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('published_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['form_id'], ['specialty_forms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['published_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('form_id', 'version_number', name='uq_specialty_form_version')
    )
    with op.batch_alter_table('specialty_form_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_specialty_form_versions_form_id'), ['form_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_specialty_form_versions_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('specialty_form_fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('field_type', sa.String(length=40), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('default_value', sa.Text(), nullable=True),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_id'], ['specialty_form_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id', 'name', name='uq_specialty_form_field_name')
    )
    with op.batch_alter_table('specialty_form_fields', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_specialty_form_fields_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_specialty_form_fields_version_id'), ['version_id'], unique=False)

    with op.batch_alter_table('specialty_forms', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_specialty_forms_latest_version', 'specialty_form_versions', ['latest_published_version_id'], ['id'], ondelete='SET NULL')

    op.create_table('specialty_form_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=True),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('submitted_by', sa.Integer(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_id'], ['specialty_form_versions.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('specialty_form_submissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_specialty_form_submissions_patient_id'), ['patient_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_specialty_form_submissions_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_specialty_form_submissions_version_id'), ['version_id'], unique=False)


def downgrade():
    with op.batch_alter_table('specialty_forms', schema=None) as batch_op:
        batch_op.drop_constraint('fk_specialty_forms_latest_version', type_='foreignkey')
    op.drop_table('specialty_form_submissions')
    op.drop_table('specialty_form_fields')
    op.drop_table('specialty_form_versions')
    op.drop_table('specialty_forms')
