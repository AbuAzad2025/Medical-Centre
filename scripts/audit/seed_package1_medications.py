"""Seed a small medication catalogue for the package-1 clinic prescription flow."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from app.core.tenant.models import Tenant
from app.extensions import db
from models.medication import Medication
from seeds import tenant_bypass
from wsgi import app

MEDS = [
    ('Paracetamol', 'باراسيتامول', 'Paracetamol', 'tablet', '500mg', 'painkiller', 2.5),
    ('Ibuprofen', 'إيبوبروفين', 'Ibuprofen', 'tablet', '400mg', 'painkiller', 4.0),
    ('Pseudoephedrine', 'سودوإيفيدرين', 'Pseudoephedrine', 'tablet', '60mg', 'decongestant', 3.5),
]

with app.app_context():
    tenant = db.session.execute(select(Tenant).filter_by(slug='dr-ahmed-clinic')).scalar_one()
    with tenant_bypass(tenant):
        existing = {
            m.trade_name
            for m in db.session.execute(select(Medication).filter_by(tenant_id=tenant.id)).scalars()
        }
        for trade, trade_ar, generic, form, strength, category, price in MEDS:
            label = f'{trade_ar} ({trade})'
            if label in existing or trade in existing:
                continue
            db.session.add(
                Medication(
                    tenant_id=tenant.id,
                    scientific_name=generic,
                    trade_name=label,
                    generic_name=generic,
                    dosage_form=form,
                    strength=strength,
                    price=price,
                    category=category,
                    stock_quantity=100,
                    is_active=True,
                )
            )
        db.session.commit()
        meds = (
            db.session.execute(select(Medication).filter_by(tenant_id=tenant.id, is_active=True))
            .scalars()
            .all()
        )
        for m in meds:
            print(m.id, m.trade_name, m.strength, m.dosage_form)
