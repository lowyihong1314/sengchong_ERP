import secrets
import time
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SessionStore:
    def __init__(self, ttl_seconds, db):
        self.ttl_seconds = ttl_seconds
        self.db = db
        self.db.initialize()

    def create(self, *, database, username, display_name="", role="user", server=""):
        token = secrets.token_urlsafe(32)
        session = {
            "database": database,
            "username": username,
            "display_name": display_name or username,
            "role": role,
            "server": server or "",
            "expires_at": time.time() + self.ttl_seconds,
            "created_at": _now_iso(),
        }

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO erp_sessions (
                    token, database_name, username, display_name, role, server, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    session["database"],
                    session["username"],
                    session["display_name"],
                    session["role"],
                    session["server"],
                    session["expires_at"],
                    session["created_at"],
                ),
            )

        return token

    def get(self, token):
        if not token:
            return None

        self.cleanup()
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT database_name, username, display_name, role, server, expires_at
                FROM erp_sessions
                WHERE token = ?
                """,
                (token,),
            ).fetchone()

        return self._row_to_session(row) if row else None

    def delete(self, token):
        if not token:
            return
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM erp_sessions WHERE token = ?", (token,))

    def cleanup(self):
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM erp_sessions WHERE expires_at <= ?", (time.time(),))

    def update_database(self, token, database):
        next_expires_at = time.time() + self.ttl_seconds
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE erp_sessions
                SET database_name = ?, expires_at = ?
                WHERE token = ?
                """,
                (database, next_expires_at, token),
            )
            row = conn.execute(
                """
                SELECT database_name, username, display_name, role, server, expires_at
                FROM erp_sessions
                WHERE token = ?
                """,
                (token,),
            ).fetchone()

        return self._row_to_session(row) if row else None

    @staticmethod
    def _row_to_session(row):
        return {
            "database": row["database_name"],
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
            "role": row["role"] or "user",
            "server": row["server"] or "",
            "expires_at": row["expires_at"],
        }
