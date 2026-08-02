import logging

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from services.access_control_service import AccessControlService
from utils.decorators import super_admin_required

# إنشاء Blueprint للسوبر أدمن
super_admin_bp = Blueprint('super_admin', __name__)

# Platform /super-admin console is not gated by a single tenant's module bundle.


# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import (
    analytics,
    api,
    backup,
    branding,
    dashboard,
    data,
    departments,
    roles,
    security,
    services,
    subscription,
    system,
    usage,
    users,
)
