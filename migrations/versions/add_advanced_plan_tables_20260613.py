"""Add advanced plan tables: medication_schedules, care_plan_tasks, data_warehouse_syncs, dicom_instances, population_health_indicators

Revision ID: 20260613_030000
Revises: add_visit_tax_triage_columns
Create Date: 2026-06-13 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260613_030000'
down_revision = 'add_visit_tax_triage_columns'
branch_labels = None
depends_on = None


def upgrade():
    # medication_schedules (eMAR)
    op.create_table(
        'medication_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prescription_item_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_time', sa.Time(), nullable=False),
        sa.Column('dose', sa.String(100), nullable=True),
        sa.Column('frequency', sa.String(50), nullable=True),
        sa.Column('window_before', sa.Integer(), server_default='30', nullable=False),
        sa.Column('window_after', sa.Integer(), server_default='60', nullable=False),
        sa.Column('is_prn', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('prn_reason', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['prescription_item_id'], ['prescription_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_medication_schedule_prescription_item', 'medication_schedules', ['prescription_item_id'])
    op.create_index('idx_medication_schedule_active', 'medication_schedules', ['is_active'])

    # care_plan_tasks
    op.create_table(
        'care_plan_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('care_plan_id', sa.Integer(), nullable=False),
        sa.Column('task_title', sa.String(300), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(30), server_default='PENDING', nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('completed_by_id', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['care_plan_id'], ['patient_care_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['completed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_care_plan_task_plan', 'care_plan_tasks', ['care_plan_id'])
    op.create_index('idx_care_plan_task_status', 'care_plan_tasks', ['status'])
    op.create_index('idx_care_plan_task_assigned', 'care_plan_tasks', ['assigned_to_id'])

    # data_warehouse_syncs
    op.create_table(
        'data_warehouse_syncs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('source_rows', sa.Integer(), nullable=True),
        sa.Column('target_rows', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_dw_sync_name', 'data_warehouse_syncs', ['sync_name'])
    op.create_index('idx_dw_sync_status', 'data_warehouse_syncs', ['status'])

    # dicom_instances
    op.create_table(
        'dicom_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('series_id', sa.Integer(), nullable=False),
        sa.Column('sop_instance_uid', sa.String(100), nullable=False),
        sa.Column('instance_number', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('thumbnail_path', sa.String(500), nullable=True),
        sa.Column('file_size_kb', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['series_id'], ['dicom_series.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sop_instance_uid')
    )
    op.create_index('idx_dicom_instance_series', 'dicom_instances', ['series_id'])
    op.create_index('idx_dicom_instance_uid', 'dicom_instances', ['sop_instance_uid'])

    # population_health_indicators
    op.create_table(
        'population_health_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('indicator_name', sa.String(200), nullable=False),
        sa.Column('indicator_type', sa.String(50), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('value', sa.Numeric(15, 4), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('numerator', sa.Integer(), nullable=True),
        sa.Column('denominator', sa.Integer(), nullable=True),
        sa.Column('district', sa.String(200), nullable=True),
        sa.Column('gender_breakdown', sa.Text(), nullable=True),
        sa.Column('age_breakdown', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_pop_health_name', 'population_health_indicators', ['indicator_name'])
    op.create_index('idx_pop_health_type', 'population_health_indicators', ['indicator_type'])
    op.create_index('idx_pop_health_period', 'population_health_indicators', ['period_start', 'period_end'])


def downgrade():
    op.drop_index('idx_pop_health_period', table_name='population_health_indicators')
    op.drop_index('idx_pop_health_type', table_name='population_health_indicators')
    op.drop_index('idx_pop_health_name', table_name='population_health_indicators')
    op.drop_table('population_health_indicators')

    op.drop_index('idx_dicom_instance_uid', table_name='dicom_instances')
    op.drop_index('idx_dicom_instance_series', table_name='dicom_instances')
    op.drop_table('dicom_instances')

    op.drop_index('idx_dw_sync_status', table_name='data_warehouse_syncs')
    op.drop_index('idx_dw_sync_name', table_name='data_warehouse_syncs')
    op.drop_table('data_warehouse_syncs')

    op.drop_index('idx_care_plan_task_assigned', table_name='care_plan_tasks')
    op.drop_index('idx_care_plan_task_status', table_name='care_plan_tasks')
    op.drop_index('idx_care_plan_task_plan', table_name='care_plan_tasks')
    op.drop_table('care_plan_tasks')

    op.drop_index('idx_medication_schedule_active', table_name='medication_schedules')
    op.drop_index('idx_medication_schedule_prescription_item', table_name='medication_schedules')
    op.drop_table('medication_schedules')
