"""
Bed Management Routes — Ward, Room, Bed, Admission, Transfer
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.bed_management import Ward, Room, Bed, Admission, BedTransfer
from models.patient import Patient
from models.user import User
from models.department import Department
from app_factory import db
import logging

bed_bp = Blueprint('bed', __name__)


@bed_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager', 'receptionist')
@handle_route_errors
def dashboard():
    wards = Ward.query.filter_by(is_active=True).all()
    total_beds = Bed.query.filter_by(is_active=True).count()
    occupied_beds = Bed.query.filter_by(status='OCCUPIED').count()
    available_beds = total_beds - occupied_beds
    occupancy_rate = (occupied_beds / total_beds * 100) if total_beds else 0
    active_admissions = Admission.query.filter_by(status='ADMITTED', is_active=True).count()
    return render_template('bed/dashboard.html',
                           wards=wards, total_beds=total_beds,
                           occupied_beds=occupied_beds, available_beds=available_beds,
                           occupancy_rate=occupancy_rate, active_admissions=active_admissions)

@bed_bp.route('/wards')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def wards():
    items = Ward.query.filter_by(is_active=True).order_by(Ward.name).all()
    return render_template('bed/wards.html', wards=items)

@bed_bp.route('/ward/<int:ward_id>')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def ward_detail(ward_id):
    ward = Ward.query.get_or_404(ward_id)
    rooms = Room.query.filter_by(ward_id=ward_id, is_active=True).all()
    return render_template('bed/ward_detail.html', ward=ward, rooms=rooms)

@bed_bp.route('/room/<int:room_id>')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def room_detail(room_id):
    room = Room.query.get_or_404(room_id)
    beds = Bed.query.filter_by(room_id=room_id, is_active=True).all()
    return render_template('bed/room_detail.html', room=room, beds=beds)

@bed_bp.route('/admissions')
@login_required
@role_required('nurse', 'admin', 'manager', 'receptionist')
@handle_route_errors
def admissions():
    status = request.args.get('status', 'ADMITTED')
    items = Admission.query.filter_by(status=status, is_active=True).order_by(
        Admission.admission_datetime.desc()
    ).limit(200).all()
    return render_template('bed/admissions.html', admissions=items, status=status)

@bed_bp.route('/admission/<int:admission_id>')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def admission_detail(admission_id):
    admission = Admission.query.get_or_404(admission_id)
    return render_template('bed/admission_detail.html', admission=admission)

@bed_bp.route('/api/available-beds')
@login_required
@handle_route_errors
def api_available_beds():
    ward_id = request.args.get('ward_id', type=int)
    query = Bed.query.filter_by(status='AVAILABLE', is_active=True)
    if ward_id:
        query = query.join(Room).filter(Room.ward_id == ward_id)
    beds = query.all()
    return jsonify([{'id': b.id, 'bed_number': b.bed_number,
                     'room': b.room.name, 'ward': b.room.ward.name} for b in beds])

@bed_bp.route('/api/bed-status')
@login_required
@handle_route_errors
def api_bed_status():
    beds = Bed.query.filter_by(is_active=True).all()
    return jsonify([{'id': b.id, 'number': b.bed_number, 'status': b.status,
                     'room': b.room.name, 'ward': b.room.ward.name,
                     'patient': b.current_patient.full_name if b.current_patient else None} for b in beds])
