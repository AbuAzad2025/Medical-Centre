"""Dynamic specialty forms — UX1-005."""

from datetime import UTC

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

specialty_forms_bp = Blueprint('specialty_forms', __name__)

ALLOWED_TYPES = {'text', 'number', 'date', 'select', 'checkbox', 'textarea'}


@specialty_forms_bp.route('/specialty-forms')
@login_required
def list_forms():
    from models.specialty_form import SpecialtyForm

    forms = (
        db.session.execute(
            select(SpecialtyForm).filter_by(is_active=True).order_by(SpecialtyForm.name)
        )
        .scalars()
        .all()
    )
    return render_template('specialty_forms/list.html', forms=forms)


@specialty_forms_bp.route('/specialty-forms/new', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def new_form():
    from models.specialty_form import SpecialtyForm, SpecialtyFormVersion

    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            slug = (request.form.get('slug') or '').strip()
            specialty = (request.form.get('specialty') or '').strip() or None
            description = (request.form.get('description') or '').strip() or None
            if not name or not slug:
                flash('الاسم والمعرّف مطلوبان', 'error')
                return redirect(url_for('specialty_forms.new_form'))
            existing = (
                db.session.execute(select(SpecialtyForm).filter_by(slug=slug)).scalars().first()
            )
            if existing:
                flash('المعرّف مستخدم مسبقاً', 'error')
                return redirect(url_for('specialty_forms.new_form'))
            form = SpecialtyForm(
                name=name,
                slug=slug,
                specialty=specialty,
                description=description,
                is_active=True,
                created_by=current_user.id,
            )
            db.session.add(form)
            db.session.flush()
            version = SpecialtyFormVersion(form_id=form.id, version_number=1, status='draft')
            db.session.add(version)
            db.session.flush()
            _save_fields_from_request(version.id)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إنشاء النموذج', 'success')
            return redirect(
                url_for('specialty_forms.edit_version', form_id=form.id, version_id=version.id)
            )
        except Exception as e:
            safe_rollback(db.session, error_message='database rollback')
            flash('حدث خطأ أثناء إنشاء النموذج', 'error')
            import logging

            logging.exception(f'Error creating specialty form: {e}')
    return render_template('specialty_forms/new.html')


@specialty_forms_bp.route('/specialty-forms/<int:form_id>')
@login_required
def view_form(form_id):
    from models.specialty_form import SpecialtyForm

    form = db.get_or_404(SpecialtyForm, form_id)
    version = form.latest_published_version
    return render_template('specialty_forms/view.html', form=form, version=version)


@specialty_forms_bp.route(
    '/specialty-forms/<int:form_id>/versions/<int:version_id>/edit', methods=['GET', 'POST']
)
@login_required
@role_required('manager', 'admin', 'super_admin')
def edit_version(form_id, version_id):
    from models.specialty_form import SpecialtyForm, SpecialtyFormVersion

    form = db.get_or_404(SpecialtyForm, form_id)
    version = db.get_or_404(SpecialtyFormVersion, version_id)
    if version.status != 'draft':
        flash('لا يمكن تعديل نسخ منشورة أو مؤرشفة', 'error')
        return redirect(url_for('specialty_forms.view_form', form_id=form.id))
    if request.method == 'POST':
        try:
            version.form.name = (request.form.get('name') or version.form.name).strip()
            version.form.specialty = (request.form.get('specialty') or '').strip() or None
            version.form.description = (request.form.get('description') or '').strip() or None
            for old in version.fields:
                db.session.delete(old)
            db.session.flush()
            _save_fields_from_request(version.id)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم حفظ النموذج', 'success')
            return redirect(
                url_for('specialty_forms.edit_version', form_id=form.id, version_id=version.id)
            )
        except Exception as e:
            safe_rollback(db.session, error_message='database rollback')
            flash('حدث خطأ أثناء حفظ النموذج', 'error')
            import logging

            logging.exception(f'Error editing specialty form: {e}')
    return render_template('specialty_forms/edit.html', form=form, version=version)


@specialty_forms_bp.route(
    '/specialty-forms/<int:form_id>/versions/<int:version_id>/publish', methods=['POST']
)
@login_required
@role_required('manager', 'admin', 'super_admin')
def publish_version(form_id, version_id):
    from datetime import datetime

    from models.specialty_form import SpecialtyForm, SpecialtyFormVersion

    form = db.get_or_404(SpecialtyForm, form_id)
    version = db.get_or_404(SpecialtyFormVersion, version_id)
    if not version.fields:
        flash('لا يمكن نشر نموذج بدون حقول', 'error')
        return redirect(
            url_for('specialty_forms.edit_version', form_id=form.id, version_id=version.id)
        )
    try:
        version.status = 'published'
        version.published_at = datetime.now(UTC)
        version.published_by = current_user.id
        form.latest_published_version_id = version.id
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم نشر النسخة', 'success')
        return redirect(url_for('specialty_forms.view_form', form_id=form.id))
    except Exception as e:
        safe_rollback(db.session, error_message='database rollback')
        flash('حدث خطأ أثناء نشر النسخة', 'error')
        import logging

        logging.exception(f'Error publishing specialty form: {e}')
        return redirect(
            url_for('specialty_forms.edit_version', form_id=form.id, version_id=version.id)
        )


@specialty_forms_bp.route('/specialty-forms/<int:form_id>/fill', methods=['GET', 'POST'])
@login_required
def fill_form(form_id):
    from models.patient import Patient
    from models.specialty_form import SpecialtyForm, SpecialtyFormSubmission

    form = db.get_or_404(SpecialtyForm, form_id)
    version = form.latest_published_version
    if not version:
        flash('لا توجد نسخة منشورة لهذا النموذج', 'error')
        return redirect(url_for('specialty_forms.list_forms'))
    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient_id', type=int)
            visit_id = request.form.get('visit_id', type=int) or None
            patient = db.get_or_404(Patient, patient_id)
            answers = {}
            for field in version.fields:
                key = f'field_{field.name}'
                if field.field_type == 'checkbox':
                    answers[field.name] = request.form.getlist(key)
                else:
                    answers[field.name] = request.form.get(key, '').strip()
                if field.required and not answers[field.name]:
                    flash(f'الحقل {field.label} مطلوب', 'error')
                    return redirect(url_for('specialty_forms.fill_form', form_id=form.id))
            submission = SpecialtyFormSubmission(
                version_id=version.id,
                patient_id=patient.id,
                visit_id=visit_id,
                answers=answers,
                submitted_by=current_user.id,
            )
            db.session.add(submission)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم حفظ الإجابات', 'success')
            return redirect(url_for('specialty_forms.view_submission', submission_id=submission.id))
        except Exception as e:
            safe_rollback(db.session, error_message='database rollback')
            flash('حدث خطأ أثناء حفظ الإجابات', 'error')
            import logging

            logging.exception(f'Error saving specialty form submission: {e}')
    patients = (
        db.session.execute(
            select(Patient).order_by(Patient.first_name, Patient.last_name).limit(200)
        )
        .scalars()
        .all()
    )
    return render_template(
        'specialty_forms/fill.html', form=form, version=version, patients=patients
    )


@specialty_forms_bp.route('/specialty-forms/submissions/<int:submission_id>')
@login_required
def view_submission(submission_id):
    from models.specialty_form import SpecialtyFormSubmission

    submission = db.get_or_404(SpecialtyFormSubmission, submission_id)
    return render_template('specialty_forms/submission.html', submission=submission)


@specialty_forms_bp.route('/specialty-forms/<int:form_id>/submissions')
@login_required
def list_submissions(form_id):
    from models.specialty_form import SpecialtyForm, SpecialtyFormSubmission

    form = db.get_or_404(SpecialtyForm, form_id)
    submissions = (
        db.session.execute(
            select(SpecialtyFormSubmission)
            .filter(SpecialtyFormSubmission.version_id.in_([v.id for v in form.versions]))
            .order_by(SpecialtyFormSubmission.submitted_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template('specialty_forms/submissions.html', form=form, submissions=submissions)


def _save_fields_from_request(version_id):
    from models.specialty_form import SpecialtyFormField

    labels = request.form.getlist('field_label[]')
    names = request.form.getlist('field_name[]')
    types = request.form.getlist('field_type[]')
    requireds = request.form.getlist('field_required[]')
    options = request.form.getlist('field_options[]')
    defaults = request.form.getlist('field_default[]')
    orders = request.form.getlist('field_order[]')
    for i in range(len(labels)):
        name = (names[i] if i < len(names) else f'field_{i}').strip()
        field_type = (types[i] if i < len(types) else 'text').strip()
        if field_type not in ALLOWED_TYPES:
            field_type = 'text'
        field = SpecialtyFormField(
            version_id=version_id,
            label=(labels[i] if i < len(labels) else name).strip(),
            name=name,
            field_type=field_type,
            required=str(requireds[i] if i < len(requireds) else '0') == '1',
            options=[
                o.strip() for o in (options[i] if i < len(options) else '').split('\n') if o.strip()
            ]
            if field_type in ('select', 'checkbox')
            else None,
            default_value=(defaults[i] if i < len(defaults) else '').strip() or None,
            sort_order=int(orders[i]) if i < len(orders) and orders[i].isdigit() else i,
        )
        db.session.add(field)
