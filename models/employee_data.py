# models/employee_data.py
from models import db


class ErpEmployee(db.Model):
    """
    A person who works for Seng Chong.

    Deliberately separate from ErpUser. Most of the workshop and installation
    crew will never log into the ERP, and a login can exist without belonging
    to an employee (an external bookkeeper, an integration account). The link
    between them is therefore optional in both directions.

    Employees are not scoped to a company: AED_SENG and AED_MANSON share the
    same crew, and which entity a job belongs to is decided by the project.

    Subcontractors do not belong here. They are AutoCount creditors, billed
    through AP invoices; mixing them in would make labour cost and AP disagree.
    """

    __tablename__ = "erp_employees"
    __table_args__ = (
        db.UniqueConstraint("employee_code", name="uq_erp_employees_code"),
        # One ERP login belongs to at most one employee.
        db.UniqueConstraint("username", name="uq_erp_employees_username"),
        db.Index("idx_erp_employees_status_name", "status", "name"),
    )

    id = db.Column(db.String(32), primary_key=True)  # uuid4().hex
    employee_code = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)

    # The ERP login this person uses, if they have one. Deleting the login
    # must not delete the person, so this is SET NULL rather than CASCADE.
    username = db.Column(
        db.String(64),
        db.ForeignKey("erp_users.username", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    # What they do. This is a job title, not an authorisation role -- that
    # lives in erp_users.role and answers a different question.
    position = db.Column(db.String(64), nullable=False, default="", server_default="")
    phone = db.Column(db.String(64), nullable=False, default="", server_default="")
    email = db.Column(db.String(128), nullable=False, default="", server_default="")
    ic_no = db.Column(db.String(32), nullable=False, default="", server_default="")

    hired_on = db.Column(db.Date)
    left_on = db.Column(db.Date)

    # Employees are retired by status, never deleted: project history and any
    # future work assignments refer to them.
    status = db.Column(db.String(32), nullable=False, default="Active", server_default="Active")

    notes = db.Column(db.Text, nullable=False, default="", server_default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    user = db.relationship("ErpUser", foreign_keys=[username])

    def __repr__(self):
        return f"<ErpEmployee {self.employee_code} {self.name}>"
