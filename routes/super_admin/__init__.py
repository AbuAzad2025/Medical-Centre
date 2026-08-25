import logging as logging

from flask import Blueprint
from flask import abort as abort
from flask import flash as flash
from flask import jsonify as jsonify
from flask import redirect as redirect
from flask import render_template as render_template
from flask import request as request
from flask import url_for as url_for
from flask_login import current_user as current_user
from flask_login import login_required as login_required
from sqlalchemy import func as func

from services.access_control_service import AccessControlService as AccessControlService
from utils.decorators import super_admin_required as super_admin_required

# Ø¥Ù†Ø´Ø§Ø¡ Blueprint Ù„Ù„Ø³ÙˆØ¨Ø± Ø£Ø¯Ù…Ù†
super_admin_bp = Blueprint('super_admin', __name__)

# Platform /super-admin console is not gated by a single tenant's module bundle.


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SUBMODULE IMPORTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

from . import analytics as analytics
from . import api as api
from . import backup as backup
from . import branding as branding
from . import dashboard as dashboard
from . import data as data
from . import departments as departments
from . import roles as roles
from . import security as security
from . import security_logs_api as security_logs_api
from . import services as services
from . import subscription as subscription
from . import system as system
from . import usage as usage
from . import users as users
