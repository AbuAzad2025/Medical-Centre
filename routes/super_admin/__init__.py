 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
import logging
from sqlalchemy import func

# إنشاء Blueprint للسوبر أدمن
super_admin_bp = Blueprint('super_admin', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@super_admin_bp.before_request
def _guard_owner_module():
    guard_module('owner')


# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import users
from . import roles
from . import departments
from . import services
from . import system
from . import analytics
from . import branding
from . import security
from . import backup
from . import data
from . import api
