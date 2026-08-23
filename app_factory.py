"""
Medical System Flask Application Factory
"""

import contextlib
import logging
import os
from datetime import UTC
from datetime import datetime as _dt
from decimal import ROUND_HALF_UP, Decimal

import click
from flask import Flask, g, redirect, render_template, request, url_for
from flask.json.provider import DefaultJSONProvider
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_session import Session
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect as _sa_inspect
from sqlalchemy import select

from utils.db_safety import safe_commit, safe_rollback

# ============================================================
# Admin Alert Hooks (module-level for testability)
# ============================================================
_ALERT_SINKS = []


def register_alert_sink(sink):
    """Register a callable sink(level: str, context: dict) for critical alerts."""
    _ALERT_SINKS.append(sink)


def _alert_admin(level, message, **ctx):
    """Fire all registered alert sinks with trace_id and tenant_id if available."""
    try:
        from flask import g, request

        ctx['trace_id'] = (
            getattr(g, 'trace_id', None)
            or request.headers.get('X-Request-ID')
            or request.headers.get('X-Correlation-ID')
        )
        ctx['tenant_id'] = getattr(g, 'tenant_id', None)
    except RuntimeError:
        ctx['trace_id'] = None
        ctx['tenant_id'] = None
    for sink in _ALERT_SINKS:
        with contextlib.suppress(Exception):
            sink(level, {'message': message, **ctx})


# ============================================================
# Flask extension instances
# ============================================================
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
socketio = SocketIO(async_mode='threading')
sess = Session()


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    class CustomJSONProvider(DefaultJSONProvider):
        def default(self, o):
            if isinstance(o, Decimal):
                return format(o.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')
            return super().default(o)

    app.json_provider_class = CustomJSONProvider

    # اختيار الإعدادات
    from config import config as app_config

    config_name = config_name or os.getenv('APP_ENV', 'development')
    app.config.from_object(app_config.get(config_name, app_config['default']))

    if (
        app_config.get(config_name, app_config['default']).__name__ == 'TestingConfig'
        or os.getenv('APP_ENV') == 'testing'
        or os.getenv('SUPPRESS_DEPRECATION_WARNINGS') in {'1', 'true', 'yes', 'on'}
    ):
        try:
            import warnings

            warnings.filterwarnings('ignore', category=DeprecationWarning)
            if os.getenv('SUPPRESS_LOGGING') in {'1', 'true', 'yes', 'on'} or app.testing:
                logging.disable(logging.CRITICAL)
        except Exception:
            pass

    # تهيئة Logging مركزي مع PII Redaction + Trace ID
    from config import get_logging_config

    log_level_name = os.environ.get(
        'LOG_LEVEL', 'DEBUG' if os.environ.get('FLASK_DEBUG') == '1' else 'INFO'
    )
    json_fmt = os.environ.get('LOG_JSON_FORMAT', '').strip().lower() in ('1', 'true', 'yes', 'on')
    logging.config.dictConfig(
        get_logging_config(
            log_level=log_level_name,
            json_format=json_fmt,
        )
    )
    app.logger.info('Logging initialized (PII redaction enabled, trace_id injection active)')

    # إظهار تتبعات أوضح في التطوير
    if os.environ.get('FLASK_DEBUG') == '1':
        app.config['PROPAGATE_EXCEPTIONS'] = True
        app.config['TRAP_HTTP_EXCEPTIONS'] = True
        app.config['TRAP_BAD_REQUEST_ERRORS'] = True

    # SQLAlchemy echo من env (لطباعة الاستعلامات في الكونسول)
    echo_env = os.environ.get('SQLALCHEMY_ECHO', '').strip().lower()
    app.config['SQLALCHEMY_ECHO'] = echo_env in {'1', 'true', 'yes', 'on'}

    # تهيئة الإضافات
    db.init_app(app)

    # Startup guard: fail fast if the application DB role is superuser or has
    # BYPASSRLS — RLS would be silently ineffective.  Override with env var
    # RLS_BYPASS_ALLOWED=1 for local development only.
    try:
        with app.app_context():
            from sqlalchemy import text as _sa_text

            row = db.session.execute(
                _sa_text(
                    'SELECT current_user AS who, rolsuper, rolbypassrls '
                    'FROM pg_roles WHERE rolname = current_user'
                )
            ).fetchone()
            if row:
                who, is_super, bypass = row
                bypass_allowed = os.environ.get('RLS_BYPASS_ALLOWED', '').strip() in (
                    '1',
                    'true',
                    'yes',
                )
                if (is_super or bypass) and not bypass_allowed:
                    import sys as _sys

                    _sys.stderr.write(
                        f"\n!!! FATAL: Application database role '{who}' has "
                        f'SUPERUSER={is_super} BYPASSRLS={bypass}.  RLS would be bypassed.\n'
                        '!!! Set RLS_BYPASS_ALLOWED=1 in env (local dev only) or '
                        'switch to a restricted role.\n'
                    )
                    raise RuntimeError(
                        f'RLS startup guard rejected superuser/BYPASSRLS role '
                        f"'{who}'.  Set RLS_BYPASS_ALLOWED=1 to override."
                    )
    except RuntimeError:
        raise
    except Exception:
        pass  # Table may not exist yet (first migration); guard is best-effort.

    # Startup guard: FIELD_ENCRYPTION_KEY is required in production.
    # Without it, EncryptedString columns silently degrade to plaintext.
    app_env = app.config.get('APP_ENV', 'development')
    if app_env in ('production', 'staging'):
        enc_key = os.environ.get('FIELD_ENCRYPTION_KEY', '')
        if not enc_key or len(enc_key) < 16:
            import sys as _sys

            _sys.stderr.write(
                f'\n!!! FATAL: FIELD_ENCRYPTION_KEY is not set (len={len(enc_key)}). '
                f'PHI fields would be stored as plaintext.\n'
                f'!!! Set FIELD_ENCRYPTION_KEY in environment.\n'
            )
            raise RuntimeError(
                'FIELD_ENCRYPTION_KEY not set in production/staging environment. '
                'EncryptedString columns would degrade to plaintext.'
            )

    @app.before_request
    def _bind_tenant_from_session_early():
        try:
            from app.core.tenant.middleware import bind_tenant_from_session

            bind_tenant_from_session()
        except Exception as e:
            app.logger.debug('Tenant bind early (expected on first request): %s', e)

    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)

    # تهيئة Flask-Session (Redis أو filesystem)
    try:
        sess.init_app(app)
        if app.config.get('SESSION_TYPE') == 'redis':
            app.logger.info('Redis session storage enabled')
        else:
            app.logger.info('Filesystem session storage enabled (default)')
    except Exception as e:
        app.logger.warning(f'Session init failed, falling back to signed cookies: {e}')

    def _get_format_map():
        # Request-level cache: avoids 200+ DB queries per page render
        cached = getattr(g, '_format_map_cache', None)
        if cached is not None:
            return cached
        try:
            from models.system_config import SystemConfig

            df = None
            tf = None
            dcfg = (
                db.session.execute(select(SystemConfig).filter_by(config_key='date_format'))
                .scalars()
                .first()
            )
            if dcfg:
                df = str(dcfg.config_value).lower()
            tcfg = (
                db.session.execute(select(SystemConfig).filter_by(config_key='time_format'))
                .scalars()
                .first()
            )
            if tcfg:
                tf = str(tcfg.config_value).lower()
        except Exception:
            df = None
            tf = None
        date_map = {'dd/mm/yyyy': '%d/%m/%Y', 'mm/dd/yyyy': '%m/%d/%Y', 'yyyy-mm-dd': '%Y-%m-%d'}
        time_map = {'hh:mm': '%H:%M', 'hh:mm:ss': '%H:%M:%S'}
        dfmt = date_map.get(df or 'yyyy-mm-dd')
        tfmt = time_map.get(tf or 'hh:mm')
        result = (dfmt, tfmt, f'{dfmt} {tfmt}')
        g._format_map_cache = result
        return result

    def _fmt_date(val):
        if not val:
            return ''
        dfmt, _, _ = _get_format_map()
        try:
            return (val if hasattr(val, 'strftime') else _dt.fromisoformat(str(val))).strftime(dfmt)
        except Exception:
            try:
                return _dt.utcfromtimestamp(float(val)).strftime(dfmt)
            except Exception:
                return str(val)

    def _fmt_time(val):
        if not val:
            return ''
        _, tfmt, _ = _get_format_map()
        try:
            return (val if hasattr(val, 'strftime') else _dt.fromisoformat(str(val))).strftime(tfmt)
        except Exception:
            try:
                return _dt.utcfromtimestamp(float(val)).strftime(tfmt)
            except Exception:
                return str(val)

    def _fmt_datetime(val):
        if not val:
            return ''
        _, _, dfull = _get_format_map()
        try:
            return (val if hasattr(val, 'strftime') else _dt.fromisoformat(str(val))).strftime(
                dfull
            )
        except Exception:
            try:
                return _dt.utcfromtimestamp(float(val)).strftime(dfull)
            except Exception:
                return str(val)

    app.jinja_env.filters['format_date'] = _fmt_date
    app.jinja_env.filters['format_time'] = _fmt_time
    app.jinja_env.filters['format_datetime'] = _fmt_datetime

    def _fmt_money(amount, currency=None):
        if amount is None:
            return ''
        try:
            cur = currency or app.config.get('DEFAULT_CURRENCY', 'ILS')
            q = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return f'{q:.2f} {cur}'
        except Exception:
            return f'{amount} {currency or app.config.get("DEFAULT_CURRENCY", "ILS")}'

    app.jinja_env.filters['format_money'] = _fmt_money

    # Asset pipeline — hashed asset URLs when built via `npm run build`
    from utils.assets import register_asset_helpers

    register_asset_helpers(app)

    from app.shared.enum_labels import enum_label, resolve_visit_payment_status_badge
    from app.shared.user_messages import resolve_user_message

    app.jinja_env.filters['enum_label'] = enum_label
    app.jinja_env.filters['user_message'] = resolve_user_message
    app.jinja_env.globals['resolve_visit_payment_status_badge'] = resolve_visit_payment_status_badge
    app.jinja_env.globals['_'] = lambda s: s

    from app.shared.branding_context import get_branding_row
    from app.shared.print_context import resolve_print_context

    @app.template_global('get_print_context')
    def get_print_context(doc_type='report'):
        return resolve_print_context(doc_type, get_branding_row())

    @app.after_request
    def _compress_json_response(response):
        try:
            ae = (request.headers.get('Accept-Encoding') or '').lower()
            if 'gzip' in ae and (response.mimetype or '').lower() == 'application/json':
                import gzip

                data = response.get_data()
                if data and len(data) > 512:
                    compressed = gzip.compress(data, compresslevel=6)
                    response.set_data(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Vary'] = 'Accept-Encoding'
        except Exception:
            pass
        return response

    # تسجيل الموديلات في metadata ليتمكن Alembic من اكتشافها (استيراد فقط، بدون استعلامات)
    with app.app_context():
        try:
            # استيراد كل نماذجك هنا (حسب مشروعك)
            # New platform models (tenant, module) — load before User to resolve Tenant ref
            import importlib

            importlib.import_module('app.core.tenant.models')
            importlib.import_module('app.core.module.models')
            importlib.import_module('app.core.saas.models')
            importlib.import_module('app.modules.workflows.stock_models')
            importlib.import_module('models.api_key')
            # استيراد النماذج الأساسية أولاً

            # استيراد النماذج المتقدمة

            # نماذج إضافية لضمان اكتمال تسجيل الـ metadata
        except Exception as e:
            app.logger.warning(f'Model import registration skipped: {e}')

        # Register tracked models + event listeners for PHI audit logging
        try:
            from sqlalchemy import event

            from models.consent_management import PatientConsent
            from models.online_booking import OnlineBooking
            from models.patient import Patient
            from models.phi_audit_log import (
                TRACKED_MODELS,
                PHIAuditLog,
                _phi_audit_after_flush,
                _phi_audit_before_flush,
                _raise_on_modify,
            )

            TRACKED_MODELS.update({Patient, OnlineBooking, PatientConsent})
            # Session-level listeners: PHI audit logging (two-phase for autoincrement PK resolution)
            event.listen(db.session, 'before_flush', _phi_audit_before_flush)
            event.listen(db.session, 'after_flush', _phi_audit_after_flush)
            # Mapper-level listeners: make PHIAuditLog records immutable at the ORM layer
            event.listen(PHIAuditLog, 'before_update', _raise_on_modify)
            event.listen(PHIAuditLog, 'before_delete', _raise_on_modify)
        except Exception as e:
            app.logger.warning(f'PHI audit model registration skipped: {e}')

        # Note: Tests call db.create_all() in their setUp, so we don't call it here

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'الرجاء تسجيل الدخول أولاً.'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(user_id):
        from flask import g

        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant
        from models.user import User

        raw = str(user_id or '')
        if not raw:
            return None
        parts = raw.split(':', 1)
        try:
            uid = int(parts[0])
        except Exception:
            return None
        expected_version = 0
        if len(parts) == 2:
            try:
                expected_version = int(parts[1])
            except Exception:
                expected_version = 0
        prev_bypass = g.get('_tenant_filter_bypass', False)
        # Always bypass tenant filter when loading a user — otherwise the
        # filter would block platform users (tenant_id=NULL) when the early
        # tenant-binding before_request has already set g.tenant_id.
        g._tenant_filter_bypass = True
        try:
            user = db.session.get(User, uid)
        finally:
            if prev_bypass:
                g._tenant_filter_bypass = True
            else:
                g.pop('_tenant_filter_bypass', None)
        if not user:
            return None
        if user.tenant_id and not g.get('tenant_id'):
            tenant = db.session.get(Tenant, user.tenant_id)
            if tenant:
                bind_g_tenant(tenant)
        actual_version = int(getattr(user, 'session_version', 0) or 0)
        if actual_version != expected_version:
            return None
        return user

    # السجلات الدوّارة (تمت في البداية)
    if not app.debug and not app.testing:
        os.makedirs('logs', exist_ok=True)
        # RotatingFileHandler already set up above — skip duplicate
        app.logger.setLevel(logging.INFO)

    # Health
    @app.get('/__health')
    def __health():
        return jsonify(status='ok')

    @app.get('/favicon.ico')
    def favicon():
        return redirect(url_for('static', filename='img/azad_logo.png'), code=302)

    # Global error handlers for custom exceptions (MUST precede generic handlers)
    from app.shared.tenant_filter import TenantIsolationError
    from utils.exceptions import IdempotencyError, ModuleNotEnabledError, TenantContextError

    @app.errorhandler(ModuleNotEnabledError)
    def handle_module_not_enabled(e):
        """SaaS module gate failure -> 403 JSON (API) or flash+redirect (HTML)."""
        if request.is_json or request.path.startswith('/api/'):
            return jsonify(success=False, error=e.message, module=e.module_name), 403
        from flask import flash, redirect, url_for

        flash(e.message, 'error')
        return redirect(url_for('main.index')), 403

    @app.errorhandler(TenantIsolationError)
    @app.errorhandler(TenantContextError)
    def handle_tenant_isolation(e):
        """RLS / cross-tenant access blocked -> 403 JSON (API) or 403 page."""
        _alert_admin('CRITICAL', 'Tenant isolation violation', error=str(e))
        if request.is_json or request.path.startswith('/api/'):
            return jsonify(success=False, error=str(e)), 403
        try:
            return render_template('errors/403.html', message=str(e)), 403
        except Exception as exc:
            return jsonify(error=str(exc)), 403

    @app.errorhandler(PermissionError)
    def handle_permission_error(e):
        """Generic cross-tenant guard from tenant_filter.py loaded_as_persistent."""
        _alert_admin('CRITICAL', 'Permission denied', error=str(e))
        if request.is_json or request.path.startswith('/api/'):
            return jsonify(success=False, error='Cross-tenant access denied'), 403
        try:
            return render_template('errors/403.html', message=str(e)), 403
        except Exception:
            return jsonify(error='Cross-tenant access denied'), 403

    @app.errorhandler(IdempotencyError)
    def handle_idempotency(e):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify(success=False, error='Duplicate request', retry_after=30), 409
        from flask import flash, redirect

        flash('طلب مكرر — يرجى المحاولة لاحقاً', 'warning')
        return redirect(request.referrer or url_for('main.index')), 409

    # معالجات الأخطاء القياسية لربط قوالب الأخطاء
    @app.errorhandler(403)
    def handle_403(error):
        try:
            return render_template('errors/403.html'), 403
        except Exception:
            return jsonify(error='لا يمكن عرض الصفحة حالياً'), 403

    @app.errorhandler(404)
    def handle_404(error):
        try:
            return render_template('errors/404.html'), 404
        except Exception:
            return jsonify(error='الصفحة غير متاحة حالياً'), 404

    # Wire critical error alerts (uses module-level _alert_admin)
    @app.errorhandler(500)
    def handle_500(error):
        _alert_admin('CRITICAL', 'Internal server error', error=str(error))
        try:
            return render_template('errors/500.html'), 500
        except Exception:
            return jsonify(error='تعذر تنفيذ الطلب حالياً'), 500

    # تهيئة بيانات افتراضية (محميّة ضد غياب الجداول أثناء أوامر Alembic)
    with app.app_context():
        try:
            insp = _sa_inspect(db.engine)
            if insp.has_table('system_configs'):
                from models.system_config import SystemConfig

                cfg = (
                    db.session.execute(select(SystemConfig).filter_by(config_key='log_level'))
                    .scalars()
                    .first()
                )
                if cfg and cfg.config_value:
                    lvl = getattr(logging, str(cfg.config_value).upper(), None)
                    if isinstance(lvl, int):
                        app.logger.setLevel(lvl)
                        for h in app.logger.handlers:
                            h.setLevel(lvl)
                # developer_* config seeding moved to platform_bootstrap.ensure_developer_config()
                # (privileged bootstrap path — normal startup is read-only)
            if insp.has_table('users'):
                # من الآمن استيراد Department فقط عند الحاجة
                # from models.department import Department
                pass
            else:
                app.logger.info(
                    'جدول users غير موجود بعد؛ سيتم تخطّي إنشاء الأدمن حتى إكمال الترحيلات.'
                )
        except Exception as e:
            # لا نُفشل التطبيق أثناء أوامر Alembic
            app.logger.warning(f'تخطّي تهيئة البيانات الافتراضية: {e}')

    # إيقاف الإنشاء التلقائي لأي جدول في التطوير لضمان هجرة احترافية فقط عبر Alembic
    # يمكن تفعيلها لاحقًا يدويًا عبر متغير بيئة DEV_CREATE_TREATMENTS=1 إن لزم
    with app.app_context():
        try:
            if app.debug and os.getenv('DEV_CREATE_TREATMENTS', '0') == '1':
                insp = _sa_inspect(db.engine)
                from models.treatment import Treatment

                if not insp.has_table(Treatment.__tablename__):
                    Treatment.__table__.create(db.engine, checkfirst=True)
                    app.logger.info('✅ تم إنشاء جدول treatments تلقائياً في وضع التطوير')
        except Exception as e:
            app.logger.warning(f'Failed to auto-create treatments table: {e}')

    # تزويد القوالب بمتغيرات العلامة التجارية ومعلومات المطور
    @app.context_processor
    def inject_branding():
        # Request-level cache: avoid repeated DB queries in nested templates
        cached = getattr(g, '_branding_request_cache', None)
        if cached is not None:
            return cached
        try:
            import time

            from flask import g as _g

            from app.shared.branding_context import build_branding_payload, get_branding_row

            tenant = getattr(_g, 'current_tenant', None)
            cache_key = (
                f'tenant:{tenant.id}' if tenant and getattr(tenant, 'id', None) else 'platform'
            )
            caches = getattr(app, '_branding_cache_v2', None)
            if caches is None:
                caches = {}
                app._branding_cache_v2 = caches
            now = time.time()
            entry = caches.get(cache_key)
            if not entry or (now - entry.get('ts', 0) > 60):
                caches[cache_key] = {
                    'ts': now,
                    'data': build_branding_payload(db, db.engine),
                }
            data = dict(caches[cache_key]['data'])
            data['branding'] = get_branding_row()
            g._branding_request_cache = data
            return data
        except Exception:
            return {}

    @app.context_processor
    def inject_env():
        try:
            return {
                'APP_ENV': (config_name or os.getenv('APP_ENV') or 'development'),
                'FLASK_ENV': app.env,
            }
        except Exception:
            return {
                'APP_ENV': os.getenv('APP_ENV', 'development'),
                'FLASK_ENV': 'production',
            }

    @app.context_processor
    def inject_user_preferences():
        try:
            from flask_login import current_user

            from app.shared.user_preferences import get_user_preferences

            if current_user.is_authenticated:
                return {'user_preferences': get_user_preferences(current_user)}
        except Exception:
            pass
        return {'user_preferences': {'theme': 'light'}}

    # تسجيل الـ blueprints المتاحة فقط
    from app.modules.owner import owner_bp
    from routes.accountant import accountant_bp
    from routes.ai_imaging_routes import ai_imaging_bp
    from routes.auth_routes import auth_bp
    from routes.backup_restore_routes import backup_restore_bp
    from routes.backup_routes import backup_bp
    from routes.barcode_routes import barcode_bp
    from routes.bed_management_routes import bed_bp
    from routes.biometric_routes import biometric_bp

    # from routes.ai_routes import ai_bp  # REMOVED - AI now integrated in super_admin
    from routes.booking_routes import booking_bp
    from routes.cds_alert_routes import cds_bp
    from routes.clinical_coding import clinical_coding_bp
    from routes.clinical_pathway_routes import pathway_bp
    from routes.custom_report_builder_routes import report_builder_bp
    from routes.data_warehouse_routes import data_warehouse_bp
    from routes.dicom_routes import dicom_bp
    from routes.doctor import doctor_bp
    from routes.emar_routes import emar_bp
    from routes.emergency import emergency_bp
    from routes.fhir_api_routes import fhir_bp
    from routes.finance import finance_bp
    from routes.inbox import inbox_bp
    from routes.lab import lab_bp
    from routes.main import main_bp
    from routes.manager import manager_bp
    from routes.medication_routes import medication_bp
    from routes.mfa_routes import mfa_bp
    from routes.monitoring_routes import monitoring_bp
    from routes.nurse_routes import nurse_bp
    from routes.nursing_assessment_routes import nursing_assessment_bp
    from routes.or_management_routes import or_bp
    from routes.patient_education_routes import patient_education_bp
    from routes.patient_portal import portal_bp
    from routes.payment_routes import payment_bp
    from routes.population_health_routes import pop_health_bp
    from routes.quality_compliance import quality_bp
    from routes.radiology import radiology_bp
    from routes.reception import reception_bp
    from routes.reception_currency import reception_currency_bp
    from routes.referral_routes import referral_bp
    from routes.saas_billing_routes import saas_billing_bp
    from routes.saas_routes import saas_bp
    from routes.security_advanced_routes import security_bp
    from routes.specialty_forms import specialty_forms_bp
    from routes.sso_routes import sso_bp
    from routes.super_admin import super_admin_bp
    from routes.telemedicine_routes import telemedicine_bp
    from routes.vaccination_routes import vaccination_bp
    from routes.what_if_routes import what_if_bp

    # Module guards — must be added BEFORE register_blueprint, and only ONCE
    def _guard_factory(module_name):
        def _guard():
            from flask import abort, g
            from werkzeug.exceptions import HTTPException

            # Skip module guards in testing mode — test tenants may not have
            # all modules enabled, causing false 302/403 in CI.
            if app.config.get('TESTING', False):
                return

            if not app.config.get('ENABLE_SAAS_MODE', False):
                return
            # Admin bypass: global admins pass through all module guards
            try:
                from flask_login import current_user

                if current_user.is_authenticated and current_user.role == 'super_admin':
                    return
            except Exception:
                pass
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                abort(403, description='Tenant context is required in SaaS mode.')
            try:
                # Always query fresh — don't rely on stale g.enabled_modules cache
                from app.core.module.validators import get_active_modules_for_tenant

                enabled = get_active_modules_for_tenant(tenant.id)
                g.enabled_modules = enabled
                if module_name not in enabled:
                    abort(
                        403, description=f"Module '{module_name}' is not activated for this tenant."
                    )
            except HTTPException:
                raise
            except Exception as exc:
                app.logger.exception('Module guard failed for %s', module_name)
                abort(403, description=str(exc))

        return _guard

    def _add_guard_once(bp, module_name):
        if not getattr(bp, '_module_guard_added', False):
            bp.before_request(_guard_factory(module_name))
            bp._module_guard_added = True

    def _add_platform_cap_guard(bp, cap):
        if getattr(bp, '_platform_cap_guard_added', False):
            return

        @bp.before_request
        def _platform_cap_guard():
            from app.core.platform_capabilities import guard_platform_capability

            guard_platform_capability(cap)

        bp._platform_cap_guard_added = True

    # Helper: allow routes to check module access programmatically
    @app.context_processor
    def _inject_module_helpers():
        def module_active(name):
            return name in getattr(g, 'enabled_modules', set())

        return {'module_active': module_active}

    @app.context_processor
    def _inject_platform_capabilities():
        from app.core.platform_capabilities import get_capabilities, platform_capability

        return {
            'platform_capability': platform_capability,
            'platform_capabilities': get_capabilities(),
        }

    @app.context_processor
    def _inject_tenant_url_for():
        """Provide tenant_url_for() that prefixes /t/<slug>/ in SaaS mode.

        Also overrides Jinja's ``url_for`` so that ALL template-generated
        URLs automatically include the ``/t/<slug>/`` prefix for
        tenant-scoped routes.  This prevents bare-path generation in
        production HTML without requiring every template to use
        ``tenant_url_for`` instead of ``url_for``.
        """
        from flask import g
        from flask import url_for as _flask_url_for

        def _tenant_url_for(endpoint, **values):
            if not app.config.get('ENABLE_SAAS_MODE', False):
                return _flask_url_for(endpoint, **values)
            tenant_slug = getattr(g, 'tenant_slug', None)
            if not tenant_slug:
                return _flask_url_for(endpoint, **values)
            url = _flask_url_for(endpoint, **values)
            if not url.startswith('/'):
                return url
            if url.startswith(('/t/', '/static/', '/owner/', '/super-admin/', '/auth/')):
                return url
            return f'/t/{tenant_slug}{url}'

        return {
            'tenant_url_for': _tenant_url_for,
            'url_for': _tenant_url_for,
        }

    _add_guard_once(reception_bp, 'reception')
    _add_guard_once(doctor_bp, 'doctor')
    _add_guard_once(lab_bp, 'lab')
    _add_guard_once(radiology_bp, 'radiology')
    _add_guard_once(emergency_bp, 'emergency')
    _add_guard_once(nurse_bp, 'nursing')
    _add_guard_once(finance_bp, 'billing')
    _add_guard_once(accountant_bp, 'billing')
    _add_guard_once(manager_bp, 'reporting')
    _add_guard_once(booking_bp, 'appointments')
    _add_guard_once(medication_bp, 'pharmacy')
    # Additional module guards for orphan blueprints
    _add_guard_once(payment_bp, 'billing')
    _add_guard_once(emar_bp, 'nursing')
    _add_guard_once(pathway_bp, 'doctor')
    _add_guard_once(report_builder_bp, 'reporting')
    _add_guard_once(data_warehouse_bp, 'reporting')
    _add_guard_once(pop_health_bp, 'reporting')
    _add_guard_once(quality_bp, 'reporting')
    _add_guard_once(what_if_bp, 'reporting')
    _add_guard_once(portal_bp, 'portal')
    _add_guard_once(dicom_bp, 'radiology')
    _add_guard_once(ai_imaging_bp, 'ai_imaging')
    _add_guard_once(barcode_bp, 'inventory')
    _add_guard_once(clinical_coding_bp, 'doctor')
    _add_guard_once(vaccination_bp, 'doctor')
    _add_guard_once(referral_bp, 'doctor')
    _add_guard_once(cds_bp, 'doctor')
    _add_guard_once(patient_education_bp, 'doctor')
    _add_guard_once(telemedicine_bp, 'doctor')
    _add_guard_once(bed_bp, 'nursing')
    _add_guard_once(or_bp, 'nursing')
    _add_guard_once(nursing_assessment_bp, 'nursing')
    _add_guard_once(specialty_forms_bp, 'doctor')
    _add_guard_once(sso_bp, 'integration')
    _add_guard_once(reception_currency_bp, 'reception')
    _add_guard_once(fhir_bp, 'integration')
    _add_platform_cap_guard(biometric_bp, 'webauthn')
    _add_platform_cap_guard(fhir_bp, 'fhir_api')
    _add_platform_cap_guard(sso_bp, 'sso')

    app.register_blueprint(main_bp)
    from routes.api_search import api_search_bp

    app.register_blueprint(api_search_bp, url_prefix='/api/search')
    from routes.api_dashboard import api_dashboard_bp

    app.register_blueprint(api_dashboard_bp, url_prefix='/api/dashboard')
    from routes.api_user import api_user_bp

    app.register_blueprint(api_user_bp, url_prefix='/api/user')
    from routes.api_lab import api_lab_bp

    app.register_blueprint(api_lab_bp, url_prefix='/api/lab')
    from routes.api_radiology import api_radiology_bp

    app.register_blueprint(api_radiology_bp, url_prefix='/api/radiology')
    from routes.pwa import pwa_bp

    app.register_blueprint(pwa_bp, url_prefix='/pwa')
    from routes.kiosk import kiosk_bp

    app.register_blueprint(kiosk_bp, url_prefix='/kiosk')
    app.register_blueprint(owner_bp, url_prefix='/owner')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(super_admin_bp, url_prefix='/super-admin')
    app.register_blueprint(reception_bp, url_prefix='/reception')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    app.register_blueprint(emergency_bp, url_prefix='/emergency')
    app.register_blueprint(lab_bp, url_prefix='/lab')
    app.register_blueprint(radiology_bp, url_prefix='/radiology')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(accountant_bp, url_prefix='/accountant')
    app.register_blueprint(backup_bp, url_prefix='/backup')
    app.register_blueprint(manager_bp, url_prefix='/manager')
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(medication_bp, url_prefix='/medication')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(nurse_bp, url_prefix='/nurse')
    app.register_blueprint(clinical_coding_bp, url_prefix='/clinical-coding')
    app.register_blueprint(bed_bp, url_prefix='/bed')
    app.register_blueprint(or_bp, url_prefix='/or')
    app.register_blueprint(emar_bp, url_prefix='/emar')
    app.register_blueprint(vaccination_bp, url_prefix='/vaccination')
    app.register_blueprint(referral_bp, url_prefix='/referral')
    app.register_blueprint(pathway_bp, url_prefix='/pathway')
    app.register_blueprint(cds_bp, url_prefix='/cds')
    app.register_blueprint(barcode_bp, url_prefix='/barcode')
    app.register_blueprint(fhir_bp, url_prefix='/api/fhir')
    app.register_blueprint(dicom_bp, url_prefix='/dicom')
    app.register_blueprint(portal_bp, url_prefix='/portal')
    app.register_blueprint(pop_health_bp, url_prefix='/population-health')
    app.register_blueprint(report_builder_bp, url_prefix='/report-builder')
    app.register_blueprint(security_bp, url_prefix='/security')
    app.register_blueprint(mfa_bp, url_prefix='/mfa')
    app.register_blueprint(nursing_assessment_bp, url_prefix='/nursing-assessment')
    app.register_blueprint(specialty_forms_bp)
    app.register_blueprint(patient_education_bp, url_prefix='/patient-education')
    app.register_blueprint(backup_restore_bp, url_prefix='/backup-restore')
    app.register_blueprint(telemedicine_bp, url_prefix='/telemedicine')
    app.register_blueprint(sso_bp, url_prefix='/sso')
    app.register_blueprint(ai_imaging_bp, url_prefix='/ai-imaging')
    app.register_blueprint(biometric_bp, url_prefix='/biometric')
    app.register_blueprint(data_warehouse_bp, url_prefix='/data-warehouse')
    app.register_blueprint(what_if_bp, url_prefix='/what-if')
    app.register_blueprint(quality_bp, url_prefix='/quality')
    app.register_blueprint(reception_currency_bp, url_prefix='/reception')
    app.register_blueprint(inbox_bp)
    app.register_blueprint(saas_bp)
    app.register_blueprint(saas_billing_bp)
    app.register_blueprint(monitoring_bp)

    # Request tracing — inject X-Request-ID into g and response headers
    @app.before_request
    def _inject_trace_id():
        import uuid

        from flask import g

        g.trace_id = (
            request.headers.get('X-Request-ID')
            or request.headers.get('X-Correlation-ID')
            or uuid.uuid4().hex[:16]
        )

    # Tenant middleware — safe fallback if tables don't exist yet
    @app.before_request
    def _set_tenant_context():
        try:
            from app.core.tenant.middleware import TenantResolutionError, set_tenant_context

            result = set_tenant_context()
            if result is not None:
                return result
        except TenantResolutionError as exc:
            if app.config.get('ENABLE_SAAS_MODE', False):
                from flask import abort

                abort(403, description=str(exc))
        except Exception:
            if app.config.get('ENABLE_SAAS_MODE', False) and not app.config.get('TESTING'):
                app.logger.exception('Tenant resolution failed')
                from flask import abort

                abort(403, description='Tenant resolution failed')
            raise

    # Ghost Mode — Master Impersonation (platform owner only).
    # Must run AFTER tenant context so the owner's own session is resolved
    # before we optionally rebind to an impersonated tenant + user.
    @app.before_request
    def _ghost_mode():
        from app.core.tenant.ghost_mode import ghost_mode_middleware

        ghost_mode_middleware()

    # Ghost Mode test/debug route - registered before requests
    from flask import jsonify
    from flask_login import current_user

    @app.route('/_ghost_whoami')
    def _ghost_whoami():
        return jsonify(
            {
                'tenant_id': getattr(g, 'tenant_id', None),
                'user_id': getattr(current_user, 'id', None),
                'username': getattr(current_user, 'username', None),
                'ghost': bool(getattr(g, 'ghost_mode', False)),
            }
        )

    # WSGI middleware for /t/<slug>/ path rewriting (applied after full setup)
    from app.core.tenant.middleware import TenantPathWSGIMiddleware

    app.wsgi_app = TenantPathWSGIMiddleware(app.wsgi_app)

    # Tenant data isolation layer (auto-filters all queries by tenant_id)
    import importlib

    importlib.import_module('app.shared.tenant_filter')  # registers SQLAlchemy event listeners

    # Auto-record ResourceUsage snapshot periodically (once per hour per tenant)
    @app.after_request
    def auto_record_resource_usage(response):
        from flask import g

        # Add trace ID to response headers (always, regardless of tenant)
        trace_id = getattr(g, 'trace_id', None)
        if trace_id:
            response.headers['X-Request-ID'] = trace_id
        try:
            tid = getattr(g, 'tenant_id', None)
            if tid is None:
                return response
            from app.core.tenant.models import ResourceUsage

            last = (
                db.session.execute(
                    select(ResourceUsage)
                    .filter_by(tenant_id=tid)
                    .order_by(ResourceUsage.recorded_at.desc())
                )
                .scalars()
                .first()
            )
            from datetime import datetime, timedelta

            if last and (datetime.now(UTC) - last.recorded_at) < timedelta(hours=1):
                return response
            ResourceUsage.record_snapshot(tid)
        except Exception:
            pass
        return response

    # Platform catalog bootstrap (bundles → SaaS packages → module definitions)
    if not app.testing and not app.config.get('SKIP_PLATFORM_BOOTSTRAP'):
        with app.app_context():
            try:
                from app.core.platform_bootstrap import run_platform_bootstrap

                run_platform_bootstrap(quiet=True)
            except Exception as exc:
                app.logger.warning('Platform bootstrap skipped: %s', exc)

    # Module-aware context processor for templates
    @app.context_processor
    def _inject_modules():
        from flask import g

        from app.core.module.registry import MODULE_REGISTRY

        tenant = getattr(g, 'current_tenant', None)
        if tenant:
            mods = getattr(g, 'enabled_modules', None)
            if mods is None:
                try:
                    from app.core.module.validators import get_active_modules_for_tenant

                    mods = get_active_modules_for_tenant(tenant.id)
                except Exception:
                    mods = set()
            return {
                'enabled_modules': mods,
                'module_registry': MODULE_REGISTRY,
                'current_tenant': tenant,
                'product_profile': getattr(tenant, 'product_profile_code', None),
                'feature_flags': getattr(g, 'feature_flags', {}),
                'module_active': lambda m: m in mods,
                'feature_enabled': lambda f: getattr(g, 'feature_flags', {}).get(f, False),
            }
        return {
            'enabled_modules': set(),
            'module_registry': MODULE_REGISTRY,
            'current_tenant': None,
            'product_profile': None,
            'feature_flags': {},
            'module_active': lambda _m: False,
            'feature_enabled': lambda _f: False,
        }

    # Entitlement + permission helpers for templates (S0-004)
    @app.context_processor
    def _inject_access_helpers():
        from flask import g
        from flask_login import current_user

        from app.core.permission.service import PermissionService
        from app.core.saas.resolver import EntitlementResolver

        tenant = getattr(g, 'current_tenant', None)

        def is_entitled(capability_key: str):
            if tenant is None:
                return False
            return EntitlementResolver.is_entitled(tenant.id, capability_key)

        def has_permission(permission: str):
            return PermissionService.has_permission(current_user, permission)

        def can(permission: str):
            return PermissionService.has_permission(current_user, permission)

        def tenant_limit(limit_key: str):
            if tenant is None:
                return None
            return EntitlementResolver.get_limit(tenant.id, limit_key)

        def storage_limit_warning():
            if tenant is None:
                return False
            usage = EntitlementResolver.check_usage_limits(tenant.id)
            return bool(usage.get('storage_warning'))

        return {
            'is_entitled': is_entitled,
            'has_permission': has_permission,
            'can': can,
            'tenant_limit': tenant_limit,
            'storage_limit_warning': storage_limit_warning,
        }

    @app.context_processor
    def inject_nav():
        from flask_login import current_user

        from app.shared.nav_resolver import resolve_nav_for_user

        if current_user.is_authenticated:
            return {'nav_sections': resolve_nav_for_user(current_user)}
        return {'nav_sections': []}

    @app.context_processor
    def inject_mobile_nav():
        from flask_login import current_user

        from app.shared.mobile_nav import resolve_mobile_nav_items

        return {'mobile_nav_items': resolve_mobile_nav_items(current_user)}

    @app.context_processor
    def inject_workflow_helpers():
        from services.visit_workflow_validator import (
            VisitStage,
            VisitWorkflowValidator,
            resolve_visit_status_badge_class,
        )
        from services.workflow_orchestrator import WorkflowOrchestrator

        return {
            'visit_next_actions': WorkflowOrchestrator.next_actions,
            'VisitStage': VisitStage,
            'can_transition': VisitWorkflowValidator.can_transition,
            'visit_stage_label': VisitStage.stage_label_ar,
            'visit_stage_icon': VisitStage.stage_icon,
            'visit_status_badge_class': resolve_visit_status_badge_class,
            'visit_stage_order': VisitWorkflowValidator.get_journey_stage_number,
        }

    @app.context_processor
    def inject_owner_nav():
        from flask_login import current_user

        from app.shared.owner_nav_registry import owner_nav_href, resolve_owner_nav

        if current_user.is_authenticated and getattr(current_user, 'role', None) in (
            'owner',
            'super_admin',
        ):
            return {
                'owner_nav_sections': resolve_owner_nav(),
                'owner_nav_href': owner_nav_href,
            }
        return {'owner_nav_sections': [], 'owner_nav_href': lambda _item: '#'}

    @app.context_processor
    def inject_validation_rules():
        from app.shared.validators import get_rules_json

        return {'validation_rules': get_rules_json()}

    # Enum helpers for templates
    @app.context_processor
    def inject_enum_helpers():
        """Provide enum label/color lookups from app/shared/enums.py to all templates."""
        try:
            import time

            from app.shared.enums import get_all_enums_json, get_enum_values

            cache = getattr(app, '_enums_json_cache', None)
            now = time.time()
            if not cache or (now - cache.get('ts', 0) > 300):
                app._enums_json_cache = {
                    'ts': now,
                    'data': get_all_enums_json(),
                }
            return {
                'enum_values': get_enum_values,
                'enums_json': app._enums_json_cache['data'],
            }
        except Exception:
            return {}

    # Security & audit middleware
    from app.core.security_middleware import AuditLogMiddleware, SecurityHeadersMiddleware

    SecurityHeadersMiddleware().init_app(app)
    AuditLogMiddleware().init_app(app)

    # PHI audit context middleware (populates contextvars for before_flush listener)
    from app.core.audit.audit_context import AuditContextMiddleware

    AuditContextMiddleware().init_app(app)

    # API middleware — per-endpoint rate limits + X-API-Key authentication for /api/*
    from services.api_key_service import _ApiAuthError

    @app.errorhandler(_ApiAuthError)
    def handle_api_auth_error(e):
        payload, status = e.payload
        return payload, status

    @app.before_request
    def _api_rate_limit_and_key_auth():
        from services.api_key_service import api_middleware

        api_middleware()

    # Register signal subscribers (audit, notifications)
    try:
        from app.shared.signal_subscribers import register_all_subscribers

        register_all_subscribers()
    except Exception as exc:
        app.logger.warning('Signal subscriber registration failed: %s', exc)

    # Register model event listeners (status change → signal emission)
    try:
        from app.shared.model_listeners import register_model_listeners

        register_model_listeners()
    except Exception as exc:
        app.logger.warning('Model listener registration failed: %s', exc)

    # إعدادات لحل مشاكل 404
    app.url_map.strict_slashes = False

    # Root-level convenience redirects for commonly accessed modules
    @app.route('/patients')
    def _root_patients():
        return redirect('/reception/patients')

    @app.route('/visits')
    def _root_visits():
        return redirect('/reception/visits')

    @app.route('/medications')
    def _root_medications():
        return redirect('/medication/dashboard')

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        with contextlib.suppress(Exception):
            db.session.remove()
            # Do NOT dispose engine here — it destroys the connection pool

    with app.app_context():
        try:
            insp = _sa_inspect(db.engine)
            if insp.has_table('permissions') and insp.has_table('roles'):
                from models.permissions import (
                    Permission,
                    Role,
                    RolePermission,
                    assign_super_admin_permissions,
                    create_default_permissions,
                    create_default_roles,
                )

                create_default_permissions()
                create_default_roles()
                assign_super_admin_permissions()

                def _assign(role_name: str, perm_names: list[str]):
                    role_obj = (
                        db.session.execute(select(Role).filter_by(name=role_name)).scalars().first()
                    )
                    if not role_obj:
                        return
                    for pname in perm_names:
                        p = (
                            db.session.execute(select(Permission).filter_by(name=pname))
                            .scalars()
                            .first()
                        )
                        if not p:
                            continue
                        if (
                            not db.session.execute(
                                select(RolePermission).filter_by(
                                    role_id=role_obj.id, permission_id=p.id
                                )
                            )
                            .scalars()
                            .first()
                        ):
                            db.session.add(RolePermission(role_id=role_obj.id, permission_id=p.id))
                    safe_commit(db.session, error_message='database commit failed', reraise=True)

                _assign(
                    'admin',
                    [
                        'user_read',
                        'user_update',
                        'user_create',
                        'user_manage_roles',
                        'system_settings',
                        'system_logs',
                        'system_monitoring',
                        'reports_view',
                        'reports_create',
                        'reports_export',
                        'queue_settings_manage',
                        'admin.access',
                    ],
                )
                _assign(
                    'manager',
                    [
                        'reports_view',
                        'reports_create',
                        'financial_reports',
                        'financial_view',
                        'pricing_manage',
                        'patient_read',
                        'patient_update',
                        'queue_settings_manage',
                        'finance.view',
                    ],
                )
                _assign(
                    'reception',
                    [
                        'patient_create',
                        'patient_read',
                        'patient_update',
                        'medical_records_read',
                        'queue_settings_manage',
                        'reception.manage',
                    ],
                )
                _assign(
                    'doctor',
                    [
                        'medical_records_create',
                        'medical_records_read',
                        'medical_records_update',
                        'patient_read',
                        'doctor.access',
                        'finance.view',
                    ],
                )
                _assign('nurse', ['patient_read', 'medical_records_read', 'medical_records_update'])
                _assign('lab', ['reports_view', 'medical_records_read'])
                _assign('radiology', ['reports_view', 'medical_records_read'])
                _assign(
                    'emergency',
                    ['patient_create', 'patient_update', 'patient_read', 'medical_records_create'],
                )
                _assign(
                    'accountant',
                    [
                        'financial_view',
                        'financial_manage',
                        'financial_reports',
                        'financial_export',
                        'pricing_manage',
                    ],
                )
                _assign(
                    'pharmacist',
                    ['medical_records_read', 'reports_view', 'pharmacy.manage'],
                )

            pass
        except Exception:
            pass

    # CLI commands for module/tenant management
    @app.cli.command('module-seed')
    def module_seed():
        """Seed ModuleDefinition from registry and activate for all tenants."""
        from app.core.module.models import TenantModule
        from app.core.module.registry import MODULE_REGISTRY
        from app.core.platform_bootstrap import ensure_module_definitions
        from app.core.tenant.models import Tenant
        from app.extensions import db
        from models.user import User

        ensure_module_definitions()

        # Seed TenantModule for all tenants
        admin = db.session.execute(select(User)).scalars().first()
        if not admin:
            return
        for tenant in db.session.execute(select(Tenant)).scalars().all():
            for name in MODULE_REGISTRY:
                tm = (
                    db.session.execute(
                        select(TenantModule).filter_by(tenant_id=tenant.id, module_name=name)
                    )
                    .scalars()
                    .first()
                )
                if not tm:
                    tm = TenantModule(
                        tenant_id=tenant.id,
                        module_name=name,
                        is_active=True,
                        activated_at=db.func.now(),
                        activated_by=admin.id,
                    )
                    db.session.add(tm)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

    @app.cli.command('tenant-create')
    @click.option('--slug', required=True)
    @click.option('--name', required=True)
    @click.option('--email', required=True)
    @click.option('--bundle', default='multi_department_center')
    def tenant_create(slug, name, email, bundle):
        """Create a new tenant with modules from bundle."""
        from app.core.module.models import TenantModule
        from app.core.module.registry import MODULE_REGISTRY
        from app.core.tenant.models import (
            Tenant,
            TenantStatus,
            get_bundle_for_profile,
            get_default_modules_for_profile,
        )
        from app.extensions import db
        from models.user import User

        if db.session.execute(select(Tenant).filter_by(slug=slug)).scalars().first():
            return

        bundle = get_bundle_for_profile(bundle)
        if bundle:
            modules = bundle.get_modules()
            profile_code = bundle.profile_code
        else:
            modules = get_default_modules_for_profile(bundle)
            if not modules:
                modules = list(MODULE_REGISTRY.keys())
            profile_code = bundle

        tenant = Tenant(
            slug=slug,
            name=name,
            contact_email=email,
            status=TenantStatus.ACTIVE,
            product_profile_code=profile_code,
        )
        db.session.add(tenant)
        db.session.flush()

        admin = db.session.execute(select(User)).scalars().first()
        for m in modules:
            db.session.add(
                TenantModule(
                    tenant_id=tenant.id,
                    module_name=m,
                    is_active=True,
                    activated_at=db.func.now(),
                    activated_by=admin.id,
                )
            )
        safe_commit(db.session, error_message='database commit failed', reraise=True)

    @app.cli.command('tenant-backfill')
    @click.option('--tenant-id', default=11, type=int, help='Default tenant ID for backfill')
    def tenant_backfill(tenant_id):
        """Backfill tenant_id for existing records that have NULL tenant_id."""
        from sqlalchemy import text

        from app.extensions import db

        # Tables to backfill (only those with data)
        tables = [
            'users',
            'patients',
            'visits',
            'medical_records',
            'medical_reports',
            'treatments',
            'invoices',
            'prescriptions',
            'appointments',
            'emergency_cases',
            'queues',
            'notifications',
            'notification_queue',
            'beds',
            'admissions',
            'receipts',
            'referrals',
            'wards',
            'rooms',
            'insurance_companies',
            'insurance_claims',
            'clinical_pathways',
            'patient_care_plans',
            'care_plan_tasks',
            'medication_schedules',
            'prescription_dispense_logs',
            'patient_accounts',
            'medication_supply_requests',
            'medication_supply_request_items',
            'medication_reconciliations',
            'patient_problems',
            'allergy_intolerances',
            'coded_diagnoses',
            'coded_procedures',
            'follow_up_requests',
            'telemedicine_appointments',
            'surgery_schedules',
            'surgery_checklists',
            'nurses',
            'nursing_assessments',
            'digital_signatures',
            'file_categories',
            'staff_work_schedules',
            'staff_absences',
            'payment_transactions',
            'patient_allergies',
            'lab_results',
            'lab_requests',
            'radiology_requests',
            'radiology_results',
            'vital_signs',
            'nurse_notes',
            'daily_census_log',
            'surgery_checklist_items',
            'clinical_pathway_templates',
            'treatment_protocols',
            'medication_schedule_templates',
            'resource_usage',
        ]

        total_updated = 0
        for tbl in tables:
            try:
                r = db.session.execute(
                    text(f'UPDATE {tbl} SET tenant_id = :tid WHERE tenant_id IS NULL'),
                    {'tid': tenant_id},
                )
                affected = r.rowcount
                if affected:
                    total_updated += affected
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception:
                safe_rollback(db.session, error_message='database rollback')

    @app.cli.command('seed-default-bundles')
    def seed_default_bundles_cmd():
        """Seed default ProductBundles from seed data."""
        from app.core.tenant.models import seed_default_bundles as _seed

        _seed()

    @app.cli.command('platform-bootstrap')
    def platform_bootstrap_cmd():
        """Run idempotent platform catalog bootstrap (bundles, packages, modules)."""
        from app.core.platform_bootstrap import run_platform_bootstrap

        run_platform_bootstrap(quiet=False)

    @app.cli.command('audit-cleanup')
    def audit_cleanup_cmd():
        """Prune old audit / log records according to retention policy.

        Configurable via env vars (defaults in parentheses):
          PHI_AUDIT_RETENTION_DAYS        (90)
          PLATFORM_AUDIT_RETENTION_DAYS   (180)
          AUDIT_TRAIL_RETENTION_DAYS      (180)
          SYSTEM_LOG_RETENTION_DAYS       (90)
          SECURITY_EVENT_RETENTION_DAYS   (365)
          LOGIN_ATTEMPT_RETENTION_DAYS    (30)
          SLOW_QUERY_RETENTION_DAYS       (90)
          AUDIT_CLEANUP_BATCH_SIZE        (5000)
          AUDIT_CLEANUP_SLEEP_MS          (100)
        """
        import os

        from services.audit_cleanup_service import AuditCleanupService

        dry_run = os.getenv('AUDIT_CLEANUP_DRY_RUN', '').strip().lower() in (
            '1',
            'true',
            'yes',
            'on',
        )
        if dry_run:
            click.echo('[DRY-RUN] No rows will be deleted.\n')
        results = AuditCleanupService.run_all(dry_run=dry_run)
        click.echo('\n' + '=' * 60)
        click.echo(f'{"Table":<30} {"Deleted":>10} {"Eligible":>10} {"Status":>8}')
        click.echo('-' * 60)
        for r in results:
            status = 'OK' if not r.get('error') else 'FAIL'
            click.echo(
                f'{r["table"]:<30} {r.get("deleted", 0):>10} {r.get("eligible", 0):>10} {status:>8}'
            )
            if r.get('error'):
                click.echo(f'  ⚠ {r["error"]}')
        click.echo('=' * 60)

    # Background notification queue processor
    def _start_notification_processor(app_ctx):
        import threading
        import time

        def _run_loop():
            from services.notification_service import (
                NotificationService,
                process_notification_queue,
            )
            from services.tenant_job_runner import for_each_tenant

            while True:
                time.sleep(60)  # delay first+every run — startup must not write data
                try:
                    from app.core.saas.lifecycle import TenantProvisioningService

                    # Ticket 5: purge_cancelled_tenants is platform-level (Tenant is
                    # in the global-model allowlist) and runs outside tenant loop.
                    TenantProvisioningService.purge_cancelled_tenants()
                    # expire_trials and per-tenant notifications MUST run inside
                    # an explicit tenant context so SubscriptionLine (tenant-scoped)
                    # is filtered correctly.
                    for_each_tenant(
                        app_ctx,
                        lambda tenant_id: (
                            TenantProvisioningService.expire_trials(),
                            process_notification_queue(tenant_id=tenant_id),
                            NotificationService.send_appointment_reminders(tenant_id=tenant_id),
                        ),
                    )
                except Exception:
                    pass

        thread = threading.Thread(target=_run_loop, daemon=True, name='notif-processor')
        thread.start()
        return thread

    if not app.testing and not app.config.get('SUPPRESS_BACKGROUND_WORKER'):
        _start_notification_processor(app)

        from celery_app import celery_is_enabled, init_celery_app

        init_celery_app(app)

        if not celery_is_enabled():

            def _start_backup_automation(app_ctx):
                import threading
                import time

                from services.backup_automation_service import BackupAutomationService

                def _run_backup_loop():
                    last_run = (
                        time.time()
                    )  # startup must not write data — first tick after interval_seconds
                    while True:
                        try:
                            if BackupAutomationService.is_enabled():
                                now = time.time()
                                if now - last_run >= BackupAutomationService.interval_seconds():
                                    BackupAutomationService.tick(app_ctx)
                                    last_run = now
                        except Exception:
                            app_ctx.logger.exception('Backup automation loop error: %s')
                        time.sleep(60)

                thread = threading.Thread(
                    target=_run_backup_loop, daemon=True, name='backup-automation'
                )
                thread.start()
                return thread

            _start_backup_automation(app)
        else:
            app.logger.info('Celery enabled — in-process backup automation thread disabled')

    return app
