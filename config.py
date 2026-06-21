"""
إعدادات النظام - Configuration (PostgreSQL Only)
"""
import os
from datetime import timedelta


class Config:
    """الإعدادات الأساسية — PostgreSQL فقط"""

    # PostgreSQL فقط — no SQLite fallback in production/development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not SQLALCHEMY_DATABASE_URI:
        # Allow subclasses (TestingConfig) to set their own fallback
        pass

    # إعدادات PostgreSQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 20,
        'echo': False
    }

    
    # إعدادات Flask
    # SERVER_NAME = '127.0.0.1:8080'
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required. Set it before running the application.")
    
    # إعدادات الأداء
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = False
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # سنة واحدة للكاش
    DEFAULT_CURRENCY = os.environ.get('DEFAULT_CURRENCY') or 'ILS'

    # ========== SaaS Multi-Tenancy Configuration ==========
    # Deployment mode:
    #   single_install — one standalone customer, no tenant enforcement (default).
    #   saas           — ENABLE_SAAS_MODE=True, tenant resolution + module guards enforced.
    DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'single_install').strip().lower()
    # Explicit SaaS flag — overrides DEPLOYMENT_MODE if set.
    # Accepts: true/on/1 (any casing) for enabled.
    ENABLE_SAAS_MODE = os.environ.get('ENABLE_SAAS_MODE', '').lower() in ('true', 'on', '1') \
        if os.environ.get('ENABLE_SAAS_MODE') is not None \
        else DEPLOYMENT_MODE == 'saas'
    # Tenant resolution strategy: domain, subdomain, path, or all (comma-separated)
    TENANT_RESOLUTION_MODE = os.environ.get('TENANT_RESOLUTION_MODE', 'path').strip().lower()
    # Base domain for subdomain-based resolution, e.g. "example.com" → tenant.example.com
    TENANT_BASE_DOMAIN = os.environ.get('TENANT_BASE_DOMAIN', '').strip().lower()
    # Auto-create default tenant on first run (dev/test convenience)
    TENANT_AUTO_CREATE = os.environ.get('TENANT_AUTO_CREATE', 'false').lower() in ('true', 'on', '1')
    TENANT_DEFAULT_SLUG = os.environ.get('TENANT_DEFAULT_SLUG', 'default').strip().lower()
    
    # إعدادات قاعدة البيانات
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # إعدادات الجلسة
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true','on','1')
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # إعدادات WTF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Debug endpoints — disabled by default (deny by design)
    DISABLE_DEBUG_ENDPOINTS = os.environ.get('DISABLE_DEBUG_ENDPOINTS', 'true').lower() in ('true', 'on', '1')

    # إعدادات المستخدم الافتراضي — يجب توفيرها عبر environment variables
    DEFAULT_ADMIN_USERNAME = os.environ.get('DEFAULT_ADMIN_USERNAME')
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD')
    DEFAULT_ADMIN_EMAIL = os.environ.get('DEFAULT_ADMIN_EMAIL')
    DEFAULT_ADMIN_NAME = os.environ.get('DEFAULT_ADMIN_NAME') or 'مدير النظام'
    
    # إعدادات البريد الإلكتروني
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'localhost'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@medical.com'
    
    # إعدادات الملفات
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # إعدادات التقارير
    REPORT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'reports')
    PDF_TEMPLATE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'pdf')
    
    # ملاحظة: تم تجنّب تكرار تعريف SQLALCHEMY_ENGINE_OPTIONS

class DevelopmentConfig(Config):
    """إعدادات التطوير — PostgreSQL فقط"""

    DEBUG = True
    DISABLE_DEBUG_ENDPOINTS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        os.environ.get('DATABASE_URL') or \
        os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DEV_DATABASE_URL أو DATABASE_URL أو SQLALCHEMY_DATABASE_URI "
            "مطلوبة للتطوير. PostgreSQL فقط."
        )

    TESTING = False
    WTF_CSRF_ENABLED = True
    LOG_LEVEL = 'DEBUG'
    LOG_TO_STDOUT = True
    # إعادة تحميل القوالب تلقائياً في التطوير حتى تظهر التعديلات دون إعادة تشغيل
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0


class ProductionConfig(Config):
    """إعدادات الإنتاج — PostgreSQL فقط"""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL أو SQLALCHEMY_DATABASE_URI مطلوبة للإنتاج. PostgreSQL فقط."
        )

    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() in ['true','on','1']
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'true').lower() in ['true','on','1']
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    LOG_LEVEL = 'INFO'
    LOG_TO_STDOUT = False


class LocalConfig(Config):
    """إعدادات التشغيل المحلي — PostgreSQL فقط"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('LOCAL_DATABASE_URL') or \
        os.environ.get('DATABASE_URL') or \
        os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "LOCAL_DATABASE_URL أو DATABASE_URL أو SQLALCHEMY_DATABASE_URI "
            "مطلوبة للتشغيل المحلي. PostgreSQL فقط."
        )
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True
    LOG_LEVEL = 'DEBUG'
    LOG_TO_STDOUT = True


class TestingConfig(Config):
    """إعدادات الاختبار — SQLite fallback إن لم تتوفر PostgreSQL"""

    TESTING = True
    WTF_CSRF_ENABLED = False
    # Load .env first so tests can pick up DATABASE_URL if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        os.environ.get('DATABASE_URL') or \
        os.environ.get('SQLALCHEMY_DATABASE_URI') or \
        'sqlite:///:memory:'
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {}
        SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Provide a default SECRET_KEY for testing so tests don't need the env var
    if not os.environ.get('SECRET_KEY'):
        SECRET_KEY = 'test-secret-key'

    LOGIN_DISABLED = False


# قاموس الإعدادات
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'local': LocalConfig,
    'default': DevelopmentConfig
}
