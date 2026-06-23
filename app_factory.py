"""
مصنع التطبيق - Application Factory (منقح ومتوافق مع الموديلات الحالية)
"""
from flask import Flask, jsonify, render_template_string, render_template, redirect, url_for, request, abort
from flask.json.provider import DefaultJSONProvider
from decimal import Decimal, ROUND_HALF_UP
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
import os, logging, click
from logging.handlers import RotatingFileHandler
from sqlalchemy import inspect as _sa_inspect
from logging import StreamHandler
from datetime import datetime
from pathlib import Path
from datetime import datetime as _dt

# إنشاء كائنات Flask
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
socketio = SocketIO(async_mode="threading")

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
    config_name = config_name or os.getenv("APP_ENV", "development")
    app.config.from_object(app_config.get(config_name, app_config["default"]))
    
    if (app_config.get(config_name, app_config["default"]).__name__ == 'TestingConfig'
        or os.getenv('APP_ENV') == 'testing'
        or os.getenv('SUPPRESS_DEPRECATION_WARNINGS') in {'1','true','yes','on'}):
        try:
            import warnings
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            if os.getenv('SUPPRESS_LOGGING') in {'1','true','yes','on'} or app.testing:
                logging.disable(logging.CRITICAL)
        except Exception:
            pass

    # تحكم بمستوى اللوجينغ عبر متغير LOG_LEVEL (DEBUG/INFO/WARNING/ERROR)
    log_level_name = os.environ.get("LOG_LEVEL", "DEBUG" if os.environ.get("FLASK_DEBUG") == "1" else "INFO")
    log_level = getattr(logging, log_level_name.upper(), logging.DEBUG)
    app.logger.setLevel(log_level)

    # إعداد Handlers: كونسول + ملف دوّار logs/app.log (معطّل في الاختبار)
    logs_dir = Path(app.root_path).joinpath("logs")
    try:
        logs_dir.mkdir(exist_ok=True)
        if not app.testing:
            file_handler = RotatingFileHandler(logs_dir / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
            file_handler.setLevel(log_level)
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s [in %(pathname)s:%(lineno)d]",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
    except Exception:
        pass  # لا نكسر التطبيق لو فشل إنشاء المجلد/الملف

    console_handler = StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    app.logger.addHandler(console_handler)

    # إظهار تتبعات أوضح في التطوير
    if os.environ.get("FLASK_DEBUG") == "1":
        app.config["PROPAGATE_EXCEPTIONS"] = True
        app.config["TRAP_HTTP_EXCEPTIONS"] = True
        app.config["TRAP_BAD_REQUEST_ERRORS"] = True

    # SQLAlchemy echo من env (لطباعة الاستعلامات في الكونسول)
    echo_env = os.environ.get("SQLALCHEMY_ECHO", "").strip().lower()
    app.config["SQLALCHEMY_ECHO"] = echo_env in {"1", "true", "yes", "on"}

    # تهيئة الإضافات
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)

    def _get_format_map():
        try:
            from models.system_config import SystemConfig
            df = None
            tf = None
            dcfg = SystemConfig.query.filter_by(config_key="date_format").first()
            if dcfg:
                df = str(dcfg.config_value).lower()
            tcfg = SystemConfig.query.filter_by(config_key="time_format").first()
            if tcfg:
                tf = str(tcfg.config_value).lower()
        except Exception:
            df = None
            tf = None
        date_map = {
            'dd/mm/yyyy': '%d/%m/%Y',
            'mm/dd/yyyy': '%m/%d/%Y',
            'yyyy-mm-dd': '%Y-%m-%d'
        }
        time_map = {
            'hh:mm': '%H:%M',
            'hh:mm:ss': '%H:%M:%S'
        }
        dfmt = date_map.get(df or 'yyyy-mm-dd')
        tfmt = time_map.get(tf or 'hh:mm')
        return dfmt, tfmt, f"{dfmt} {tfmt}"

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
            return (val if hasattr(val, 'strftime') else _dt.fromisoformat(str(val))).strftime(dfull)
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
            return f"{q:.2f} {cur}"
        except Exception:
            return f"{amount} {currency or app.config.get('DEFAULT_CURRENCY', 'ILS')}"
    app.jinja_env.filters['format_money'] = _fmt_money

    from app.shared.enum_labels import enum_label
    app.jinja_env.filters['enum_label'] = enum_label

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
            # استيراد النماذج الأساسية أولاً
            import models.department
            import models.user
            import models.patient
            import models.visit
            import models.treatment
            import models.appointment
            import models.payment
            import models.invoice
            import models.lab_request
            import models.radiology_request
            import models.medical_report
            import models.service
            import models.insurance
            # استيراد النماذج المتقدمة
            import models.audit_trail
            import models.system_config
            import models.permissions
            import models.notification
            import models.branding
            import models.dental
            import models.cash_register
            import models.budget
            import models.nurse
            import models.queue_management
            import models.pricing_management
            import models.reporting
            # نماذج إضافية لضمان اكتمال تسجيل الـ metadata
            import models.medication
            import models.emergency
            import models.backup
            import models.receipt
            import models.pricing
            import models.radiology_result
            import models.whatsapp_integration
            import models.file_management
            import models.online_booking
            import models.patient_account
            import models.patient_visit_counter
            import models.relationships_map
            import models.request_workflow
            import models.task_management
            import models.workflow
            import models.ai_analytics
            import models.advanced_permissions
            import models.follow_up
            import models.drug_interaction
            import models.supply_request
            import models.user_department_access
            import models.visit_transfer
            import models.emergency_status_history
            import models.lab_quality
            import models.lab_reagent
            import models.lab_test_catalog
            import models.exchange_rate
            import models.specialty_form
        except Exception as e:
            app.logger.warning(f"Model import registration skipped: {e}")

        # Note: Tests call db.create_all() in their setUp, so we don't call it here

    login_manager.login_view = "auth.login"
    login_manager.login_message = "الرجاء تسجيل الدخول أولاً."
    login_manager.session_protection = "strong"
    
    @login_manager.user_loader
    def load_user(user_id):
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
        user = db.session.get(User, uid)
        if not user:
            return None
        actual_version = int(getattr(user, 'session_version', 0) or 0)
        if actual_version != expected_version:
            return None
        return user

    # السجلات الدوّارة (تمت في البداية)
    if not app.debug and not app.testing:
        os.makedirs("logs", exist_ok=True)
        # RotatingFileHandler already set up above — skip duplicate
        app.logger.setLevel(logging.INFO)

    # Health
    @app.get("/__health")
    def __health():
        return jsonify(status="ok")

    # ping endpoint للتشخيص
    @app.get("/__ping")
    def __ping():
        return "pong", 200

    @app.get("/favicon.ico")
    def favicon():
        return redirect(url_for('static', filename='img/azad_logo.png'), code=302)

    # استعراض المسارات (للتسهيل أثناء التطوير)
    @app.get("/__routes")
    def list_routes():
        if app.config.get('DISABLE_DEBUG_ENDPOINTS', True):
            abort(404)
        rows = []
        for r in app.url_map.iter_rules():
            methods = ",".join(sorted(m for m in r.methods if m in {"GET","POST","PUT","PATCH","DELETE"}))
            rows.append(f"<div class='route'><b>{r.rule}</b> &nbsp; <small>{methods}</small> → <code>{r.endpoint}</code></div>")
        html = """
        <html dir="rtl" lang="ar"><head><meta charset="utf-8">
        <style>body{{font-family:Arial;padding:20px}}.route{{background:#eef;padding:8px;margin:5px;border-right:4px solid #39f}}</style>
        </head><body><h3>قائمة المسارات</h3>{rows}</body></html>""".format(rows="".join(rows))
        return render_template_string(html)

    # معالجات الأخطاء القياسية لربط قوالب الأخطاء
    @app.errorhandler(403)
    def handle_403(error):
        try:
            return render_template('errors/403.html'), 403
        except Exception:
            return jsonify(error="لا يمكن عرض الصفحة حالياً"), 403

    @app.errorhandler(404)
    def handle_404(error):
        try:
            return render_template('errors/404.html'), 404
        except Exception:
            return jsonify(error="الصفحة غير متاحة حالياً"), 404

    @app.errorhandler(500)
    def handle_500(error):
        try:
            return render_template('errors/500.html'), 500
        except Exception:
            return jsonify(error="تعذر تنفيذ الطلب حالياً"), 500

    # تهيئة بيانات افتراضية (محميّة ضد غياب الجداول أثناء أوامر Alembic)
    with app.app_context():
        try:
            insp = _sa_inspect(db.engine)
            if insp.has_table("system_configs"):
                from models.system_config import SystemConfig
                cfg = SystemConfig.query.filter_by(config_key="log_level").first()
                if cfg and cfg.config_value:
                    lvl = getattr(logging, str(cfg.config_value).upper(), None)
                    if isinstance(lvl, int):
                        app.logger.setLevel(lvl)
                        for h in app.logger.handlers:
                            h.setLevel(lvl)
                # تهيئة معلومات شركة البرمجة والمبرمج
                defaults = [
                    {"key": "developer_company", "value": "شركة آزاد للأنظمة الذكية", "type": "string"},
                    {"key": "developer_name", "value": "المهندس أحمد غنام", "type": "string"},
                    {"key": "developer_logo_url", "value": "", "type": "string"},
                    {"key": "developer_mobile", "value": "+ --------", "type": "string"},
                    {"key": "developer_location", "value": "رام الله - فلسطين", "type": "string"}
                ]
                for d in defaults:
                    if not SystemConfig.query.filter_by(config_key=d["key"]).first():
                        sc = SystemConfig(config_key=d["key"], config_value=d["value"], config_type=d["type"], category="general", is_system=True)
                        db.session.add(sc)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            if insp.has_table("users"):
                from models.user import User
                # من الآمن استيراد Department فقط عند الحاجة
                # from models.department import Department
                pass

                pass
            else:
                app.logger.info("جدول users غير موجود بعد؛ سيتم تخطّي إنشاء الأدمن حتى إكمال الترحيلات.")
        except Exception as e:
            # لا نُفشل التطبيق أثناء أوامر Alembic
            app.logger.warning(f"تخطّي تهيئة البيانات الافتراضية: {e}")

    # إيقاف الإنشاء التلقائي لأي جدول في التطوير لضمان هجرة احترافية فقط عبر Alembic
    # يمكن تفعيلها لاحقًا يدويًا عبر متغير بيئة DEV_CREATE_TREATMENTS=1 إن لزم
    with app.app_context():
        try:
            if app.debug and os.getenv('DEV_CREATE_TREATMENTS', '0') == '1':
                insp = _sa_inspect(db.engine)
                from models.treatment import Treatment
                if not insp.has_table(Treatment.__tablename__):
                    Treatment.__table__.create(db.engine, checkfirst=True)
                    app.logger.info("✅ تم إنشاء جدول treatments تلقائياً في وضع التطوير")
        except Exception as e:
            app.logger.warning(f"Failed to auto-create treatments table: {e}")

    # تزويد القوالب بمتغيرات العلامة التجارية ومعلومات المطور
    @app.context_processor
    def inject_branding():
        try:
            import time
            from flask import g
            from app.shared.branding_context import build_branding_payload

            tenant = getattr(g, 'current_tenant', None)
            cache_key = f'tenant:{tenant.id}' if tenant and getattr(tenant, 'id', None) else 'platform'
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
            return caches[cache_key]['data']
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

    # تسجيل الـ blueprints المتاحة فقط
    from routes.main import main_bp
    from routes.auth_routes import auth_bp
    from routes.super_admin import super_admin_bp
    from routes.reception import reception_bp
    from routes.doctor import doctor_bp
    from routes.emergency import emergency_bp
    from routes.lab import lab_bp
    from routes.radiology import radiology_bp
    from routes.finance import finance_bp
    from routes.accountant import accountant_bp
    from routes.backup_routes import backup_bp
    from routes.manager import manager_bp
    # from routes.ai_routes import ai_bp  # REMOVED - AI now integrated in super_admin
    from routes.booking_routes import booking_bp
    from routes.medication_routes import medication_bp
    from routes.payment_routes import payment_bp
    from routes.nurse_routes import nurse_bp
    from app.modules.owner import owner_bp
    from routes.clinical_coding import clinical_coding_bp
    from routes.bed_management_routes import bed_bp
    from routes.or_management_routes import or_bp
    from routes.emar_routes import emar_bp
    from routes.vaccination_routes import vaccination_bp
    from routes.referral_routes import referral_bp
    from routes.clinical_pathway_routes import pathway_bp
    from routes.cds_alert_routes import cds_bp
    from routes.barcode_routes import barcode_bp
    from routes.fhir_api_routes import fhir_bp
    from routes.dicom_routes import dicom_bp
    from routes.patient_portal import portal_bp
    from routes.population_health_routes import pop_health_bp
    from routes.custom_report_builder_routes import report_builder_bp
    from routes.security_advanced_routes import security_bp
    from routes.mfa_routes import mfa_bp
    from routes.nursing_assessment_routes import nursing_assessment_bp
    from routes.patient_education_routes import patient_education_bp
    from routes.backup_restore_routes import backup_restore_bp
    from routes.telemedicine_routes import telemedicine_bp
    from routes.sso_routes import sso_bp
    from routes.ai_imaging_routes import ai_imaging_bp
    from routes.biometric_routes import biometric_bp
    from routes.data_warehouse_routes import data_warehouse_bp
    from routes.what_if_routes import what_if_bp
    from routes.quality_compliance import quality_bp
    from routes.reception_currency import reception_currency_bp
    from routes.inbox import inbox_bp
    from routes.specialty_forms import specialty_forms_bp

    # Module guards — must be added BEFORE register_blueprint, and only ONCE
    def _guard_factory(module_name):
        def _guard():
            from flask import g, abort
            from werkzeug.exceptions import HTTPException
            if not app.config.get('ENABLE_SAAS_MODE', False):
                return None
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                abort(403, description="Tenant context is required in SaaS mode.")
            try:
                # Use cached enabled_modules from g (set by set_tenant_context)
                enabled = getattr(g, 'enabled_modules', None)
                if enabled is None or module_name not in enabled:
                    from app.core.module.validators import get_active_modules_for_tenant
                    enabled = get_active_modules_for_tenant(tenant.id)
                    g.enabled_modules = enabled
                if module_name not in enabled:
                    abort(403, description=f"Module '{module_name}' is not activated for this tenant.")
            except HTTPException:
                raise
            except Exception as exc:
                app.logger.exception("Module guard failed for %s", module_name)
                abort(403, description=str(exc))
        return _guard

    def _add_guard_once(bp, module_name):
        if not getattr(bp, '_module_guard_added', False):
            bp.before_request(_guard_factory(module_name))
            bp._module_guard_added = True

    # Helper: allow routes to check module access programmatically
    @app.context_processor
    def _inject_module_helpers():
        def module_active(name):
            return name in getattr(g, 'enabled_modules', set())
        return dict(module_active=module_active)

    @app.context_processor
    def _inject_tenant_url_for():
        """Provide tenant_url_for() that prefixes /t/<slug>/ in SaaS mode."""
        from flask import url_for, g
        def tenant_url_for(endpoint, **values):
            if not app.config.get('ENABLE_SAAS_MODE', False):
                return url_for(endpoint, **values)
            tenant_slug = getattr(g, 'tenant_slug', None)
            if not tenant_slug:
                return url_for(endpoint, **values)
            url = url_for(endpoint, **values)
            if not url.startswith('/'):
                return url
            if url.startswith('/t/') or url.startswith('/static/'):
                return url
            if url.startswith('/owner/') or url.startswith('/super-admin/') or url.startswith('/auth/'):
                return url
            return f'/t/{tenant_slug}{url}'
        return dict(tenant_url_for=tenant_url_for)

    _add_guard_once(reception_bp, "reception")
    _add_guard_once(doctor_bp, "doctor")
    _add_guard_once(lab_bp, "lab")
    _add_guard_once(radiology_bp, "radiology")
    _add_guard_once(emergency_bp, "emergency")
    _add_guard_once(nurse_bp, "nursing")
    _add_guard_once(finance_bp, "billing")
    _add_guard_once(accountant_bp, "billing")
    _add_guard_once(manager_bp, "reporting")
    _add_guard_once(booking_bp, "appointments")
    _add_guard_once(medication_bp, "pharmacy")
    # Additional module guards for orphan blueprints
    _add_guard_once(payment_bp, "billing")
    _add_guard_once(emar_bp, "nursing")
    _add_guard_once(pathway_bp, "doctor")
    _add_guard_once(report_builder_bp, "reporting")
    _add_guard_once(data_warehouse_bp, "reporting")
    _add_guard_once(pop_health_bp, "reporting")
    _add_guard_once(quality_bp, "reporting")
    _add_guard_once(what_if_bp, "reporting")
    _add_guard_once(portal_bp, "portal")
    _add_guard_once(dicom_bp, "radiology")
    _add_guard_once(ai_imaging_bp, "ai_imaging")
    _add_guard_once(barcode_bp, "inventory")
    _add_guard_once(clinical_coding_bp, "doctor")
    _add_guard_once(vaccination_bp, "doctor")
    _add_guard_once(referral_bp, "doctor")
    _add_guard_once(cds_bp, "doctor")
    _add_guard_once(patient_education_bp, "doctor")
    _add_guard_once(telemedicine_bp, "doctor")
    _add_guard_once(bed_bp, "nursing")
    _add_guard_once(or_bp, "nursing")
    _add_guard_once(nursing_assessment_bp, "nursing")
    _add_guard_once(specialty_forms_bp, "doctor")
    _add_guard_once(sso_bp, "integration")
    _add_guard_once(reception_currency_bp, "reception")
    _add_guard_once(fhir_bp, "integration")

    app.register_blueprint(main_bp)
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

    # Tenant middleware — safe fallback if tables don't exist yet
    @app.before_request
    def _set_tenant_context():
        try:
            from app.core.tenant.middleware import set_tenant_context
            set_tenant_context()
        except Exception:
            if app.config.get('ENABLE_SAAS_MODE', False):
                app.logger.exception("Tenant resolution failed")
                from flask import abort
                abort(403, description="Tenant resolution failed")
            # Tenant tables may not exist yet in standalone mode.
            pass

    # WSGI middleware for /t/<slug>/ path rewriting (applied after full setup)
    from app.core.tenant.middleware import TenantPathWSGIMiddleware
    app.wsgi_app = TenantPathWSGIMiddleware(app.wsgi_app)

    # Tenant data isolation layer (auto-filters all queries by tenant_id)
    import importlib
    importlib.import_module('app.shared.tenant_filter')  # registers SQLAlchemy event listeners

    # Auto-record ResourceUsage snapshot periodically (once per hour per tenant)
    @app.after_request
    def auto_record_resource_usage(response):
        try:
            tid = getattr(g, 'tenant_id', None)
            if tid is None:
                return response
            from app.core.tenant.models import ResourceUsage
            last = ResourceUsage.query.filter_by(tenant_id=tid)\
                .order_by(ResourceUsage.recorded_at.desc()).first()
            from datetime import datetime, timedelta, timezone
            if last and (datetime.now(timezone.utc) - last.recorded_at) < timedelta(hours=1):
                return response
            ResourceUsage.record_snapshot(tid)
        except Exception:
            pass
        return response

    # Auto-seed default ProductBundles if table exists and is empty
    with app.app_context():
        try:
            from sqlalchemy import inspect
            if 'product_bundles' in inspect(db.engine).get_table_names():
                count = db.session.execute(db.text('SELECT COUNT(*) FROM product_bundles')).scalar()
                if count == 0:
                    from app.core.tenant.models import seed_default_bundles
                    seed_default_bundles()
        except Exception:
            pass

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
        return {'enabled_modules': set(), 'module_registry': MODULE_REGISTRY, 'current_tenant': None, 'product_profile': None, 'feature_flags': {}, 'module_active': lambda m: False, 'feature_enabled': lambda f: False}

    # Entitlement + permission helpers for templates (S0-004)
    @app.context_processor
    def _inject_access_helpers():
        from flask import g
        from app.core.saas.resolver import EntitlementResolver
        from app.core.permission.service import PermissionService
        from flask_login import current_user

        tenant = getattr(g, 'current_tenant', None)

        def is_entitled(capability_key: str):
            if tenant is None:
                return False
            return EntitlementResolver.is_entitled(tenant.id, capability_key)

        def has_permission(permission: str):
            return PermissionService.has_permission(current_user, permission)

        def can(permission: str):
            return PermissionService.has_permission(current_user, permission)

        return dict(is_entitled=is_entitled, has_permission=has_permission, can=can)

    @app.context_processor
    def inject_nav():
        from flask_login import current_user
        from app.shared.nav_resolver import resolve_nav_for_user
        if current_user.is_authenticated:
            return {'nav_sections': resolve_nav_for_user(current_user)}
        return {'nav_sections': []}

    # Enum helpers for templates
    @app.context_processor
    def inject_enum_helpers():
        """Provide enum label/color lookups from app/shared/enums.py to all templates."""
        try:
            from app.shared.enums import get_enum_values, get_all_enums_json
            import time
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
    from app.core.security_middleware import SecurityHeadersMiddleware, AuditLogMiddleware
    SecurityHeadersMiddleware().init_app(app)
    AuditLogMiddleware().init_app(app)

    # Register signal subscribers (audit, notifications)
    try:
        from app.shared.signal_subscribers import register_all_subscribers
        register_all_subscribers()
    except Exception as exc:
        app.logger.warning("Signal subscriber registration failed: %s", exc)

    # Register model event listeners (status change → signal emission)
    try:
        from app.shared.model_listeners import register_model_listeners
        register_model_listeners()
    except Exception as exc:
        app.logger.warning("Model listener registration failed: %s", exc)

    # إعدادات لحل مشاكل 404
    app.url_map.strict_slashes = False
    @app.get("/__perf/finance")
    def __perf_finance():
        if app.config.get('DISABLE_PERF_ENDPOINTS', True):
            abort(404)
        import re, time
        from flask import request, jsonify, render_template_string
        tc = app.test_client()
        threshold_ms = int(request.args.get("threshold_ms", "800") or "800")
        repeat = int(request.args.get("repeat", "1") or "1")
        base_paths = ["/finance/dashboard","/finance/payments","/finance/invoices","/finance/audit","/payment/dashboard","/accountant/dashboard","/accountant/reports","/accountant/financial","/payment/reports"]
        extra = request.args.get("paths") or ""
        if extra:
            for it in extra.split(","):
                it = it.strip()
                if it:
                    base_paths.append(it)
        include_json = (request.args.get("include_json") or "0").lower() in {"1","true","yes","on"}
        status = {}
        slow = []
        max_ms = 0
        for p in base_paths:
            times = []
            code = 0
            for _ in range(max(1, repeat)):
                t0 = time.perf_counter()
                r = tc.get(p, follow_redirects=True)
                dt = int((time.perf_counter() - t0) * 1000)
                code = r.status_code
                times.append(dt)
            avg = int(sum(times) / len(times))
            max_ms = max(max_ms, avg)
            entry = {"code": code, "ms": avg}
            status[p] = entry
            if avg > threshold_ms or code != 200:
                slow.append({"path": p, "code": code, "ms": avg})
        if include_json:
            json_endpoints = [
                ("/finance/post", {}),
            ]
            for ep, payload in json_endpoints:
                times = []
                code = 0
                for _ in range(max(1, repeat)):
                    t0 = time.perf_counter()
                    r = tc.post(ep, json=payload, follow_redirects=False)
                    dt = int((time.perf_counter() - t0) * 1000)
                    code = r.status_code
                    times.append(dt)
                avg = int(sum(times) / len(times))
                max_ms = max(max_ms, avg)
                status[ep] = {"code": code, "ms": avg}
                if avg > threshold_ms or code not in (200, 400, 422):
                    slow.append({"path": ep, "code": code, "ms": avg})
        result = {
            "threshold_ms": threshold_ms,
            "repeat": repeat,
            "status": status,
            "alerts": {"slow": slow, "max_ms": max_ms, "ok_count": sum(1 for v in status.values() if v["code"] == 200 and v["ms"] <= threshold_ms)},
            "overall": ("degraded" if slow else "ok")
        }
        if result["overall"] == "degraded":
            try:
                app.logger.warning(f"Perf degraded: threshold={threshold_ms} slow={slow}")
            except Exception:
                pass
        if (request.args.get("format") or "").lower() == "html":
            rows = []
            for path, entry in status.items():
                is_slow = entry["ms"] > threshold_ms or entry["code"] != 200
                rows.append(f"<tr class='{'slow' if is_slow else ''}'><td>{path}</td><td>{entry['code']}</td><td>{entry['ms']} ms</td></tr>")
            html = """
            <html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
            body{{font-family:Arial;padding:20px;background:#f7f7fb}}
            table{{width:100%;border-collapse:collapse;background:#fff}}
            th,td{{border:1px solid #ddd;padding:8px;text-align:right}}
            th{{background:#eef}}
            tr.slow{{background:#ffecec}}
            .badge{{display:inline-block;padding:6px 10px;border-radius:12px}}
            .ok{{background:#d4edda;color:#155724}}
            .degraded{{background:#fff3cd;color:#856404}}
            </style></head><body>
            <h3>قياس الأداء</h3>
            <div class='badge {state}'>{state_label}</div>
            <div>العتبة: {thr} ms &nbsp; التكرار: {rep}</div>
            <table><thead><tr><th>المسار</th><th>الكود</th><th>الزمن</th></tr></thead><tbody>{rows}</tbody></table>
            </body></html>
            """.format(rows="".join(rows), thr=threshold_ms, rep=repeat, state=("degraded" if slow else "ok"), state_label=("منخفض" if not slow else "متدهور"))
            return render_template_string(html)
        return jsonify(result)

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
        try:
            db.session.remove()
            # Do NOT dispose engine here — it destroys the connection pool
        except Exception:
            pass

    with app.app_context():
        try:
            insp = _sa_inspect(db.engine)
            if insp.has_table("permissions") and insp.has_table("roles"):
                from models.permissions import create_default_permissions, create_default_roles, assign_super_admin_permissions, Role, Permission, RolePermission
                create_default_permissions()
                create_default_roles()
                assign_super_admin_permissions()

                def _assign(role_name: str, perm_names: list[str]):
                    role_obj = Role.query.filter_by(name=role_name).first()
                    if not role_obj:
                        return
                    for pname in perm_names:
                        p = Permission.query.filter_by(name=pname).first()
                        if not p:
                            continue
                        if not RolePermission.query.filter_by(role_id=role_obj.id, permission_id=p.id).first():
                            db.session.add(RolePermission(role_id=role_obj.id, permission_id=p.id))
                    db.session.commit()

                _assign('admin', ['user_read','user_update','user_create','user_manage_roles','system_settings','system_logs','system_monitoring','reports_view','reports_create','reports_export','queue_settings_manage'])
                _assign('manager', ['reports_view','reports_create','financial_reports','financial_view','pricing_manage','patient_read','patient_update','queue_settings_manage'])
                _assign('reception', ['patient_create','patient_read','patient_update','medical_records_read','queue_settings_manage'])
                _assign('doctor', ['medical_records_create','medical_records_read','medical_records_update','patient_read'])
                _assign('nurse', ['patient_read','medical_records_read','medical_records_update'])
                _assign('lab', ['reports_view','medical_records_read'])
                _assign('radiology', ['reports_view','medical_records_read'])
                _assign('emergency', ['patient_create','patient_update','patient_read','medical_records_create'])
                _assign('accountant', ['financial_view','financial_manage','financial_reports','financial_export','pricing_manage'])
                _assign('pharmacist', ['medical_records_read','reports_view'])

            pass

            pass
        except Exception:
            pass

    # CLI commands for module/tenant management
    @app.cli.command("module-seed")
    def module_seed():
        """Seed ModuleDefinition from registry and activate for all tenants."""
        from app.core.module.models import ModuleDefinition, TenantModule
        from app.core.module.registry import MODULE_REGISTRY
        from app.core.tenant.models import Tenant
        from app.extensions import db
        from models.user import User
        
        # Seed ModuleDefinition
        for name, meta in MODULE_REGISTRY.items():
            m = ModuleDefinition.query.filter_by(name=name).first()
            if not m:
                m = ModuleDefinition(name=name, name_ar=meta.name_ar, category=meta.category, 
                                     description=meta.description_ar, is_active=True)
                db.session.add(m)
        db.session.commit()
        print(f"ModuleDefinition: {ModuleDefinition.query.count()} modules")

        # Seed TenantModule for all tenants
        admin = User.query.first()
        if not admin:
            print("No admin user found")
            return
        for tenant in Tenant.query.all():
            for name in MODULE_REGISTRY.keys():
                tm = TenantModule.query.filter_by(tenant_id=tenant.id, module_name=name).first()
                if not tm:
                    tm = TenantModule(tenant_id=tenant.id, module_name=name, is_active=True,
                                      activated_at=db.func.now(), activated_by=admin.id)
                    db.session.add(tm)
        db.session.commit()
        print(f"TenantModule seeded for {Tenant.query.count()} tenants")

    @app.cli.command("tenant-create")
    @click.option("--slug", required=True)
    @click.option("--name", required=True)
    @click.option("--email", required=True)
    @click.option("--bundle", default="multi_department_center")
    def tenant_create(slug, name, email, bundle):
        """Create a new tenant with modules from bundle."""
        from app.core.tenant.models import Tenant, TenantStatus, get_bundle_for_profile, get_default_modules_for_profile
        from app.core.module.models import TenantModule
        from app.core.module.registry import MODULE_REGISTRY
        from app.extensions import db
        from models.user import User
        
        if Tenant.query.filter_by(slug=slug).first():
            print(f"Tenant {slug} already exists")
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
        
        tenant = Tenant(slug=slug, name=name, contact_email=email,
                        status=TenantStatus.ACTIVE, product_profile_code=profile_code)
        db.session.add(tenant)
        db.session.flush()
        
        admin = User.query.first()
        for m in modules:
            db.session.add(TenantModule(tenant_id=tenant.id, module_name=m, is_active=True,
                                        activated_at=db.func.now(), activated_by=admin.id))
        db.session.commit()
        print(f"Created tenant {tenant.id} ({slug}) with {len(modules)} modules")

    @app.cli.command("tenant-backfill")
    @click.option("--tenant-id", default=11, type=int, help="Default tenant ID for backfill")
    def tenant_backfill(tenant_id):
        """Backfill tenant_id for existing records that have NULL tenant_id."""
        from app.extensions import db
        from sqlalchemy import text
        
        # Tables to backfill (only those with data)
        tables = [
            'users', 'patients', 'visits', 'medical_records', 'medical_reports',
            'treatments', 'invoices', 'prescriptions',
            'appointments', 'emergency_cases', 'queues', 'notifications', 'notification_queue',
            'beds', 'admissions', 'receipts', 'referrals', 'wards', 'rooms',
            'insurance_companies', 'insurance_claims', 'clinical_pathways',
            'patient_care_plans', 'care_plan_tasks',
            'medication_schedules', 'prescription_dispense_logs',
            'patient_accounts', 'medication_supply_requests', 'medication_supply_request_items',
            'medication_reconciliations', 'patient_problems', 'allergy_intolerances',
            'coded_diagnoses', 'coded_procedures', 'follow_up_requests',
            'telemedicine_appointments', 'surgery_schedules', 'surgery_checklists',
            'nurses', 'nursing_assessments', 'digital_signatures', 'file_categories',
            'staff_work_schedules', 'staff_absences', 'payment_transactions',
            'patient_allergies', 'lab_results', 'lab_requests', 'radiology_requests',
            'radiology_results', 'vital_signs', 'nurse_notes', 'daily_census_log',
            'surgery_checklist_items', 'clinical_pathway_templates',
            'treatment_protocols', 'medication_schedule_templates',
            'resource_usage',
        ]
        
        total_updated = 0
        for tbl in tables:
            try:
                r = db.session.execute(
                    text(f"UPDATE {tbl} SET tenant_id = :tid WHERE tenant_id IS NULL"),
                    {"tid": tenant_id}
                )
                affected = r.rowcount
                if affected:
                    total_updated += affected
                    print(f"  {tbl}: {affected} rows updated")
                db.session.commit()
            except Exception:
                db.session.rollback()
        
        print(f"\nBackfill complete: {total_updated} total rows updated")

    @app.cli.command("seed-default-bundles")
    def seed_default_bundles():
        """Seed default ProductBundles from seed data."""
        from app.core.tenant.models import seed_default_bundles as _seed
        _seed()

    # Background notification queue processor
    def _start_notification_processor(app_ctx):
        import threading
        import time

        def _run_loop():
            from services.tenant_job_runner import for_each_tenant
            from services.notification_service import process_notification_queue, NotificationService

            while True:
                try:
                    for_each_tenant(
                        app_ctx,
                        lambda tenant_id: (
                            process_notification_queue(tenant_id=tenant_id),
                            NotificationService.send_appointment_reminders(tenant_id=tenant_id),
                        ),
                    )
                except Exception:
                    pass
                time.sleep(60)

        thread = threading.Thread(target=_run_loop, daemon=True, name='notif-processor')
        thread.start()
        return thread

    if not app.testing and not app.config.get('SUPPRESS_BACKGROUND_WORKER'):
        _start_notification_processor(app)

    return app
