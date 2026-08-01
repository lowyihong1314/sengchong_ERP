import secrets
from datetime import timedelta

from models import db
from models.sessions import ErpSession

from .services.values import now


class SessionStore:
    """
    Web/API session tokens, stored in the database rather than in process
    memory so gunicorn can run more than one worker.
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
        return self._to_session(session) if session else None

    def delete(self, token):
        if not token:
            return
        db.session.execute(db.delete(ErpSession).where(ErpSession.token == token))
        db.session.commit()

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

        return self._to_session(session)

    @staticmethod
    def _to_session(session):
        return {
            "database": session.database_name,
            "username": session.username,
            "display_name": session.display_name or session.username,
            "role": session.role or "user",
            "server": session.server or "",
            "expires_at": session.expires_at,
        }
