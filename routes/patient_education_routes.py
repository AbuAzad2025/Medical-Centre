"""
Patient Education Materials Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_from_directory
from flask_login import login_required, current_user
from app_factory import db
from models import PatientEducationMaterial, PatientEducationAssignment, Patient
import os
from werkzeug.utils import secure_filename

patient_education_bp = Blueprint('patient_education', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'education')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@patient_education_bp.route('/')
@login_required
def index():
    category = request.args.get('category', '')
    query = PatientEducationMaterial.query
    if category:
        query = query.filter_by(category=category)
    materials = query.filter_by(is_active=True).order_by(PatientEducationMaterial.created_at.desc()).all()
    categories = db.session.query(PatientEducationMaterial.category).distinct().all()
    return render_template('patient_education/index.html', materials=materials,
                           categories=[c[0] for c in categories], current_category=category)


@patient_education_bp.route('/material/<int:material_id>')
@login_required
def view_material(material_id):
    material = PatientEducationMaterial.query.get_or_404(material_id)
    material.view_count += 1
    db.session.commit()
    assignments = PatientEducationAssignment.query.filter_by(material_id=material_id).order_by(
        PatientEducationAssignment.created_at.desc()).limit(20).all()
    return render_template('patient_education/view.html', material=material, assignments=assignments)


@patient_education_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_material():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'general').strip()
        content_html = request.form.get('content_html', '')
        content_text = request.form.get('content_text', '')
        language = request.form.get('language', 'ar')

        material = PatientEducationMaterial(
            title=title,
            category=category,
            content_html=content_html,
            content_text=content_text,
            language=language,
            created_by=current_user.id
        )

        file = request.files.get('file')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            material.file_path = f'/static/uploads/education/{filename}'
            material.file_type = filename.rsplit('.', 1)[1].lower()

        db.session.add(material)
        db.session.commit()
        flash('تم إضافة المادة التعليمية بنجاح', 'success')
        return redirect(url_for('patient_education.view_material', material_id=material.id))

    return render_template('patient_education/new.html')


@patient_education_bp.route('/edit/<int:material_id>', methods=['GET', 'POST'])
@login_required
def edit_material(material_id):
    material = PatientEducationMaterial.query.get_or_404(material_id)
    if request.method == 'POST':
        material.title = request.form.get('title', '').strip()
        material.category = request.form.get('category', 'general').strip()
        material.content_html = request.form.get('content_html', '')
        material.content_text = request.form.get('content_text', '')
        material.language = request.form.get('language', 'ar')
        material.is_active = request.form.get('is_active') == 'on'

        file = request.files.get('file')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            material.file_path = f'/static/uploads/education/{filename}'
            material.file_type = filename.rsplit('.', 1)[1].lower()

        db.session.commit()
        flash('تم تحديث المادة التعليمية', 'success')
        return redirect(url_for('patient_education.view_material', material_id=material.id))

    return render_template('patient_education/edit.html', material=material)


@patient_education_bp.route('/assign', methods=['POST'])
@login_required
def assign_material():
    patient_id = request.form.get('patient_id', type=int)
    material_id = request.form.get('material_id', type=int)
    notes = request.form.get('notes', '')

    if not patient_id or not material_id:
        flash('بيانات غير كاملة', 'danger')
        return redirect(url_for('patient_education.index'))

    assignment = PatientEducationAssignment(
        patient_id=patient_id,
        material_id=material_id,
        assigned_by=current_user.id,
        notes=notes
    )
    db.session.add(assignment)
    db.session.commit()
    flash('تم إسناد المادة التعليمية للمريض', 'success')
    return redirect(url_for('patient_education.view_material', material_id=material_id))


@patient_education_bp.route('/patient/<int:patient_id>')
@login_required
def patient_materials(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    assignments = PatientEducationAssignment.query.filter_by(patient_id=patient_id).order_by(
        PatientEducationAssignment.created_at.desc()).all()
    materials = PatientEducationMaterial.query.filter_by(is_active=True).all()
    return render_template('patient_education/patient.html', patient=patient,
                           assignments=assignments, materials=materials)
