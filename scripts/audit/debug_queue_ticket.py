import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from app.core.tenant.models import Tenant
from app.extensions import db
from models.queue_management import QueueManagement
from models.visit import Visit
from seeds import tenant_bypass
from wsgi import app

with app.app_context():
    tenant = db.session.execute(select(Tenant).filter_by(slug='dr-ahmed-clinic')).scalar_one()
    with tenant_bypass(tenant):
        visit = db.session.get(Visit, 13)
        print('visit', visit.id if visit else None, visit.doctor_id if visit else None)
        rows = (
            db.session.execute(
                select(QueueManagement).filter_by(
                    visit_id=13, department_id=visit.department_id, status='waiting'
                )
            )
            .scalars()
            .all()
        )
        print('tickets', [(r.id, r.status, r.department_id) for r in rows])
        print(
            'all',
            [
                (r.id, r.status, r.visit_id)
                for r in db.session.execute(select(QueueManagement)).scalars().all()
            ],
        )
