import calendar
import datetime as dt
import uuid
from decimal import Decimal

from models import db
from models.employee_data import ErpEmployee
from models.payroll import ErpPayrollItem, ErpPayrollRun
from models.salary_data import ErpEmployeeSalary
from models.work_entry import ErpWorkEntry

from .salary_data import _ot_rule_text
from .values import money_or_empty, now, parse_money, to_date_text, to_iso
from .work_entry import compute_pay


ZERO = Decimal("0.00")

# Editable by hand on a draft line. Everything else is derived from timesheets
# or copied from the salary setup.
ITEM_MONEY_FIELDS = {
    "fixedAllowance": "fixed_allowance",
    "adjustment": "adjustment",
    "epfEmployee": "epf_employee",
    "epfEmployer": "epf_employer",
    "socsoEmployee": "socso_employee",
    "socsoEmployer": "socso_employer",
    "eisEmployee": "eis_employee",
    "eisEmployer": "eis_employer",
    "pcb": "pcb",
    "otherDeduction": "other_deduction",
}
ITEM_TEXT_FIELDS = {
    "adjustmentNote": "adjustment_note",
    "otherDeductionNote": "other_deduction_note",
}

# Until the KWSP / PERKESO / LHDN rate tables exist, nothing computes these and
# a payslip has to say so rather than look complete.
STATUTORY_PENDING = (
    "Statutory rates are not configured: EPF, SOCSO, EIS and PCB are not "
    "calculated. This payslip shows gross pay only."
)


def _dec(value, default=ZERO):
    parsed = parse_money(value)
    return default if parsed is None else parsed


def _period_bounds(period):
    try:
        year, month = (int(part) for part in str(period).split("-"))
        start = dt.date(year, month, 1)
    except (ValueError, TypeError):
        raise ValueError("Period must be YYYY-MM.")
    return start, dt.date(year, month, calendar.monthrange(year, month)[1])


class PayrollStore:
    """
    Monthly payroll: gather the timesheet, let it be adjusted, then lock it.

    Locking is the whole point. Work entries price themselves from today's
    salary setup, which is right for a live view and wrong for a month already
    paid, so a locked run keeps its own copy of every figure and every rule it
    used.
    """

    def meta(self):
        return {"statutoryConfigured": False, "statutoryNote": STATUTORY_PENDING}

    def list_runs(self, company=""):
        query = db.select(ErpPayrollRun)
        if company:
            query = query.where(ErpPayrollRun.company == str(company).strip().upper())
        runs = db.session.scalars(
            query.order_by(ErpPayrollRun.period.desc(), ErpPayrollRun.company)
        )
        return [self._public_run(run) for run in runs]

    def get_run(self, run_id, *, with_items=True):
        run = self._load(run_id)
        if not run:
            return None
        payload = self._public_run(run)
        if with_items:
            payload["items"] = [self._public_item(item) for item in self._sorted_items(run)]
        return payload

    def generate(self, company, period, username, *, replace=False):
        """
        Build (or rebuild) a draft from the timesheet for that month.

        Rebuilding discards hand edits, which is why it refuses unless the
        caller says replace -- and always refuses once the run is locked.
        """
        company = str(company or "").strip().upper()
        if not company:
            raise ValueError("Company is required.")
        start, end = _period_bounds(period)
        period = f"{start.year:04d}-{start.month:02d}"

        run = db.session.scalars(
            db.select(ErpPayrollRun).where(
                ErpPayrollRun.company == company, ErpPayrollRun.period == period
            )
        ).first()

        if run and run.status == "locked":
            raise ValueError(f"{company} {period} is locked; it cannot be regenerated.")
        if run and not replace:
            raise ValueError(
                f"A draft already exists for {company} {period}; pass replace to rebuild it."
            )

        timestamp = now()
        if run is None:
            run = ErpPayrollRun(
                id=uuid.uuid4().hex,
                company=company,
                period=period,
                period_start=start,
                period_end=end,
                created_at=timestamp,
                updated_at=timestamp,
                created_by=username or "",
                updated_by=username or "",
            )
            db.session.add(run)
            db.session.flush()
        else:
            for item in list(run.items):
                db.session.delete(item)
            db.session.flush()
            run.updated_at = timestamp
            run.updated_by = username or ""

        rows = db.session.execute(
            db.select(ErpWorkEntry, ErpEmployee, ErpEmployeeSalary)
            .join(ErpEmployee, ErpEmployee.id == ErpWorkEntry.employee_id)
            .outerjoin(ErpEmployeeSalary, ErpEmployeeSalary.employee_id == ErpEmployee.id)
            .where(
                ErpWorkEntry.company == company,
                ErpWorkEntry.work_date >= start,
                ErpWorkEntry.work_date <= end,
            )
        ).all()

        buckets = {}
        for entry, employee, salary in rows:
            bucket = buckets.setdefault(
                employee.id,
                {
                    "employee": employee,
                    "salary": salary,
                    "day_units": ZERO,
                    "ot_hours": ZERO,
                    "overnight_nights": ZERO,
                    "overnight_hours": ZERO,
                    "normal": ZERO,
                    "ot": ZERO,
                    "overnight": ZERO,
                },
            )
            bucket["day_units"] += _dec(entry.day_units)
            bucket["ot_hours"] += _dec(entry.ot_hours)
            bucket["overnight_nights"] += _dec(entry.overnight_nights)
            bucket["overnight_hours"] += _dec(entry.overnight_hours)
            pay = compute_pay(entry, salary)
            if pay["payable"]:
                bucket["normal"] += _dec(pay["normalPay"])
                bucket["ot"] += _dec(pay["otPay"])
                bucket["overnight"] += _dec(pay["overnightPay"])

        for bucket in buckets.values():
            employee, salary = bucket["employee"], bucket["salary"]
            item = ErpPayrollItem(
                id=uuid.uuid4().hex,
                run_id=run.id,
                employee_id=employee.id,
                employee_code=employee.employee_code,
                employee_name=employee.name,
                position=employee.position or "",
                daily_rate=_dec(salary.basic_rate) if salary else ZERO,
                ot_rule=_ot_rule_text(salary) if salary else "No salary setup",
                bank_name=(salary.bank_name if salary else "") or "",
                bank_account_no=(salary.bank_account_no if salary else "") or "",
                epf_member_no=(salary.epf_member_no if salary else "") or "",
                socso_no=(salary.socso_no if salary else "") or "",
                day_units=bucket["day_units"],
                ot_hours=bucket["ot_hours"],
                overnight_nights=bucket["overnight_nights"],
                overnight_hours=bucket["overnight_hours"],
                normal_pay=bucket["normal"],
                ot_pay=bucket["ot"],
                overnight_pay=bucket["overnight"],
                # A monthly allowance is not earned per timesheet row; it is
                # brought in once per run and can be edited off if unwanted.
                fixed_allowance=_dec(salary.fixed_allowance) if salary else ZERO,
            )
            self._recompute(item)
            db.session.add(item)

        db.session.commit()
        return self.get_run(run.id)

    def update_item(self, item_id, username, payload):
        if not isinstance(payload, dict):
            raise ValueError("JSON object payload is required.")

        item = db.session.get(ErpPayrollItem, str(item_id or "").strip())
        if not item:
            return None
        if item.run.status == "locked":
            raise ValueError("This payroll run is locked; its lines cannot be changed.")

        for api_field, column in ITEM_MONEY_FIELDS.items():
            if api_field in payload:
                setattr(item, column, _dec(payload.get(api_field)))
        for api_field, column in ITEM_TEXT_FIELDS.items():
            if api_field in payload:
                setattr(item, column, str(payload.get(api_field) or "").strip())

        self._recompute(item)
        item.run.updated_at = now()
        item.run.updated_by = username or ""
        db.session.commit()
        return self._public_item(item)

    def lock(self, run_id, username):
        run = self._load(run_id)
        if not run:
            return None
        if run.status == "locked":
            raise ValueError("This payroll run is already locked.")
        if not run.items:
            raise ValueError("Nothing to lock: this run has no lines.")

        timestamp = now()
        run.status = "locked"
        run.locked_at = timestamp
        run.locked_by = username or ""
        run.statutory_basis = STATUTORY_PENDING
        run.updated_at = timestamp
        run.updated_by = username or ""
        db.session.commit()
        return self.get_run(run.id)

    def delete_run(self, run_id):
        run = self._load(run_id)
        if not run:
            return None
        if run.status == "locked":
            raise ValueError("A locked payroll run cannot be deleted.")
        payload = self._public_run(run)
        db.session.delete(run)
        db.session.commit()
        return payload

    # ------------------------------------------------------------- internals

    @staticmethod
    def _recompute(item):
        item.gross_pay = (
            _dec(item.normal_pay)
            + _dec(item.ot_pay)
            + _dec(item.overnight_pay)
            + _dec(item.fixed_allowance)
            + _dec(item.adjustment)
        )
        deductions = (
            _dec(item.epf_employee)
            + _dec(item.socso_employee)
            + _dec(item.eis_employee)
            + _dec(item.pcb)
            + _dec(item.other_deduction)
        )
        item.net_pay = item.gross_pay - deductions

    @staticmethod
    def _load(run_id):
        return db.session.get(ErpPayrollRun, str(run_id or "").strip())

    @staticmethod
    def _sorted_items(run):
        return sorted(run.items, key=lambda item: (item.employee_name, item.employee_code))

    def _public_run(self, run):
        items = list(run.items)
        total = lambda attr: float(sum(_dec(getattr(i, attr)) for i in items))
        return {
            "id": run.id,
            "company": run.company,
            "period": run.period,
            "periodStart": to_date_text(run.period_start),
            "periodEnd": to_date_text(run.period_end),
            "status": run.status,
            "locked": run.status == "locked",
            "headcount": len(items),
            "totalDayUnits": total("day_units"),
            "totalOtHours": total("ot_hours"),
            "totalGross": total("gross_pay"),
            "totalDeductions": float(
                sum(
                    _dec(i.epf_employee)
                    + _dec(i.socso_employee)
                    + _dec(i.eis_employee)
                    + _dec(i.pcb)
                    + _dec(i.other_deduction)
                    for i in items
                )
            ),
            "totalNet": total("net_pay"),
            "totalEmployerCost": float(
                sum(
                    _dec(i.gross_pay) + _dec(i.epf_employer) + _dec(i.socso_employer)
                    + _dec(i.eis_employer)
                    for i in items
                )
            ),
            "statutoryConfigured": False,
            "statutoryNote": run.statutory_basis or STATUTORY_PENDING,
            "notes": run.notes,
            "lockedAt": to_iso(run.locked_at) if run.locked_at else "",
            "lockedBy": run.locked_by,
            "createdAt": to_iso(run.created_at),
            "updatedAt": to_iso(run.updated_at),
            "createdBy": run.created_by,
            "updatedBy": run.updated_by,
        }

    @staticmethod
    def _public_item(item):
        return {
            "id": item.id,
            "runId": item.run_id,
            "employeeId": item.employee_id,
            "employeeCode": item.employee_code,
            "name": item.employee_name,
            "position": item.position,
            "dailyRate": money_or_empty(item.daily_rate),
            "otRule": item.ot_rule,
            "bankName": item.bank_name,
            "bankAccountNo": item.bank_account_no,
            "epfMemberNo": item.epf_member_no,
            "socsoNo": item.socso_no,
            "dayUnits": money_or_empty(item.day_units),
            "otHours": money_or_empty(item.ot_hours),
            "overnightNights": money_or_empty(item.overnight_nights),
            "overnightHours": money_or_empty(item.overnight_hours),
            "normalPay": money_or_empty(item.normal_pay),
            "otPay": money_or_empty(item.ot_pay),
            "overnightPay": money_or_empty(item.overnight_pay),
            "fixedAllowance": money_or_empty(item.fixed_allowance),
            "adjustment": money_or_empty(item.adjustment),
            "adjustmentNote": item.adjustment_note,
            "grossPay": money_or_empty(item.gross_pay),
            "epfEmployee": money_or_empty(item.epf_employee),
            "epfEmployer": money_or_empty(item.epf_employer),
            "socsoEmployee": money_or_empty(item.socso_employee),
            "socsoEmployer": money_or_empty(item.socso_employer),
            "eisEmployee": money_or_empty(item.eis_employee),
            "eisEmployer": money_or_empty(item.eis_employer),
            "pcb": money_or_empty(item.pcb),
            "otherDeduction": money_or_empty(item.other_deduction),
            "otherDeductionNote": item.other_deduction_note,
            "netPay": money_or_empty(item.net_pay),
        }
