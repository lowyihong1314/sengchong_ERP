# models/user_data.py
from models import db


class ErpUser(db.Model):
    """An ERP web login. Deliberately separate from AutoCount's own users."""

    __tablename__ = "erp_users"

    username = db.Column(db.String(64), primary_key=True)
    display_name = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    default_company = db.Column(db.String(64), nullable=False, default="", server_default="")
    password_hash = db.Column(db.String(256), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<ErpUser {self.username} role={self.role}>"
