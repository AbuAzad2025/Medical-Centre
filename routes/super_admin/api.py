"""api routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

# Imports
 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
from services.super_admin_service import super_admin_service
import logging
from sqlalchemy import func
from datetime import datetime, timedelta, timezone


# =============================================
# API ROUTES
# =============================================

# ============================================
# API Routes for AJAX Calls
# ============================================

@super_admin_bp.route('/api/audit-log', methods=['POST'])
@login_required
@super_admin_required
def api_audit_log():
    """API لتسجيل الأحداث"""
    try:
        from models.audit_trail import AuditTrail
        from app_factory import db
        
        data = request.get_json(silent=True) or {}
        
        action = (data.get('action') or 'view')
        allowed_actions = {'create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access'}
        safe_action = action if action in allowed_actions else 'view'

        entity_type = (data.get('entity_type') or 'system')
        allowed_entity_types = {'system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department'}
        safe_entity_type = entity_type if entity_type in allowed_entity_types else 'system'

        audit = AuditTrail(
            entity_type=safe_entity_type,
            entity_id=int(data.get('entity_id', 0) or 0),
            action=safe_action,
            user_id=current_user.id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            description=data.get('description', ''),
            notes=(data.get('notes') or '') + (f"\nraw_action={action}" if safe_action != action else '') + (f"\nraw_entity_type={entity_type}" if safe_entity_type != entity_type else '')
        )
        
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تسجيل الحدث'}), 200
        
    except Exception as e:
        from app_factory import db
        db.session.rollback()
        logging.error(f"API audit log error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تسجيل الحدث حالياً'}), 500

@super_admin_bp.route('/api/recent-activities')
@login_required
@super_admin_required
def api_recent_activities():
    """API للحصول على النشاطات الأخيرة"""
    try:
        from models.audit_trail import AuditTrail
        from datetime import datetime, timedelta
        
        # الحصول على آخر 10 نشاطات
        recent = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(10).all()
        
        activities = []
        for activity in recent:
            # حساب الوقت النسبي
            time_diff = datetime.now(timezone.utc) - activity.created_at
            if time_diff.seconds < 60:
                time_str = f"منذ {time_diff.seconds} ثانية"
            elif time_diff.seconds < 3600:
                time_str = f"منذ {time_diff.seconds // 60} دقيقة"
            elif time_diff.seconds < 86400:
                time_str = f"منذ {time_diff.seconds // 3600} ساعة"
            else:
                time_str = f"منذ {time_diff.days} يوم"
            
            # تحديد نوع النشاط
            activity_type = 'primary'
            if activity.action in ['create', 'add']:
                activity_type = 'success'
            elif activity.action in ['update', 'edit']:
                activity_type = 'warning'
            elif activity.action in ['delete', 'remove']:
                activity_type = 'danger'
            
            activities.append({
                'title': activity.description or f"{activity.action} {activity.entity_type}",
                'description': activity.notes or f"المستخدم: {activity.user.full_name if activity.user else 'غير معروف'}",
                'time': time_str,
                'type': activity_type
            })
        
        return jsonify({'success': True, 'activities': activities}), 200
        
    except Exception as e:
        logging.error(f"API recent activities error: {str(e)}")
        return jsonify({'success': False, 'activities': []}), 200

@super_admin_bp.route('/api/ai-assistant', methods=['POST'])
@login_required
@super_admin_required
def api_ai_assistant():
    """API للمساعد الذكي المتطور - محرك واحد موحد"""
    try:
        from app_factory import db
        from services.smart_ai_engine import SmartAIEngine
        from services.ai_validator import AIValidator
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        # إنشاء محرك الذكاء الاصطناعي
        ai_engine = SmartAIEngine(db)
        
        # التحقق من صحة النظام (اختياري - فقط للتحذيرات)
        validation = AIValidator.validate_system_data()
        
        # معالجة السؤال باستخدام المحرك الذكي
        result = ai_engine.process_query(user_message)
        
        response = result.get('response', 'عذراً، لم أتمكن من فهم سؤالك')
        actions = result.get('actions', [])
        
        # إضافة تحذير إذا كانت هناك أخطاء في النظام (بدون منع الاستخدام)
        if not validation['valid'] and len(validation['errors']) > 0:
            warning = "\n\nملاحظة: تم اكتشاف بعض المشاكل في النظام. اكتب فحص صحة النظام للتفاصيل."
            response += warning
        
        return jsonify({
            'success': True,
            'response': response,
            'actions': actions
        }), 200
        
    except Exception as e:
        logging.error(f"AI Assistant error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'response': 'تعذر معالجة طلبك حالياً، يرجى المحاولة مرة أخرى'
        }), 200

