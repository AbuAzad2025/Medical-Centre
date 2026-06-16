"""
Owner (Cloud Control Plane) — platform-level administration
"""
from flask import Blueprint

owner_bp = Blueprint("owner", __name__)

from app.modules.owner import routes
