"""
Bed Management Routes — Ward, Room, Bed, Admission, Transfer
"""

from flask import Blueprint, g, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from models.bed_management import Admission, Bed, Room, Ward
from services.admission_service import AdmissionService
from utils.decorators import handle_route_errors, role_required

bed_bp = Blueprint('bed', __name__)


@bed_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager', 'receptionist')
@handle_route_errors
def dashboard():
    wards = db.session.execute(select(Ward).filter_by(is_active=True)).scalars().all()
    total_beds = db.session.execute(
        select(func.count()).select_from(Bed).filter_by(is_active=True)
    ).scalar()
    occupied_beds = db.session.execute(
        select(func.count()).select_from(Bed).filter_by(status='OCCUPIED')
    ).scalar()
    available_beds = total_beds - occupied_beds
    occupancy_rate = (occupied_beds / total_beds * 100) if total_beds else 0
    active_admissions = db.session.execute(
        select(func.count()).select_from(Admission).filter_by(status='ADMITTED', is_active=True)
    ).scalar()
    return render_template(
        'bed/dashboard.html',
        wards=wards,
        total_beds=total_beds,
        occupied_beds=occupied_beds,
        available_beds=available_beds,
        occupancy_rate=occupancy_rate,
        active_admissions=active_admissions,
    )


@bed_bp.route('/wards')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def wards():
    items = (
        db.session.execute(select(Ward).filter_by(is_active=True).order_by(Ward.name))
        .scalars()
        .all()
    )
    return render_template('bed/wards.html', wards=items)


@bed_bp.route('/ward/<int:ward_id>')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def ward_detail(ward_id):
    ward = db.get_or_404(Ward, ward_id)
    rooms = (
        db.session.execute(select(Room).filter_by(ward_id=ward_id, is_active=True)).scalars().all()
    )
    return render_template('bed/ward_detail.html', ward=ward, rooms=rooms)


@bed_bp.route('/room/<int:room_id>')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def room_detail(room_id):
    room = db.get_or_404(Room, room_id)
    beds = (
        db.session.execute(select(Bed).filter_by(room_id=room_id, is_active=True)).scalars().all()
    )
    return render_template('bed/room_detail.html', room=room, beds=beds)


@bed_bp.route('/admissions')
@login_required
@role_required('nurse', 'admin', 'manager', 'receptionist')
@handle_route_errors
def admissions():
    status = request.args.get('status', 'ADMITTED')
    items = (
        db.session.execute(
            select(Admission)
            .filter_by(status=status, is_active=True)
            .order_by(Admission.admission_datetime.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return render_template('bed/admissions.html', admissions=items, status=status)


@bed_bp.route('/admission/<int:admission_id>')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def admission_detail(admission_id):
    admission = db.get_or_404(Admission, admission_id)
    return render_template('bed/admission_detail.html', admission=admission)


@bed_bp.route('/api/available-beds')
@login_required
@role_required('nurse', 'doctor', 'admin', 'manager')
@handle_route_errors
def api_available_beds():
    ward_id = request.args.get('ward_id', type=int)
    query = select(Bed)
    if ward_id:
        query = query.join(Room).filter(Room.ward_id == ward_id)
    beds = db.session.execute(query).scalars().all()
    return jsonify(
        [
            {'id': b.id, 'bed_number': b.bed_number, 'room': b.room.name, 'ward': b.room.ward.name}
            for b in beds
        ]
    )


@bed_bp.route('/api/bed-status')
@login_required
@role_required('nurse', 'doctor', 'admin', 'manager')
@handle_route_errors
def api_bed_status():
    beds = db.session.execute(select(Bed).filter_by(is_active=True)).scalars().all()
    return jsonify(
        [
            {
                'id': b.id,
                'number': b.bed_number,
                'status': b.status,
                'room': b.room.name,
                'ward': b.room.ward.name,
                'patient': b.current_patient.full_name if b.current_patient else None,
            }
            for b in beds
        ]
    )


def _tenant_id():
    return getattr(g, 'tenant_id', None) or getattr(current_user, 'tenant_id', None)


@bed_bp.route('/api/admissions/admit', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def api_admit():
    data = request.get_json(silent=True) or {}
    visit_id = data.get('visit_id')
    bed_id = data.get('bed_id')
    if visit_id is None or bed_id is None:
        return jsonify({'success': False, 'message': 'visit_id و bed_id مطلوبان'}), 400
    result = AdmissionService.create_admission(
        visit_id=visit_id,
        bed_id=bed_id,
        user_id=current_user.id,
        tenant_id=_tenant_id(),
    )
    return jsonify(result), 200 if result.get('success') else 400


@bed_bp.route('/api/admissions/<int:admission_id>/discharge', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def api_discharge(admission_id):
    data = request.get_json(silent=True) or {}
    discharge_type = data.get('discharge_type')
    if not discharge_type:
        return jsonify({'success': False, 'message': 'discharge_type مطلوب'}), 400
    result = AdmissionService.process_discharge(
        admission_id=admission_id,
        discharge_type=discharge_type,
        summary_notes=data.get('summary_notes'),
        user_id=current_user.id,
        tenant_id=_tenant_id(),
    )
    return jsonify(result), 200 if result.get('success') else 400


@bed_bp.route('/api/admissions/<int:admission_id>/transfer', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def api_transfer(admission_id):
    data = request.get_json(silent=True) or {}
    target_bed_id = data.get('target_bed_id')
    if target_bed_id is None:
        return jsonify({'success': False, 'message': 'target_bed_id مطلوب'}), 400
    result = AdmissionService.process_transfer(
        admission_id=admission_id,
        target_bed_id=target_bed_id,
        transfer_reason=data.get('transfer_reason'),
        user_id=current_user.id,
        tenant_id=_tenant_id(),
    )
    return jsonify(result), 200 if result.get('success') else 400
