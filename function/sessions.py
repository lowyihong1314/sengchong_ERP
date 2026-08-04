import secrets
from datetime import timedelta

from models import db
from models.sessions import ErpSession
from models.user_data import ErpUser

from .services.values import now


class SessionStore:
    """
    Web/API session tokens, stored in the database rather than in process
    memory so gunicorn can run more than one worker.

    A session carries per-login state -- which AutoCount company this token is
    currently looking at, and when it expires. It does *not* carry authority:
    display name and role are read back from erp_users on every lookup, so
    changing someone's role or deleting their account takes effect on their
    next request rather than whenever the token happens to expire.
    """

    def __init__(self, ttl_seconds):
        self.ttl_seconds = ttl_seconds

    def create(self, *, database, username, display_name="", role="user", server=""):
        token = secrets.token_urlsafe(32)

        db.session.add(
            ErpSession(
                token=token,
                database_name=database,
                username=username,
                # Recorded for the audit trail -- "what were they when they
                # signed in" -- and deliberately not what authorisation reads.
                display_name=display_name or username,
                role=role,
                server=server or "",
                expires_at=now() + timedelta(seconds=self.ttl_seconds),
                created_at=now(),
            )
        )
        db.session.commit()

        return token

    def get(self, token):
        if not token:
            return None

        self.cleanup()
        session = db.session.get(ErpSession, token)
        if not session:
            return None

        return self._with_user(session)

    def delete(self, token):
        if not token:
            return
        db.session.execute(db.delete(ErpSession).where(ErpSession.token == token))
        db.session.commit()

    def delete_for_user(self, username):
        """Drop every session belonging to one account. Returns how many."""
        target = str(username or "").strip().lower()
        if not target:
            return 0

        result = db.session.execute(
            db.delete(ErpSession).where(db.func.lower(ErpSession.username) == target)
        )
        db.session.commit()
        return result.rowcount or 0

    def set_database_for_user(self, username, database):
        """
        Move every live session of one account onto a company. Returns how many.

        A session records the company it was opened against, so a default
        changed afterwards would not reach anyone already signed in -- they
        would keep working in the old company until the session expired, with
        the setting on screen saying otherwise. An admin moving somebody
        between companies means now, not at their next login.

        Only for the admin path. The login and company-switch handlers write
        the default *from* the session and must not be fed back into it.
        """
        target = str(username or "").strip().lower()
        if not target:
            return 0

        result = db.session.execute(
            db.update(ErpSession)
            .where(db.func.lower(ErpSession.username) == target)
            .values(database_name=database)
        )
        db.session.commit()
        return result.rowcount or 0

    def cleanup(self):
        db.session.execute(db.delete(ErpSession).where(ErpSession.expires_at <= now()))
        db.session.commit()

    def update_database(self, token, database):
        session = db.session.get(ErpSession, token)
        if not session:
            # The UPDATE this replaces was a no-op for an unknown token, and
            # the SELECT that followed returned nothing.
            db.session.commit()
            return None

        session.database_name = database
        session.expires_at = now() + timedelta(seconds=self.ttl_seconds)
        db.session.commit()

        return self._with_user(session)

    def _with_user(self, session):
        """
        Resolve a session row against the account it belongs to.

        Returns None when the account is gone, and deletes the orphaned token
        on the way out: removing a user should sign them out, not leave a
        working credential behind.
        """
        user = db.session.get(ErpUser, session.username)
        if not user:
            db.session.delete(session)
            db.session.commit()
            return None

        return {
            "database": session.database_name,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": user.role or "user",
            "server": session.server or "",
            "expires_at": session.expires_at,
        }
