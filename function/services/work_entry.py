import uuid
from decimal import Decimal

from models import db
from models.employee_data import ErpEmployee
from models.project_data import ErpProject
from models.salary_data import ErpEmployeeSalary
from models.work_entry import ErpWorkEntry

from .values import money_or_empty, now, parse_date, parse_money, to_date_text, to_iso


# How a night away is paid. All four are in use here, so the mode is a
# property of the person rather than a single company-wide formula.
OVERNIGHT_MODES = ("allowance", "hourly", "extra_day", "allowance_plus_hours")

NUMBER_FIELDS = {
    "dayUnits": "day_units",
    "otHours": "ot_hours",
    "overnightNights": "overnight_nights",
    "overnightHours": "overnight_hours",
}

ZERO = Decimal("0.00")


def _dec(value, default=ZERO):
    parsed = parse_money(value)
    return default if parsed is None else parsed


def _round2(value):
    return Decimal(value).quantize(Decimal("0.01"))


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


def compute_pay(entry, salary):
    """
    Work out what one work entry is worth.

    Everyone is day-rated, so:
        normal    = day_units x daily_rate
        overtime  = ot_hours x (daily_rate / ot_divisor) x ot_multiplier

    The divisor is that person's standard hours -- 8, 9 and 10 are all in use
    here -- and the multiplier that goes with it is theirs too.

    Overnight depends on their mode:
        allowance             nights x flat amount
        hourly                hours x hourly base x overnight_multiplier
        extra_day             nights x daily_rate x overnight_day_factor
        allowance_plus_hours  both of the first two

    Returns zeros (and a reason) when the person has no salary set up, rather
    than guessing a rate.
    """
    if salary is None:
        return {
            "dailyRate": "",
            "normalPay": "",
            "otPay": "",
            "overnightPay": "",
            "totalPay": "",
            "payable": False,
            "payableNote": "No salary setup for this employee",
        }

    daily = _dec(salary.basic_rate)
    divisor = _dec(salary.ot_divisor, Decimal("8"))
    if divisor <= 0:
        divisor = Decimal("8")

    hourly_base = daily / divisor

    normal = _dec(entry.day_units) * daily
    overtime = _dec(entry.ot_hours) * hourly_base * _dec(salary.ot_multiplier, Decimal("1.5"))

    mode = salary.overnight_mode or "allowance"
    nights = _dec(entry.overnight_nights)
    night_hours = _dec(entry.overnight_hours)
    allowance = _dec(salary.overnight_allowance)
    night_multiplier = _dec(salary.overnight_multiplier, Decimal("2"))
    day_factor = _dec(salary.overnight_day_factor, Decimal("1"))

    if mode == "hourly":
        overnight = night_hours * hourly_base * night_multiplier
    elif mode == "extra_day":
        overnight = nights * daily * day_factor
    elif mode == "allowance_plus_hours":
        overnight = nights * allowance + night_hours * hourly_base * night_multiplier
    else:  # allowance
        overnight = nights * allowance

    normal, overtime, overnight = _round2(normal), _round2(overtime), _round2(overnight)
    return {
        "dailyRate": float(daily),
        "normalPay": float(normal),
        "otPay": float(overtime),
        "overnightPay": float(overnight),
        "totalPay": float(normal + overtime + overnight),
        "payable": True,
        "payableNote": "",
    }


class WorkEntryStore:
    """
    Attendance and overtime. Admin only, because the pay figures it derives are
    as sensitive as the salary setup they come from.
    """

    def meta(self):
        return {"overnightModes": list(OVERNIGHT_MODES)}

    def list_entries(self, *, company="", employee_key="", project_key="", date_from="", date_to=""):
        query = (
            db.select(ErpWorkEntry, ErpEmployee, ErpEmployeeSalary, ErpProject)
            .join(ErpEmployee, ErpEmployee.id == ErpWorkEntry.employee_id)
            .outerjoin(ErpEmployeeSalary, ErpEmployeeSalary.employee_id == ErpEmployee.id)
            .outerjoin(ErpProject, ErpProject.id == ErpWorkEntry.project_id)
        )

        if company:
            query = query.where(ErpWorkEntry.company == str(company).strip().upper())
        if employee_key:
            employee = self._find_employee(employee_key)
            query = query.where(ErpWorkEntry.employee_id == (employee.id if employee else ""))
        if project_key:
            project = self._find_project(project_key)
            query = query.where(ErpWorkEntry.project_id == (project.id if project else ""))
        start, end = parse_date(date_from), parse_date(date_to)
        if start:
            query = query.where(ErpWorkEntry.work_date >= start)
        if end:
            query = query.where(ErpWorkEntry.work_date <= end)

        rows = db.session.execute(
            query.order_by(
                ErpWorkEntry.work_date.desc(),
                ErpEmployee.name,
                ErpWorkEntry.company,
                ErpWorkEntry.id,
            )
        )
        return [self._public_entry(e, emp, sal, proj) for e, emp, sal, proj in rows]

    def summary(self, entries):
        """Totals for whatever slice the caller just listed."""
        payable = [e for e in entries if e["payable"]]
        add = lambda key: round(sum(float(e[key] or 0) for e in payable), 2)
        return {
            "count": len(entries),
            "dayUnits": round(sum(float(e["dayUnits"] or 0) for e in entries), 2),
            "otHours": round(sum(float(e["otHours"] or 0) for e in entries), 2),
            "overnightNights": round(sum(float(e["overnightNights"] or 0) for e in entries), 2),
            "normalPay": add("normalPay"),
            "otPay": add("otPay"),
            "overnightPay": add("overnightPay"),
            "totalPay": add("totalPay"),
            "missingSalarySetup": sum(1 for e in entries if not e["payable"]),
        }

    def get_entry(self, entry_id):
        row = self._load(entry_id)
        return self._public_entry(*row) if row else None

    def save_entry(self, entry_id, username, payload):
        """Create when entry_id is empty, otherwise update that row."""
        try:
            return self._save_entry(entry_id, username, payload)
        except Exception:
            # A rejected call must leave nothing behind: a half-built row still
            # attached to the session would be flushed by the next query.
            db.session.rollback()
            raise

    def _save_entry(self, entry_id, username, payload):
        if not isinstance(payload, dict):
            raise ValueError("JSON object payload is required.")

        entry = None
        if entry_id:
            entry = db.session.get(ErpWorkEntry, str(entry_id).strip())
            if not entry:
                return None

        timestamp = now()
        if entry is None:
            employee = self._find_employee(payload.get("employeeKey") or payload.get("employeeCode"))
            if not employee:
                raise ValueError("Employee is required.")
            work_date = parse_date(payload.get("workDate"))
            if not work_date:
                raise ValueError("Work date is required.")
            company = _string_or_empty(payload.get("company")).upper()
            if not company:
                raise ValueError("Company is required.")

            entry = ErpWorkEntry(
                id=uuid.uuid4().hex,
                employee_id=employee.id,
                work_date=work_date,
                company=company,
                created_at=timestamp,
                updated_at=timestamp,
                created_by=username or "",
                updated_by=username or "",
            )
            db.session.add(entry)
        else:
            if "workDate" in payload:
                work_date = parse_date(payload.get("workDate"))
                if not work_date:
                    raise ValueError("Work date is required.")
                entry.work_date = work_date
            if "company" in payload:
                company = _string_or_empty(payload.get("company")).upper()
                if not company:
                    raise ValueError("Company is required.")
                entry.company = company

        if "projectKey" in payload or "projectCode" in payload:
            key = payload.get("projectKey", payload.get("projectCode"))
            entry.project_id = self._resolve_project_id(key, entry.company)

        for api_field, column in NUMBER_FIELDS.items():
            if api_field in payload:
                value = _dec(payload.get(api_field))
                if value < 0:
                    raise ValueError(f"{api_field} cannot be negative")
                setattr(entry, column, value)

        if "note" in payload:
            entry.note = _string_or_empty(payload.get("note"))

        entry.updated_at = timestamp
        entry.updated_by = username or ""
        db.session.commit()

        return self.get_entry(entry.id)

    def delete_entry(self, entry_id):
        entry = db.session.get(ErpWorkEntry, str(entry_id or "").strip())
        if not entry:
            return None
        payload = self.get_entry(entry.id)
        db.session.delete(entry)
        db.session.commit()
        return payload

    def day_sheet(self, work_date, company):
        """
        Every active employee for one date at one company, with whatever is
        already recorded. This is what the batch screen edits: the foreman goes
        down the list once at the end of the day.
        """
        target = parse_date(work_date)
        if not target:
            raise ValueError("Work date is required.")
        company = _string_or_empty(company).upper()
        if not company:
            raise ValueError("Company is required.")

        employees = db.session.scalars(
            db.select(ErpEmployee)
            .where(ErpEmployee.status == "Active")
            .order_by(ErpEmployee.name, ErpEmployee.employee_code)
        ).all()

        existing = {}
        rows = db.session.execute(
            db.select(ErpWorkEntry)
            .where(ErpWorkEntry.work_date == target, ErpWorkEntry.company == company)
            .order_by(ErpWorkEntry.id)
        )
        for (entry,) in rows:
            existing.setdefault(entry.employee_id, entry)

        sheet = []
        for employee in employees:
            entry = existing.get(employee.id)
            salary = employee.salary
            row = {
                "employeeId": employee.id,
                "employeeCode": employee.employee_code,
                "name": employee.name,
                "position": employee.position,
                "entryId": entry.id if entry else "",
                "dayUnits": money_or_empty(entry.day_units) if entry else 0.0,
                "otHours": money_or_empty(entry.ot_hours) if entry else 0.0,
                "overnightNights": money_or_empty(entry.overnight_nights) if entry else 0.0,
                "overnightHours": money_or_empty(entry.overnight_hours) if entry else 0.0,
                "projectCode": (entry.project.project_code if entry and entry.project else ""),
                "note": entry.note if entry else "",
            }
            row.update(compute_pay(entry, salary) if entry else {
                "dailyRate": money_or_empty(salary.basic_rate) if salary else "",
                "normalPay": 0.0, "otPay": 0.0, "overnightPay": 0.0, "totalPay": 0.0,
                "payable": salary is not None,
                "payableNote": "" if salary else "No salary setup for this employee",
            })
            sheet.append(row)

        return {"workDate": to_date_text(target), "company": company, "data": sheet}

    def save_day_sheet(self, work_date, company, username, rows):
        """
        Apply one batch of edits. A row with nothing recorded deletes any entry
        that existed, so clearing a mistake is the same gesture as making one.

        All or nothing: one bad row rolls the whole batch back rather than
        leaving the sheet half applied.
        """
        try:
            return self._save_day_sheet(work_date, company, username, rows)
        except Exception:
            db.session.rollback()
            raise

    def _save_day_sheet(self, work_date, company, username, rows):
        target = parse_date(work_date)
        if not target:
            raise ValueError("Work date is required.")
        company = _string_or_empty(company).upper()
        if not company:
            raise ValueError("Company is required.")
        if not isinstance(rows, list):
            raise ValueError("rows must be a list")

        timestamp = now()
        saved = deleted = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            employee = self._find_employee(row.get("employeeId") or row.get("employeeCode"))
            if not employee:
                continue

            values = {column: _dec(row.get(api)) for api, column in NUMBER_FIELDS.items()}
            if any(v < 0 for v in values.values()):
                raise ValueError(f"Negative value for {employee.employee_code}")
            empty = all(v == ZERO for v in values.values())

            entry = db.session.scalars(
                db.select(ErpWorkEntry).where(
                    ErpWorkEntry.employee_id == employee.id,
                    ErpWorkEntry.work_date == target,
                    ErpWorkEntry.company == company,
                )
            ).first()

            if empty:
                if entry:
                    db.session.delete(entry)
                    deleted += 1
                continue

            if entry is None:
                entry = ErpWorkEntry(
                    id=uuid.uuid4().hex,
                    employee_id=employee.id,
                    work_date=target,
                    company=company,
                    created_at=timestamp,
                    updated_at=timestamp,
                    created_by=username or "",
                    updated_by=username or "",
                )
                db.session.add(entry)

            for column, value in values.items():
                setattr(entry, column, value)
            if "projectCode" in row or "projectKey" in row:
                entry.project_id = self._resolve_project_id(
                    row.get("projectKey", row.get("projectCode")), company
                )
            if "note" in row:
                entry.note = _string_or_empty(row.get("note"))
            entry.updated_at = timestamp
            entry.updated_by = username or ""
            saved += 1

        db.session.commit()
        result = self.day_sheet(work_date, company)
        result.update({"saved": saved, "deleted": deleted})
        return result

    # ---------------------------------------------------------------- lookups

    @staticmethod
    def _find_employee(key):
        target = str(key or "").strip()
        if not target:
            return None
        return db.session.scalars(
            db.select(ErpEmployee).where(
                db.or_(ErpEmployee.id == target, ErpEmployee.employee_code == target)
            )
        ).first()

    @staticmethod
    def _find_project(key, company=""):
        target = str(key or "").strip()
        if not target:
            return None
        query = db.select(ErpProject).where(
            db.or_(ErpProject.id == target, ErpProject.project_code == target)
        )
        if company:
            query = query.where(ErpProject.company == company)
        return db.session.scalars(query).first()

    def _resolve_project_id(self, key, company):
        """Blank clears the link; an unknown code is refused rather than dropped."""
        target = str(key or "").strip()
        if not target:
            return None
        project = self._find_project(target, company)
        if not project:
            raise ValueError(f"No such project for {company}: {target}")
        return project.id

    @staticmethod
    def _load(entry_id):
        return db.session.execute(
            db.select(ErpWorkEntry, ErpEmployee, ErpEmployeeSalary, ErpProject)
            .join(ErpEmployee, ErpEmployee.id == ErpWorkEntry.employee_id)
            .outerjoin(ErpEmployeeSalary, ErpEmployeeSalary.employee_id == ErpEmployee.id)
            .outerjoin(ErpProject, ErpProject.id == ErpWorkEntry.project_id)
            .where(ErpWorkEntry.id == str(entry_id or "").strip())
        ).first()

    @staticmethod
    def _public_entry(entry, employee, salary, project):
        payload = {
            "id": entry.id,
            "employeeId": employee.id,
            "employeeCode": employee.employee_code,
            "name": employee.name,
            "position": employee.position,
            "workDate": to_date_text(entry.work_date),
            "company": entry.company,
            "projectId": entry.project_id or "",
            "projectCode": project.project_code if project else "",
            "projectTitle": project.title if project else "",
            "dayUnits": money_or_empty(entry.day_units),
            "otHours": money_or_empty(entry.ot_hours),
            "overnightNights": money_or_empty(entry.overnight_nights),
            "overnightHours": money_or_empty(entry.overnight_hours),
            "note": entry.note,
            "createdAt": to_iso(entry.created_at),
            "updatedAt": to_iso(entry.updated_at),
            "createdBy": entry.created_by,
            "updatedBy": entry.updated_by,
        }
        payload.update(compute_pay(entry, salary))
        return payload
