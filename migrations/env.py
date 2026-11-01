import logging
import os
import sys
from logging.config import fileConfig

# Allow version modules to import shared helpers from migrations/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine_url_from_config():
    """Get database URL from config (set via -x flag or alembic.ini)"""
    # First try to get URL from -x flag (passed by verify_migrations.py)
    if config.cmd_opts and hasattr(config.cmd_opts, 'x') and config.cmd_opts.x:
        for x in config.cmd_opts.x:
            if x.startswith('sqlalchemy.url='):
                return x.split('=', 1)[1]
    # Fall back to config file
    return config.get_main_option("sqlalchemy.url")


def get_metadata():
    """Get metadata for migrations - in offline mode we return empty metadata"""
    # In offline mode, we don't have access to Flask app, so return empty metadata
    # The actual migrations don't need metadata for SQL generation
    from sqlalchemy import MetaData
    return MetaData()


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_engine_url_from_config()
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    This function MUST be called within a Flask app context.
    """
    # Import Flask only when running online (with actual database)
    from flask import current_app

    def get_engine():
        try:
            # this works with Flask-SQLAlchemy<3 and Alchemical
            return current_app.extensions['migrate'].db.get_engine()
        except (TypeError, AttributeError):
            # this works with Flask-SQLAlchemy>=3
            return current_app.extensions['migrate'].db.engine

    def get_engine_url():
        try:
            return get_engine().url.render_as_string(hide_password=False).replace(
                '%', '%%')
        except AttributeError:
            return str(get_engine().url).replace('%', '%%')

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


# Only run migrations if we're in a Flask app context.
# If not in app context (e.g., alembic command run directly without Flask),
# defer execution until Flask-Migrate's upgrade() calls us with proper context.
try:
    from flask import current_app
    # Check if we're in an app context by trying to access current_app
    _ = current_app
    # If we get here without RuntimeError, we're in an app context
    if not context.is_offline_mode():
        run_migrations_online()
    else:
        run_migrations_offline()
except RuntimeError:
    # Not in a Flask app context - this happens when alembic runs directly
    # without Flask (e.g., `alembic upgrade head` from command line).
    # In this case, we don't run migrations here; Flask-Migrate's upgrade()
    # will call us again with proper app context.
    pass