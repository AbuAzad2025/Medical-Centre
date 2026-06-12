"""
Medical Centre Platform — Modular Application Package
"""
from flask import Flask
from app.extensions import db, login_manager, migrate, mail, csrf, socketio

def create_app(config_name: str | None = None) -> Flask:
    """Application factory — minimal bootstrap for gradual migration."""
    from config import config as config_dict

    app = Flask(__name__, instance_relative_config=True)

    if config_name is None:
        config_name = app.config.get("ENV", "development")

    cfg = config_dict.get(config_name) or config_dict["default"]
    app.config.from_object(cfg)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)

    # Register blueprints (legacy paths until full migration)
    from routes import main as main_routes
    app.register_blueprint(main_routes.main_bp)

    return app
