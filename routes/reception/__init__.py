import logging as logging
from datetime import datetime as datetime
from datetime import timezone as timezone

from flask import Blueprint, request
from flask import flash as flash
from flask import jsonify as jsonify
from flask import redirect as redirect
from flask import render_template as render_template
from flask import url_for as url_for
from flask_login import current_user as current_user
from flask_login import login_required as login_required
from sqlalchemy import func as func

from app_factory import db as db
from models.appointment import Appointment as Appointment
from models.department import Department as Department
from models.follow_up import FollowUpRequest as FollowUpRequest
from models.online_booking import OnlineBooking as OnlineBooking
from models.patient import Patient as Patient
from models.patient_satisfaction import PatientSatisfactionSurvey as PatientSatisfactionSurvey
from models.payment import Payment as Payment
from models.payment import PaymentMethod as PaymentMethod
from models.payment import PaymentStatus as PaymentStatus
from models.queue_management import QueueManagement as QueueManagement
from models.user import StaffAbsence as StaffAbsence
from models.user import StaffWorkSchedule as StaffWorkSchedule
from models.user import User as User
from models.visit import Visit as Visit
from services.access_control_service import AccessControlService as AccessControlService
from services.gatekeeper_service import GatekeeperService as GatekeeperService
from services.pos_terminal_service import PosTerminalService as PosTerminalService
from utils.decorators import can_create_visits as can_create_visits
from utils.decorators import can_delete_patient as can_delete_patient
from utils.decorators import can_modify_patient_data as can_modify_patient_data
from utils.decorators import reception_only as reception_only
from utils.decorators import role_required as role_required
from utils.decorators import role_required_json as role_required_json

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

from . import api as api
from . import appointments as appointments
from . import dashboard as dashboard
from . import patients as patients
from . import payments as payments
from . import queue as queue
from . import visits as visits
