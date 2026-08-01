# models/sessions.py
from models import db


class ErpSession(db.Model):
    """A web/API session token. Stored in the DB so gunicorn can run >1 worker."""

    __tablename__ = "erp_sessions"
    __table_args__ = (db.Index("idx_erp_sessions_expires_at", "expires_at"),)

    token = db.Column(db.String(64), primary_key=True)
    database_name = db.Column(db.String(64), nullable=False)
    username = db.Column(db.String(64), nullable=False)
    display_name = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    server = db.Column(db.String(128), nullable=False, default="", server_default="")

    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<ErpSession {self.username}@{self.database_name}>"
