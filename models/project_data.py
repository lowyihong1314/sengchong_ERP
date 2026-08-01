# models/project_data.py
from models import db


class ErpProject(db.Model):
    """
    The business-facing job layer that AutoCount does not have.

    A project ties a customer job (kitchen cabinet, wardrobe, mall counter, ...)
    to the AutoCount documents raised against it. It is ERP-owned data: nothing
    here is ever written back into AutoCount's accounting tables.
    """

    __tablename__ = "erp_projects"
    __table_args__ = (
        db.UniqueConstraint("company", "project_code", name="uq_erp_projects_company_code"),
        db.Index("idx_erp_projects_company_updated", "company", "updated_at"),
    )

    id = db.Column(db.String(32), primary_key=True)  # uuid4().hex
    company = db.Column(db.String(64), nullable=False)
    project_code = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(255), nullable=False)

    debtor_code = db.Column(db.String(64), nullable=False, default="", server_default="")
    debtor_name = db.Column(db.String(255), nullable=False, default="", server_default="")
    contact_person = db.Column(db.String(128), nullable=False, default="", server_default="")
    phone = db.Column(db.String(64), nullable=False, default="", server_default="")
    site_address = db.Column(db.Text, nullable=False, default="", server_default="")
    service_category = db.Column(db.String(64), nullable=False, default="", server_default="")
    status = db.Column(db.String(32), nullable=False, default="Lead", server_default="Lead")

    # NULL means "not set". The API still renders that as "".
    expected_install_date = db.Column(db.Date)
    completion_date = db.Column(db.Date)

    # Money is Numeric, not Float: these are quoted and collected amounts.
    quoted_total = db.Column(db.Numeric(14, 2))
    collected_total = db.Column(db.Numeric(14, 2))
    outstanding_amount = db.Column(db.Numeric(14, 2))
    estimated_cost = db.Column(db.Numeric(14, 2))
    actual_cost = db.Column(db.Numeric(14, 2))

    notes = db.Column(db.Text, nullable=False, default="", server_default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    documents = db.relationship(
        "ErpProjectDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    photos = db.relationship(
        "ErpProjectPhoto",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<ErpProject {self.company}/{self.project_code}>"


class ErpProjectDocument(db.Model):
    """Link from a project to one AutoCount document number, by module."""

    __tablename__ = "erp_project_documents"
    __table_args__ = (
        db.UniqueConstraint("project_id", "module", "doc_no", name="uq_erp_project_documents_link"),
        # "which project owns invoice ML 2605/01?" -- the hot lookup when the
        # detail page of an AutoCount document asks for its project.
        db.Index("idx_erp_project_documents_lookup", "module", "doc_no"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(
        db.String(32),
        db.ForeignKey("erp_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    module = db.Column(db.String(32), nullable=False)
    doc_no = db.Column(db.String(64), nullable=False)

    project = db.relationship("ErpProject", back_populates="documents")

    def __repr__(self):
        return f"<ErpProjectDocument {self.module}:{self.doc_no}>"
