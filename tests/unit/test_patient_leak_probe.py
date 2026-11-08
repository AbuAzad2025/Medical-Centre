"""Probe whether rows created in one test are visible in the next."""

import pytest

from app.extensions import db
from models.patient import Patient


def test_sees_patients(app, test_tenant, db):
    rows = db.session.execute(
        db.text("select count(*) from patients where first_name like 'WaitPatient%'")
    ).scalar()
    print('\nWaitPatient rows visible in this test:', rows)
    assert True
