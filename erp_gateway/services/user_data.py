from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash


PROTECTED_USERNAMES = {"yukang"}
USER_ROLES = {"admin", "user"}


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_username(username):
    return str(username or "").strip().lower()


def _row_value(row, key, default=""):
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


class UserDataStore:
    def __init__(self, db):
        self.db = db
        self.db.initialize()

    def authenticate(self, username, password):
        username = _normalize_username(username)
        if not username or password is None:
            return None

        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT username, display_name, role, default_company, password_hash, created_at, updated_at
                FROM erp_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

        if not row:
            return None

        password_hash = row["password_hash"] or ""
        if not password_hash or not check_password_hash(password_hash, str(password)):
            return None

        return self._public_user(row)

    def upsert_user(self, username, password, *, display_name=None, role="user", default_company=""):
        username = _normalize_username(username)
        if not username:
            raise ValueError("Username is required.")
        if password is None or str(password) == "":
            raise ValueError("Password is required.")
        role = str(role or "user").strip().lower()
        if role not in USER_ROLES:
            raise ValueError("Role must be admin or user.")

        now = _now_iso()
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT created_at, display_name, role, default_company FROM erp_users WHERE username = ?",
                (username,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO erp_users (
                    username, display_name, role, default_company, password_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    display_name = excluded.display_name,
                    role = excluded.role,
                    default_company = excluded.default_company,
                    password_hash = excluded.password_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    username,
                    display_name or (existing["display_name"] if existing else "") or username,
                    role or (existing["role"] if existing else "") or "user",
                    default_company or (existing["default_company"] if existing else "") or "",
                    generate_password_hash(str(password)),
                    existing["created_at"] if existing else now,
                    now,
                ),
            )

        return self.get_user(username)

    def get_user(self, username):
        username = _normalize_username(username)
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT username, display_name, role, default_company, created_at, updated_at
                FROM erp_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        return self._public_user(row) if row else None

    def list_users(self):
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT username, display_name, role, default_company, created_at, updated_at
                FROM erp_users
                ORDER BY username
                """
            ).fetchall()
        return [self._public_user(row) for row in rows]

    def delete_user(self, username):
        username = _normalize_username(username)
        if not username:
            raise ValueError("Username is required.")
        if username in PROTECTED_USERNAMES:
            raise ValueError(f"User {username} cannot be removed.")

        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT username, display_name, role, default_company, created_at, updated_at
                FROM erp_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM erp_users WHERE username = ?", (username,))
        return self._public_user(row)

    def set_default_company(self, username, database):
        username = _normalize_username(username)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE erp_users SET default_company = ?, updated_at = ? WHERE username = ?",
                (database or "", _now_iso(), username),
            )
        return self.get_user(username)

    def has_users(self):
        with self.db.connect() as conn:
            row = conn.execute("SELECT 1 FROM erp_users LIMIT 1").fetchone()
        return row is not None

    @staticmethod
    def _public_user(row):
        return {
            "username": row["username"],
            "displayName": row["display_name"] or row["username"],
            "role": row["role"] or "user",
            "defaultCompany": row["default_company"] or "",
            "createdAt": _row_value(row, "created_at"),
            "updatedAt": _row_value(row, "updated_at"),
        }
