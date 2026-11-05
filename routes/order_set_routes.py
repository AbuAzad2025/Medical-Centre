"""Order Sets and Best Practice Advisories routes."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.order_set import BestPracticeAdvisory, OrderSet, OrderSetItem
from utils.decorators import role_required
from utils.tenant_query import get_tenant_record

order_set_bp = Blueprint('order_set', __name__)


@order_set_bp.route('/')
@login_required
@role_required('doctor', 'admin', 'manager')
def index():
    sets = (
        db.session.execute(select(OrderSet).filter_by(is_active=True).order_by(OrderSet.name))
        .scalars()
        .all()
    )
    return render_template('order_sets/index.html', order_sets=sets)


@order_set_bp.route('/<int:set_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def detail(set_id):
    os = get_tenant_record(OrderSet, set_id)
    if not os:
        flash('Order set not found', 'error')
        return redirect(url_for('order_set.index'))
    return render_template('order_sets/detail.html', order_set=os)


@order_set_bp.route('/api/list', methods=['GET'])
@login_required
def api_list():
    sets = (
        db.session.execute(select(OrderSet).filter_by(is_active=True).order_by(OrderSet.name))
        .scalars()
        .all()
    )
    return jsonify([s.to_dict() for s in sets])


@order_set_bp.route('/api/bpa/check', methods=['POST'])
@login_required
def api_bpa_check():
    data = request.get_json() or {}
    context = data.get('context', {})
    advisories = (
        db.session.execute(select(BestPracticeAdvisory).filter_by(is_active=True)).scalars().all()
    )
    triggered = [a.to_dict() for a in advisories if a.check_trigger(context)]
    triggered.sort(key=lambda x: x.get('priority', 0), reverse=True)
    return jsonify({'advisories': triggered})


@order_set_bp.route('/api/create', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def api_create():
    data = request.get_json() or {}
    os = OrderSet(
        tenant_id=getattr(current_user, 'tenant_id', None),
        name=data.get('name', ''),
        name_ar=data.get('name_ar'),
        description=data.get('description'),
        category=data.get('category'),
        diagnosis_code=data.get('diagnosis_code'),
        created_by=current_user.id,
    )
    db.session.add(os)
    db.session.flush()
    for item in data.get('items', []):
        oi = OrderSetItem(
            tenant_id=getattr(current_user, 'tenant_id', None),
            order_set_id=os.id,
            item_type=item.get('item_type', 'medication'),
            item_name=item.get('item_name', ''),
            item_code=item.get('item_code'),
            default_dosage=item.get('default_dosage'),
            default_quantity=item.get('default_quantity', 1),
            default_duration=item.get('default_duration', 7),
            is_optional=item.get('is_optional', False),
            sort_order=item.get('sort_order', 0),
        )
        db.session.add(oi)
    db.session.commit()
    return jsonify(os.to_dict()), 201


@order_set_bp.route('/api/bpa/create', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def api_bpa_create():
    data = request.get_json() or {}
    bpa = BestPracticeAdvisory(
        tenant_id=getattr(current_user, 'tenant_id', None),
        name=data.get('name', ''),
        name_ar=data.get('name_ar'),
        description=data.get('description'),
        trigger_condition=data.get('trigger_condition', 'diagnosis'),
        trigger_value=data.get('trigger_value'),
        advisory_type=data.get('advisory_type', 'info'),
        advisory_message=data.get('advisory_message', ''),
        advisory_message_ar=data.get('advisory_message_ar'),
        priority=data.get('priority', 0),
    )
    db.session.add(bpa)
    db.session.commit()
    return jsonify(bpa.to_dict()), 201
