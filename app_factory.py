"""
مصنع التطبيق - Application Factory (منقح ومتوافق مع الموديلات الحالية)
"""
from flask import Flask, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
import os, logging
from logging.handlers import RotatingFileHandler
from sqlalchemy import inspect as _sa_inspect
from logging import StreamHandler
from datetime import datetime
from pathlib import Path

# إنشاء كائنات Flask
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # اختيار الإعدادات
    from config import config as app_config
    config_name = config_name or os.getenv("APP_ENV", "development")
    app.config.from_object(app_config.get(config_name, app_config["default"]))

    # تحكم بمستوى اللوجينغ عبر متغير LOG_LEVEL (DEBUG/INFO/WARNING/ERROR)
    log_level_name = os.environ.get("LOG_LEVEL", "DEBUG" if os.environ.get("FLASK_DEBUG") == "1" else "INFO")
    log_level = getattr(logging, log_level_name.upper(), logging.DEBUG)
    app.logger.setLevel(log_level)

    # إعداد Handlers: كونسول + ملف دوّار logs/app.log
    logs_dir = Path(app.root_path).joinpath("logs")
    try:
        logs_dir.mkdir(exist_ok=True)
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

    # تسجيل الموديلات في metadata ليتمكن Alembic من اكتشافها (استيراد فقط، بدون استعلامات)
    with app.app_context():
        try:
            # استيراد كل نماذجك هنا (حسب مشروعك)
            # استيراد النماذج الأساسية أولاً
            import models.department
            import models.user
            import models.patient
            import models.visit
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
            import models.nurse
            import models.queue_management
            import models.pricing_management
            import models.reporting
        except Exception as e:
            app.logger.warning(f"Model import registration skipped: {e}")

    login_manager.login_view = "auth.login"
    login_manager.login_message = "الرجاء تسجيل الدخول أولاً."
    login_manager.session_protection = "strong"
    
    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    # السجلات الدوّارة
    if not app.debug and not app.testing:
        os.makedirs("logs", exist_ok=True)
        handler = RotatingFileHandler("logs/medical_system.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    # Health
    @app.get("/__health")
    def __health():
        return jsonify(status="ok")

    # ping endpoint للتشخيص
    @app.get("/__ping")
    def __ping():
        return "pong", 200

    # استعراض المسارات (للتسهيل أثناء التطوير)
    @app.get("/__routes")
    def list_routes():
        rows = []
        for r in app.url_map.iter_rules():
            methods = ",".join(sorted(m for m in r.methods if m in {"GET","POST","PUT","PATCH","DELETE"}))
            rows.append(f"<div class='route'><b>{r.rule}</b> &nbsp; <small>{methods}</small> → <code>{r.endpoint}</code></div>")
        html = """
        <html dir="rtl" lang="ar"><head><meta charset="utf-8">
        <style>body{{font-family:Arial;padding:20px}}.route{{background:#eef;padding:8px;margin:5px;border-right:4px solid #39f}}</style>
        </head><body><h3>قائمة المسارات</h3>{rows}</body></html>""".format(rows="".join(rows))
        return render_template_string(html)

    # تهيئة بيانات افتراضية (محميّة ضد غياب الجداول أثناء أوامر Alembic)
    with app.app_context():
        try:
            insp = _sa_inspect(db.engine)
            if insp.has_table("users"):
                from models.user import User
                # من الآمن استيراد Department فقط عند الحاجة
                # from models.department import Department
                username = app.config.get('DEFAULT_ADMIN_USERNAME')
                if username and not User.query.filter_by(username=username).first():
                    admin = User(
                        username=username,
                        email=app.config.get('DEFAULT_ADMIN_EMAIL'),
                        full_name=app.config.get('DEFAULT_ADMIN_NAME'),
                        role='admin',
                        department_id=None,
                        is_admin=True
                    )
                    admin.set_password(app.config.get('DEFAULT_ADMIN_PASSWORD'))
                    db.session.add(admin)
                    db.session.commit()
                    app.logger.info("تم إنشاء المستخدم الافتراضي")
                else:
                    app.logger.info("تخطّي إنشاء المستخدم الافتراضي: موجود مسبقًا أو لم يُحدَّد اسم مستخدم.")
            else:
                app.logger.info("جدول users غير موجود بعد؛ سيتم تخطّي إنشاء الأدمن حتى إكمال الترحيلات.")
        except Exception as e:
            # لا نُفشل التطبيق أثناء أوامر Alembic
            app.logger.warning(f"تخطّي تهيئة البيانات الافتراضية: {e}")

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

    app.register_blueprint(main_bp)
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
    # app.register_blueprint(ai_bp, url_prefix='/ai')  # REMOVED - AI now in super_admin
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(medication_bp, url_prefix='/medication')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(nurse_bp, url_prefix='/nurse')

    # إعدادات لحل مشاكل 404
    app.url_map.strict_slashes = False
    return app