# models/work_entry.py
from models import db


class ErpWorkEntry(db.Model):
    """
    One person's work on one date at one company.

    Not one row per day: somebody can work for AED_SENG and AED_MANSON on the
    same date, and each company counts a full day, so that is two rows. A row
    can also carry the overtime and overnight worked in that same stint, which
    is how a foreman actually writes it down.

    The money is not stored here. It is derived from the employee's salary
    setup when read, so correcting a rate fixes the figures instead of leaving
    stale ones behind. A payroll run will snapshot what it used at the time --
    that snapshot, not this table, is the record for a pay dispute.
    """

    __tablename__ = "erp_work_entries"
    __table_args__ = (
        db.Index("idx_erp_work_entries_employee_date", "employee_id", "work_date"),
        db.Index("idx_erp_work_entries_date_company", "work_date", "company"),
        db.Index("idx_erp_work_entries_project", "project_id"),
    )

    id = db.Column(db.String(32), primary_key=True)  # uuid4().hex
    employee_id = db.Column(
        db.String(32),
        db.ForeignKey("erp_employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date = db.Column(db.Date, nullable=False)
    company = db.Column(db.String(64), nullable=False)

    # Optional: plenty of work (shop tidying, running errands) belongs to no
    # single job. Deleting a project must not delete the attendance record.
    project_id = db.Column(
        db.String(32),
        db.ForeignKey("erp_projects.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Normal work is counted in days because everyone is day-rated; 0.5 is
    # allowed for the occasional half day.
    day_units = db.Column(db.Numeric(6, 2), nullable=False, default=0, server_default="0")
    ot_hours = db.Column(db.Numeric(6, 2), nullable=False, default=0, server_default="0")

    # Both are needed: some overnight arrangements pay a flat amount per
    # night, some pay for the hours, and some pay both.
    overnight_nights = db.Column(
        db.Numeric(6, 2), nullable=False, default=0, server_default="0"
    )
    overnight_hours = db.Column(
        db.Numeric(6, 2), nullable=False, default=0, server_default="0"
    )

    note = db.Column(db.Text, nullable=False, default="", server_default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    employee = db.relationship("ErpEmployee", backref=db.backref("work_entries", passive_deletes=True))
    project = db.relationship("ErpProject")

    def __repr__(self):
        return f"<ErpWorkEntry {self.work_date} {self.company} {self.employee_id}>"
