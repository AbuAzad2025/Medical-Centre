"""Fix whatsapp phone_number column type to TEXT.

Revision ID: s5_001_whatsapp_phone_text
Revises: add_slug_to_roles_20261113

The model declares ``phone_number = EncryptedString(20)`` whose PostgreSQL
implementation is always TEXT (ciphertext is longer than the plaintext).  The
production baseline created the column as VARCHAR(20), so enabling field
encryption would fail to insert any phone number.  Align the database with the
model. Widening varchar -> text is a safe, metadata-only change in PostgreSQL.
"""

from alembic import op

revision = 's5_001_whatsapp_phone_text'
down_revision = 'add_slug_to_roles_20261113'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE whatsapp_integration_messages ALTER COLUMN phone_number TYPE TEXT')


def downgrade() -> None:
    op.execute(
        'ALTER TABLE whatsapp_integration_messages ALTER COLUMN phone_number TYPE VARCHAR(20)'
    )
