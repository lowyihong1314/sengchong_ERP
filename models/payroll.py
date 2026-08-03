# models/payroll.py
from models import db


class ErpPayrollRun(db.Model):
    """
    One month's payroll for one company.

    A run starts as a draft that can be regenerated and edited freely. Locking
    it freezes the figures: from then on the items are the record, and later
    edits to a salary rate or a timesheet do not reach back into a month that
    has already been paid.
    """

    __tablename__ = "erp_payroll_runs"
    __table_args__ = (
        db.UniqueConstraint("company", "period", name="uq_erp_payroll_runs_company_period"),
        db.Index("idx_erp_payroll_runs_period", "period"),
    )

    id = db.Column(db.String(32), primary_key=True)  # uuid4().hex
    company = db.Column(db.String(64), nullable=False)
    period = db.Column(db.String(7), nullable=False)  # YYYY-MM
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    # draft -> locked. There is no unlock: a locked run is corrected by a
    # later adjustment, not by rewriting history.
    status = db.Column(db.String(16), nullable=False, default="draft", server_default="draft")

    # What the statutory rules were when this run was locked. Empty until
    # rate tables exist, and recorded so a payslip can say which rules it used.
    statutory_basis = db.Column(db.Text, nullable=False, default="", server_default="")

    notes = db.Column(db.Text, nullable=False, default="", server_default="")
    locked_at = db.Column(db.DateTime(timezone=True))
    locked_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    items = db.relationship(
        "ErpPayrollItem",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<ErpPayrollRun {self.company} {self.period} {self.status}>"


class ErpPayrollItem(db.Model):
    """
    One person's line on one payroll run, and the payslip behind it.

    Everything needed to reprint that payslip is copied here rather than
    referenced: the name, the daily rate, the overtime rule. A payslip must
    still be reproducible after somebody gets a raise or changes department,
    so it cannot be rebuilt by re-reading today's salary setup.
    """

    __tablename__ = "erp_payroll_items"
    __table_args__ = (
        db.UniqueConstraint("run_id", "employee_id", name="uq_erp_payroll_items_run_employee"),
    )

    id = db.Column(db.String(32), primary_key=True)
    run_id = db.Column(
        db.String(32), db.ForeignKey("erp_payroll_runs.id", ondelete="CASCADE"), nullable=False
    )
    employee_id = db.Column(
        db.String(32), db.ForeignKey("erp_employees.id", ondelete="RESTRICT"), nullable=False
    )

    # --- snapshot of who they were and what they were paid ---
    employee_code = db.Column(db.String(32), nullable=False)
    employee_name = db.Column(db.String(128), nullable=False)
    position = db.Column(db.String(64), nullable=False, default="", server_default="")
    daily_rate = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    ot_rule = db.Column(db.String(255), nullable=False, default="", server_default="")
    bank_name = db.Column(db.String(64), nullable=False, default="", server_default="")
    bank_account_no = db.Column(db.String(64), nullable=False, default="", server_default="")
    epf_member_no = db.Column(db.String(32), nullable=False, default="", server_default="")
    socso_no = db.Column(db.String(32), nullable=False, default="", server_default="")

    # --- what they worked ---
    day_units = db.Column(db.Numeric(8, 2), nullable=False, default=0, server_default="0")
    ot_hours = db.Column(db.Numeric(8, 2), nullable=False, default=0, server_default="0")
    overnight_nights = db.Column(db.Numeric(8, 2), nullable=False, default=0, server_default="0")
    overnight_hours = db.Column(db.Numeric(8, 2), nullable=False, default=0, server_default="0")

    # --- earnings ---
    normal_pay = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    ot_pay = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    overnight_pay = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    fixed_allowance = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    # Anything the clerk adds by hand: a bonus, a claim, a deduction for an
    # advance. Signed, so one field covers both directions.
    adjustment = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    adjustment_note = db.Column(db.String(255), nullable=False, default="", server_default="")
    gross_pay = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")

    # --- statutory deductions ---
    # All zero until the KWSP / PERKESO / LHDN rate tables exist. They are
    # columns rather than a later migration so the payslip layout, the totals
    # and the reports are already shaped for them.
    epf_employee = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    epf_employer = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    socso_employee = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    socso_employer = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    eis_employee = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    eis_employer = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    pcb = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    other_deduction = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    other_deduction_note = db.Column(db.String(255), nullable=False, default="", server_default="")

    net_pay = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")

    run = db.relationship("ErpPayrollRun", back_populates="items")
    employee = db.relationship("ErpEmployee")

    def __repr__(self):
        return f"<ErpPayrollItem {self.employee_code} {self.net_pay}>"
