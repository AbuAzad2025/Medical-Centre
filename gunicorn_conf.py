"""Gunicorn configuration.

Critical for gunicorn >= 22 where the WSGI app is imported in the arbiter
(master) BEFORE workers are forked: any DB connections opened during
create_app() are inherited by every forked worker, so all workers end up
writing to the SAME PostgreSQL sockets -> protocol corruption
(PGRES_TUPLES_OK / ResourceClosedError / keymap KeyErrors).

post_fork disposes the inherited pool in each child so every worker dials
fresh connections of its own.
"""


def post_fork(server, worker):  # noqa: ARG001
    try:
        from app.extensions import db

        db.engine.dispose()
        server.log.info('post_fork: disposed inherited SQLAlchemy pool')
    except Exception as e:  # pragma: no cover - defensive
        server.log.warning('post_fork: engine dispose failed: %s', e)
