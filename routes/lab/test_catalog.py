"""Test catalog and panel CRUD routes"""

from routes.lab import lab_bp
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.lab_test_catalog import LabTestCatalog, LabTestPanel, LabTestPanelItem
from app_factory import db
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


CATEGORIES = [
    'chemistry', 'hematology', 'microbiology', 'serology',
    'immunology', 'urinalysis', 'coagulation', 'other'
]


def _tenant_filter():
    if getattr(current_user, 'tenant_id', None):
        return LabTestCatalog.tenant_id == current_user.tenant_id
    return True


# ─────────────── Test Catalog CRUD ───────────────

@lab_bp.route('/test-catalog/')
@login_required
@role_required('lab', 'manager', 'admin')
def test_catalog():
    category = request.args.get('category', '')
    q = LabTestCatalog.query.filter(_tenant_filter())
    if category:
        q = q.filter(LabTestCatalog.category == category)
    tests = q.order_by(LabTestCatalog.sort_order, LabTestCatalog.code).all()
    return render_template('lab/test_catalog.html', tests=tests, categories=CATEGORIES, selected_category=category)


@lab_bp.route('/test-catalog/add', methods=['POST'])
@login_required
@role_required('lab', 'manager', 'admin')
def test_catalog_add():
    try:
        test = LabTestCatalog(
            tenant_id=getattr(current_user, 'tenant_id', None),
            code=request.form.get('code', '').strip(),
            name_ar=request.form.get('name_ar', '').strip(),
            name_en=request.form.get('name_en', '').strip(),
            category=request.form.get('category', 'other'),
            unit=request.form.get('unit', '').strip(),
            default_reference_range=request.form.get('default_reference_range', '').strip(),
            critical_low=request.form.get('critical_low', '').strip(),
            critical_high=request.form.get('critical_high', '').strip(),
            price=request.form.get('price', 0) or 0,
            preparation_instructions=request.form.get('preparation_instructions', '').strip(),
            is_active=request.form.get('is_active', '1') == '1',
            sort_order=request.form.get('sort_order', 0) or 0,
        )
        db.session.add(test)
        db.session.commit()
        flash('تم إضافة الفحص إلى الكتالوج', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('Error adding test catalog entry')
        flash(f'خطأ في إضافة الفحص: {e}', 'danger')
    return redirect(url_for('lab.test_catalog', category=request.form.get('category', '')))


@lab_bp.route('/test-catalog/<int:id>/edit', methods=['POST'])
@login_required
@role_required('lab', 'manager', 'admin')
def test_catalog_edit(id):
    test = db.session.get(LabTestCatalog, id)
    if not test:
        flash('الفحص غير موجود', 'danger')
        return redirect(url_for('lab.test_catalog'))
    try:
        test.code = request.form.get('code', '').strip()
        test.name_ar = request.form.get('name_ar', '').strip()
        test.name_en = request.form.get('name_en', '').strip()
        test.category = request.form.get('category', 'other')
        test.unit = request.form.get('unit', '').strip()
        test.default_reference_range = request.form.get('default_reference_range', '').strip()
        test.critical_low = request.form.get('critical_low', '').strip()
        test.critical_high = request.form.get('critical_high', '').strip()
        test.price = request.form.get('price', 0) or 0
        test.preparation_instructions = request.form.get('preparation_instructions', '').strip()
        test.is_active = request.form.get('is_active', '1') == '1'
        test.sort_order = request.form.get('sort_order', 0) or 0
        test.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('تم تحديث الفحص', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('Error editing test catalog entry')
        flash(f'خطأ في تحديث الفحص: {e}', 'danger')
    return redirect(url_for('lab.test_catalog', category=request.form.get('category', '')))


@lab_bp.route('/test-catalog/<int:id>/delete', methods=['POST'])
@login_required
@role_required('lab', 'manager', 'admin')
def test_catalog_delete(id):
    test = db.session.get(LabTestCatalog, id)
    if not test:
        flash('الفحص غير موجود', 'danger')
        return redirect(url_for('lab.test_catalog'))
    try:
        db.session.delete(test)
        db.session.commit()
        flash('تم حذف الفحص', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في حذف الفحص: {e}', 'danger')
    return redirect(url_for('lab.test_catalog'))


# ─────────────── Test Panels CRUD ───────────────

@lab_bp.route('/test-panels/')
@login_required
@role_required('lab', 'manager', 'admin')
def test_panels():
    panels = LabTestPanel.query.filter(
        LabTestPanel.tenant_id == getattr(current_user, 'tenant_id', None)
    ).order_by(LabTestPanel.name_ar).all()
    tests = LabTestCatalog.query.filter(
        _tenant_filter(), LabTestCatalog.is_active == True
    ).order_by(LabTestCatalog.sort_order, LabTestCatalog.code).all()
    return render_template('lab/test_panels.html', panels=panels, tests=tests)


@lab_bp.route('/test-panels/add', methods=['POST'])
@login_required
@role_required('lab', 'manager', 'admin')
def test_panels_add():
    try:
        panel = LabTestPanel(
            tenant_id=getattr(current_user, 'tenant_id', None),
            name_ar=request.form.get('name_ar', '').strip(),
            name_en=request.form.get('name_en', '').strip(),
            description=request.form.get('description', '').strip(),
            is_active=request.form.get('is_active', '1') == '1',
        )
        test_ids = request.form.getlist('test_ids')
        for idx, tid in enumerate(test_ids):
            if tid and tid.strip().isdigit():
                panel.items.append(LabTestPanelItem(
                    test_id=int(tid),
                    sort_order=idx
                ))
        db.session.add(panel)
        db.session.commit()
        flash('تم إضافة الباقة', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('Error adding panel')
        flash(f'خطأ في إضافة الباقة: {e}', 'danger')
    return redirect(url_for('lab.test_panels'))


@lab_bp.route('/test-panels/<int:id>/edit', methods=['POST'])
@login_required
@role_required('lab', 'manager', 'admin')
def test_panels_edit(id):
    panel = db.session.get(LabTestPanel, id)
    if not panel:
        flash('الباقة غير موجودة', 'danger')
        return redirect(url_for('lab.test_panels'))
    try:
        panel.name_ar = request.form.get('name_ar', '').strip()
        panel.name_en = request.form.get('name_en', '').strip()
        panel.description = request.form.get('description', '').strip()
        panel.is_active = request.form.get('is_active', '1') == '1'
        panel.updated_at = datetime.now(timezone.utc)

        panel.items.clear()
        db.session.flush()
        test_ids = request.form.getlist('test_ids')
        for idx, tid in enumerate(test_ids):
            if tid and tid.strip().isdigit():
                panel.items.append(LabTestPanelItem(
                    test_id=int(tid),
                    sort_order=idx
                ))
        db.session.commit()
        flash('تم تحديث الباقة', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('Error editing panel')
        flash(f'خطأ في تحديث الباقة: {e}', 'danger')
    return redirect(url_for('lab.test_panels'))


@lab_bp.route('/test-panels/<int:id>/delete', methods=['POST'])
@login_required
@role_required('lab', 'manager', 'admin')
def test_panels_delete(id):
    panel = db.session.get(LabTestPanel, id)
    if not panel:
        flash('الباقة غير موجودة', 'danger')
        return redirect(url_for('lab.test_panels'))
    try:
        db.session.delete(panel)
        db.session.commit()
        flash('تم حذف الباقة', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في حذف الباقة: {e}', 'danger')
    return redirect(url_for('lab.test_panels'))


# ─────────────── JSON API for auto-fill ───────────────

@lab_bp.route('/api/test-catalog')
@login_required
def api_test_catalog():
    q = LabTestCatalog.query.filter(_tenant_filter(), LabTestCatalog.is_active == True)
    q = q.order_by(LabTestCatalog.sort_order, LabTestCatalog.code)
    tests = q.all()
    return jsonify([{
        'id': t.id,
        'code': t.code,
        'name_ar': t.name_ar,
        'name_en': t.name_en,
        'category': t.category,
        'unit': t.unit or '',
        'default_reference_range': t.default_reference_range or '',
        'critical_low': t.critical_low or '',
        'critical_high': t.critical_high or '',
    } for t in tests])


@lab_bp.route('/api/test-catalog/<int:id>')
@login_required
def api_test_catalog_item(id):
    test = db.session.get(LabTestCatalog, id)
    if not test:
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'id': test.id,
        'code': test.code,
        'name_ar': test.name_ar,
        'name_en': test.name_en,
        'category': test.category,
        'unit': test.unit or '',
        'default_reference_range': test.default_reference_range or '',
        'critical_low': test.critical_low or '',
        'critical_high': test.critical_high or '',
        'price': float(test.price) if test.price else 0,
        'preparation_instructions': test.preparation_instructions or '',
    })
