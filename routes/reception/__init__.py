import logging
from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app_factory import db
from models.appointment import Appointment
from models.department import Department
from models.follow_up import FollowUpRequest
from models.online_booking import OnlineBooking
from models.patient import Patient
from models.patient_satisfaction import PatientSatisfactionSurvey
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.queue_management import QueueManagement
from models.user import StaffAbsence, StaffWorkSchedule, User
from models.visit import Visit
from services.access_control_service import AccessControlService
from services.gatekeeper_service import GatekeeperService
from services.pos_terminal_service import PosTerminalService
from utils.decorators import (
    can_create_visits,
    can_delete_patient,
    can_modify_patient_data,
    reception_only,
    role_required,
    role_required_json,
)

reception_bp = Blueprint('reception', __name__)

from services.feature_gate_service import guard_module


@reception_bp.before_request
def _guard_reception_module():
    guard_module('reception')


def _wants_json():
    """تحديد ما إذا كان الطلب يتوقع JSON (طلبات fetch)"""
    accept = (request.headers.get('Accept') or '').lower()
    xreq = (request.headers.get('X-Requested-With') or '').lower()
    return ('application/json' in accept) or (xreq == 'xmlhttprequest')


# ═══════════════════════════════════════
# SUBMODULE IMPORTS (must be at bottom)
# ═══════════════════════════════════════

from . import api, appointments, dashboard, patients, payments, queue, visits
