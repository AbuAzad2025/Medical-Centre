"""
Owner (Cloud Control Plane) — platform-level administration
"""
from flask import Blueprint

owner_bp = Blueprint("owner", __name__, url_prefix="/owner")

from app.modules.owner import routes
