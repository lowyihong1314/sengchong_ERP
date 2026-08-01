from werkzeug.security import check_password_hash, generate_password_hash

from models import db
from models.user_data import ErpUser

from .values import now, to_iso


PROTECTED_USERNAMES = {"yukang"}
USER_ROLES = {"admin", "user"}


def _normalize_username(username):
    return str(username or "").strip().lower()


class UserDataStore:
    """ERP web logins. Kept separate from AutoCount's own user accounts."""

    def authenticate(self, username, password):
        username = _normalize_username(username)
        if not username or password is None:
            return None

        user = db.session.get(ErpUser, username)
        if not user:
            return None

        password_hash = user.password_hash or ""
        if not password_hash or not check_password_hash(password_hash, str(password)):
            return None

        return self._public_user(user)

    def upsert_user(self, username, password, *, display_name=None, role="user", default_company=""):
        username = _normalize_username(username)
        if not username:
            raise ValueError("Username is required.")
        if password is None or str(password) == "":
            raise ValueError("Password is required.")
        role = str(role or "user").strip().lower()
        if role not in USER_ROLES:
            raise ValueError("Role must be admin or user.")

        timestamp = now()
        user = db.session.get(ErpUser, username)
        if user is None:
            user = ErpUser(username=username, created_at=timestamp)
            db.session.add(user)

        # An omitted field keeps whatever the row already had, then falls back
        # to a sensible default for a brand new user.
        user.display_name = display_name or user.display_name or username
        user.role = role or user.role or "user"
        user.default_company = default_company or user.default_company or ""
        user.password_hash = generate_password_hash(str(password))
        user.updated_at = timestamp

        db.session.commit()
        return self._public_user(user)

    def get_user(self, username):
        user = db.session.get(ErpUser, _normalize_username(username))
        return self._public_user(user) if user else None

    def list_users(self):
        users = db.session.scalars(db.select(ErpUser).order_by(ErpUser.username)).all()
        return [self._public_user(user) for user in users]

    def delete_user(self, username):
        username = _normalize_username(username)
        if not username:
            raise ValueError("Username is required.")
        if username in PROTECTED_USERNAMES:
            raise ValueError(f"User {username} cannot be removed.")

        user = db.session.get(ErpUser, username)
        if not user:
            return None

        payload = self._public_user(user)
        db.session.delete(user)
        db.session.commit()
        return payload

    def set_default_company(self, username, database):
        username = _normalize_username(username)
        user = db.session.get(ErpUser, username)
        if not user:
            return None

        user.default_company = database or ""
        user.updated_at = now()
        db.session.commit()
        return self._public_user(user)

    def has_users(self):
        return db.session.scalar(db.select(db.func.count()).select_from(ErpUser)) > 0

    @staticmethod
    def _public_user(user):
        return {
            "username": user.username,
            "displayName": user.display_name or user.username,
            "role": user.role or "user",
            "defaultCompany": user.default_company or "",
            "createdAt": to_iso(user.created_at),
            "updatedAt": to_iso(user.updated_at),
        }
