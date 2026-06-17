
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timezone
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.online_booking import OnlineBooking
from models.department import Department
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.queue_management import QueueManagement
from models.patient_satisfaction import PatientSatisfactionSurvey
from services.gatekeeper_service import GatekeeperService
from utils.decorators import can_create_visits, reception_only, role_required, role_required_json, can_modify_patient_data, can_delete_patient
from app_factory import db
import logging
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService

reception_bp = Blueprint('reception', __name__)


def _wants_json():
    """تحديد ما إذا كان الطلب يتوقع JSON (طلبات fetch)"""
    accept = (request.headers.get('Accept') or '').lower()
    xreq = (request.headers.get('X-Requested-With') or '').lower()
    return ('application/json' in accept) or (xreq == 'xmlhttprequest')


# ═══════════════════════════════════════
# SUBMODULE IMPORTS (must be at bottom)
# ═══════════════════════════════════════

from . import patients
from . import dashboard
from . import visits
from . import appointments
from . import queue
from . import payments
from . import api
