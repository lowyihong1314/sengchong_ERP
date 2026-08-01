# models/sengchong_content.py
from models import db


class SengchongService(db.Model):
    """One service card on the public site (kitchen cabinet, wardrobe, ...)."""

    __tablename__ = "sengchong_services"

    no = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(128), nullable=False)
    bg = db.Column(db.String(512), nullable=False)

    def __repr__(self):
        return f"<SengchongService {self.no} {self.service_name}>"


class SengchongContact(db.Model):
    """One contact person shown on the public site."""

    __tablename__ = "sengchong_contacts"

    no = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    number = db.Column(db.String(64), nullable=False)
    bg = db.Column(db.String(512), nullable=False)

    def __repr__(self):
        return f"<SengchongContact {self.no} {self.name}>"


class SengchongSetting(db.Model):
    """Key/value footer and site settings, edited from the ERP only."""

    __tablename__ = "sengchong_settings"

    key = db.Column("key", db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.String(40), nullable=False)

    def __repr__(self):
        return f"<SengchongSetting {self.key}>"


class ErpWebsiteAuditLog(db.Model):
    """Who published/unpublished what on the public site, and when."""

    __tablename__ = "erp_website_audit_log"
    __table_args__ = (db.Index("idx_erp_website_audit_company_created", "company", "created_at"),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.String(64), nullable=False)
    project_code = db.Column(db.String(64), nullable=False, default="", server_default="")
    field_name = db.Column(db.String(64), nullable=False, default="", server_default="")
    old_value = db.Column(db.Text, nullable=False, default="", server_default="")
    new_value = db.Column(db.Text, nullable=False, default="", server_default="")
    username = db.Column(db.String(64), nullable=False, default="", server_default="")
    created_at = db.Column(db.String(40), nullable=False)

    def __repr__(self):
        return f"<ErpWebsiteAuditLog {self.action} {self.entity_type}:{self.entity_id}>"
