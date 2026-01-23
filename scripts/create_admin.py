"""
Create Core Users Script (idempotent)
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app_factory import create_app, db
from models.user import User
from models.department import Department


def ensure_user(username, email, full_name, role, password, department_id=None, is_admin=False):
    u = User.query.filter_by(username=username).first()
    if u:
        u.email = email
        u.full_name = full_name
        u.role = role
        u.is_admin = is_admin
        u.is_active = True
        if department_id is not None:
            u.department_id = department_id
        u.set_password(password)
        db.session.commit()
        return False
    u = User(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        is_admin=is_admin,
        is_active=True,
        department_id=department_id,
    )
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return True


def main():
    app = create_app()
    with app.app_context():
        dept = Department.query.first()
        dept_id = dept.id if dept else None

        created = []
        if ensure_user('admin', 'admin@example.com', 'Admin User', 'admin', 'Admin@12345', is_admin=True):
            created.append('admin')
        if ensure_user('super', 'super@example.com', 'Super Admin', 'super_admin', 'Super@123', is_admin=True):
            created.append('super_admin')
        if ensure_user('manager', 'manager@example.com', 'Manager User', 'manager', 'Manager@12345', is_admin=True):
            created.append('manager')
        if ensure_user('doctor', 'doctor@example.com', 'Doctor User', 'doctor', 'Doctor@123', department_id=dept_id):
            created.append('doctor')
        if ensure_user('lab', 'lab@example.com', 'Lab User', 'lab', 'Lab@123', department_id=dept_id):
            created.append('lab')
        if ensure_user('radiology', 'radiology@example.com', 'Radiology User', 'radiology', 'Radiology@123', department_id=dept_id):
            created.append('radiology')
        if ensure_user('nurse', 'nurse@example.com', 'Nurse User', 'nurse', 'Nurse@123'):
            created.append('nurse')
        if ensure_user('pharmacist', 'pharmacist@example.com', 'Pharmacist User', 'pharmacist', 'Pharmacist@123'):
            created.append('pharmacist')
        if ensure_user('accountant', 'accountant@example.com', 'Accountant User', 'accountant', '123456'):
            created.append('accountant')
        if ensure_user('emergency', 'emergency@example.com', 'Emergency User', 'emergency', 'Emergency@123'):
            created.append('emergency')
        if ensure_user('reception', 'reception@example.com', 'Reception User', 'reception', 'Reception@123'):
            created.append('reception')

        if created:
            print('created:', ', '.join(created))
        else:
            print('users already exist')


if __name__ == '__main__':
    main()
