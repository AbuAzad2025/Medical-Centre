"""wards routes - extracted from monolithic nurse_routes.py"""

# Imports
from flask import redirect, render_template, url_for
from flask_login import login_required

from routes.nurse_routes import nurse_bp
from utils.decorators import role_required

# =============================================
# WARDS ROUTES
# =============================================


@nurse_bp.route('/patients')
@login_required
@role_required('nurse', 'manager')
def patients():
    """مرضى التمريض"""

    return redirect(url_for('nurse.patient_care'))


@nurse_bp.route('/wards')
@login_required
@role_required('nurse', 'manager')
def wards():
    """الأجنحة"""

    return render_template('nurse/patient_monitoring.html')
