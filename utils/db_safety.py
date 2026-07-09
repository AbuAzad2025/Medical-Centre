"""
Centralised database safety wrapper.

All `db.session.commit()` and `db.session.rollback()` calls in the
codebase MUST be replaced by calls to this module.
"""

import logging
from contextlib import contextmanager

from flask import current_app


def safe_commit(db_session, *, error_message="Database error", reraise=False, logger=None):
    """
    Commit and rollback on failure.

    Parameters
    ----------
    db_session : SQLAlchemy session
    error_message : str
        Prefix for the log line on failure.
    reraise : bool
        If True, re-raise the exception after rollback.
        Use for model-level code where callers must handle errors.
    logger : Logger, optional
        Defaults to ``current_app.logger``.

    Returns
    -------
    True on success, False on failure (unless *reraise* is True).

    Usage
    -----
    # Service / route — return error code on failure:
        if not safe_commit(db.session):
            return {"success": False, "message": "…"}

    # Model — let the exception propagate:
        safe_commit(db.session, reraise=True)
    """
    try:
        db_session.commit()
        return True
    except Exception as e:
        db_session.rollback()
        (logger or current_app.logger).error(f"{error_message}: {e}")
        if reraise:
            raise
        return False


def safe_rollback(db_session, *, error_message="Database rollback", logger=None):
    """
    Roll back the current transaction and log.

    Use for functions that deliberately defer the final ``commit`` to their
    caller (e.g. idempotency-scoped payment creation). On error the pending
    changes are discarded and the failure is logged; the exception is *not*
    swallowed so the caller's error path still works.
    """
    try:
        db_session.rollback()
    except Exception as e:
        (logger or current_app.logger).error(f"{error_message}: {e}")


@contextmanager
def safe_transaction(db_session, *, error_message="Database error", logger=None):
    """
    Context manager that commits on success, rolls back on exception.

    Usage
    -----
    # Simple create:
        with safe_transaction(db.session):
            obj = Model(**data)
            db.session.add(obj)

    # Two-phase (business + audit):
        with safe_transaction(db.session):
            visit.paid_amount = new_amount
            visit.payment_status = "paid"

        with safe_transaction(db.session):
            audit = AuditTrail(…)
            db.session.add(audit)
    """
    try:
        yield
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        (logger or current_app.logger).error(f"{error_message}: {e}")
        raise
