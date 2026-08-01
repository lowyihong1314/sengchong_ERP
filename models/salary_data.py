# models/salary_data.py
from models import db


class ErpEmployeeSalary(db.Model):
    """
    What one employee is paid, and the identifiers a payroll run needs.

    One row per employee -- this is the *current* setup, not a history. Payroll
    runs will snapshot what they used at the time, which is the record that
    matters for a dispute; keeping effective-dated rows here as well would be
    two sources of truth.

    Statutory amounts are deliberately absent. EPF, SOCSO, EIS and PCB are
    calculated during a payroll run from rate tables maintained in the app, not
    stored per employee, so a rate change does not mean editing every row.
    """

    __tablename__ = "erp_employee_salary"

    # 1:1 with the employee, so the employee id is the key.
    employee_id = db.Column(
        db.String(32),
        db.ForeignKey("erp_employees.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Monthly / Daily / Hourly. The workshop is often day-rated while office
    # staff are monthly, and basic_rate means "per that unit".
    pay_type = db.Column(db.String(16), nullable=False, default="Monthly", server_default="Monthly")
    basic_rate = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    fixed_allowance = db.Column(db.Numeric(14, 2), nullable=False, default=0, server_default="0")
    allowance_note = db.Column(db.String(255), nullable=False, default="", server_default="")

    # Statutory identifiers. Numbers only -- the rates that go with them live
    # in the payroll rate tables.
    epf_member_no = db.Column(db.String(32), nullable=False, default="", server_default="")
    socso_no = db.Column(db.String(32), nullable=False, default="", server_default="")
    tax_no = db.Column(db.String(32), nullable=False, default="", server_default="")

    # Not everyone contributes: this drives whether a payroll run applies the
    # EPF/SOCSO/EIS rules to this person at all.
    epf_contributing = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    socso_contributing = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )

    # --- Overtime -------------------------------------------------------
    # Everyone here is day-rated, and the hourly OT base is the daily rate
    # divided by that person's standard hours: 8, 9 and 10 are all in use.
    # The multiplier that goes with it varies too (1.5, 1.75, 2.0), and the
    # pairing is per person, not a company-wide rule.
    ot_divisor = db.Column(db.Numeric(5, 2), nullable=False, default=8, server_default="8")
    ot_multiplier = db.Column(
        db.Numeric(5, 2), nullable=False, default=1.5, server_default="1.5"
    )

    # --- Overnight ------------------------------------------------------
    # All four arrangements are in use, so this is a per-person mode rather
    # than one formula:
    #   allowance             flat amount per night
    #   hourly                hours x (daily / ot_divisor) x overnight_multiplier
    #   extra_day             daily x overnight_day_factor, per night
    #   allowance_plus_hours  the flat amount AND the hours on top
    overnight_mode = db.Column(
        db.String(24), nullable=False, default="allowance", server_default="allowance"
    )
    overnight_allowance = db.Column(
        db.Numeric(14, 2), nullable=False, default=0, server_default="0"
    )
    overnight_multiplier = db.Column(
        db.Numeric(5, 2), nullable=False, default=2, server_default="2"
    )
    overnight_day_factor = db.Column(
        db.Numeric(5, 2), nullable=False, default=1, server_default="1"
    )

    bank_name = db.Column(db.String(64), nullable=False, default="", server_default="")
    bank_account_no = db.Column(db.String(64), nullable=False, default="", server_default="")

    effective_from = db.Column(db.Date)
    notes = db.Column(db.Text, nullable=False, default="", server_default="")

    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    # delete-orphan + passive_deletes so the database's ON DELETE CASCADE does
    # the work. Without it SQLAlchemy tries to disassociate first, which means
    # blanking employee_id -- and that is this table's primary key.
    employee = db.relationship(
        "ErpEmployee",
        backref=db.backref(
            "salary", uselist=False, cascade="all, delete-orphan", passive_deletes=True
        ),
    )

    def __repr__(self):
        return f"<ErpEmployeeSalary {self.employee_id} {self.pay_type} {self.basic_rate}>"
