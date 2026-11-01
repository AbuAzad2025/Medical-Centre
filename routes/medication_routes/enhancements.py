import logging
from datetime import datetime, timedelta

from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.drug_interaction import DrugInteraction
from models.medication import Medication
from routes.medication_routes import medication_bp
from utils.decorators import role_required


@medication_bp.route('/api/interactions/check', methods=['GET', 'POST'])
@medication_bp.route('/interactions/check', methods=['GET', 'POST'])
@medication_bp.route(
    '/interactions/check/<int:medication_a_id>/<int:medication_b_id>', methods=['GET']
)
@login_required
@role_required('pharmacist', 'admin', 'manager', 'doctor')
def check_drug_interactions(medication_a_id=None, medication_b_id=None):
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('medication_ids')
        if ids is None:
            ids = request.args.getlist('medication_id') or request.args.getlist('medication_ids')
        a_id = data.get('medication_a_id', medication_a_id)
        if a_id is None:
            a_id = request.args.get('medication_a_id', type=int)
        b_id = data.get('medication_b_id', medication_b_id)
        if b_id is None:
            b_id = request.args.get('medication_b_id', type=int)

        q = select(DrugInteraction)
        tenant_med_ids = select(Medication.id).filter(
            Medication.tenant_id == current_user.tenant_id
        )
        q = q.filter(
            DrugInteraction.medication_a_id.in_(tenant_med_ids),
            DrugInteraction.medication_b_id.in_(tenant_med_ids),
        )

        if ids:
            try:
                id_list = [int(x) for x in (ids if isinstance(ids, list) else [ids])]
            except (TypeError, ValueError):
                id_list = []
            if id_list:
                q = q.filter(
                    DrugInteraction.medication_a_id.in_(id_list),
                    DrugInteraction.medication_b_id.in_(id_list),
                )
        elif a_id is not None and b_id is not None:
            try:
                a, b = sorted([int(a_id), int(b_id)])
            except (TypeError, ValueError):
                a, b = None, None
            if a is not None:
                q = q.filter(
                    DrugInteraction.medication_a_id == a,
                    DrugInteraction.medication_b_id == b,
                )
        else:
            # no filter -> return none to avoid huge payload
            q = q.filter(False)

        interactions = db.session.execute(q).scalars().all()
        out = []
        for it in interactions:
            out.append(
                {
                    'id': it.id,
                    'medication_a_id': it.medication_a_id,
                    'medication_b_id': it.medication_b_id,
                    'severity': getattr(it, 'severity', None),
                    'description': getattr(it, 'description', None),
                    'is_active': getattr(it, 'is_active', None),
                }
            )
        return jsonify(
            {'success': True, 'interactions': out, 'has_interaction': bool(out), 'count': len(out)}
        )
    except Exception:
        logging.exception('Error checking drug interactions')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@medication_bp.route('/api/stock/alerts', methods=['GET'])
@medication_bp.route('/stock-alerts/api', methods=['GET'])
@medication_bp.route('/stock/alerts', methods=['GET'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def stock_alerts_api():
    try:
        tenant_id = current_user.tenant_id
        low_stock = (
            db.session.execute(
                select(Medication).filter(
                    Medication.tenant_id == tenant_id,
                    Medication.stock_quantity <= Medication.minimum_stock,
                )
            )
            .scalars()
            .all()
        )
        expired = (
            db.session.execute(
                select(Medication).filter(
                    Medication.tenant_id == tenant_id,
                    Medication.expiry_date.isnot(None),
                    Medication.expiry_date < datetime.now().date(),
                )
            )
            .scalars()
            .all()
        )
        soon_cutoff = datetime.now().date() + timedelta(days=30)
        expiring_soon = (
            db.session.execute(
                select(Medication).filter(
                    Medication.tenant_id == tenant_id,
                    Medication.expiry_date.isnot(None),
                    Medication.expiry_date >= datetime.now().date(),
                    Medication.expiry_date <= soon_cutoff,
                )
            )
            .scalars()
            .all()
        )

        def _med(m):
            return {
                'id': m.id,
                'trade_name': getattr(m, 'trade_name', None),
                'stock_quantity': getattr(m, 'stock_quantity', None),
                'minimum_stock': getattr(m, 'minimum_stock', None),
                'expiry_date': m.expiry_date.isoformat()
                if getattr(m, 'expiry_date', None)
                else None,
            }

        return jsonify(
            {
                'success': True,
                'low_stock': [_med(m) for m in low_stock],
                'expired': [_med(m) for m in expired],
                'expiring_soon': [_med(m) for m in expiring_soon],
                'counts': {
                    'low_stock': len(low_stock),
                    'expired': len(expired),
                    'expiring_soon': len(expiring_soon),
                },
            }
        )
    except Exception:
        logging.exception('Error loading stock alerts')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@medication_bp.route('/api/expiry', methods=['GET'])
@medication_bp.route('/expiry', methods=['GET'])
@medication_bp.route('/expiry-tracking', methods=['GET'])
@medication_bp.route('/expiries', methods=['GET'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def expiry_tracking():
    try:
        tenant_id = current_user.tenant_id
        try:
            days = int(request.args.get('days', 30))
        except (TypeError, ValueError):
            days = 30
        days = max(days, 0)
        cutoff = datetime.now().date() + timedelta(days=days)
        meds = (
            db.session.execute(
                select(Medication).filter(
                    Medication.tenant_id == tenant_id,
                    Medication.expiry_date.isnot(None),
                    Medication.expiry_date <= cutoff,
                )
            )
            .scalars()
            .all()
        )
        out = []
        for m in meds:
            out.append(
                {
                    'id': m.id,
                    'trade_name': getattr(m, 'trade_name', None),
                    'expiry_date': m.expiry_date.isoformat()
                    if getattr(m, 'expiry_date', None)
                    else None,
                    'stock_quantity': getattr(m, 'stock_quantity', None),
                    'expired': bool(
                        getattr(m, 'expiry_date', None) and m.expiry_date < datetime.now().date()
                    ),
                }
            )
        return jsonify({'success': True, 'medications': out, 'count': len(out)})
    except Exception:
        logging.exception('Error loading expiry tracking')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
