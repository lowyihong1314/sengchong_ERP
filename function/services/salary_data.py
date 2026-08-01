from models import db
from models.employee_data import ErpEmployee
from models.salary_data import ErpEmployeeSalary

from .values import money_or_empty, now, parse_date, parse_money, to_date_text, to_iso


PAY_TYPES = ("Monthly", "Daily", "Hourly")
# How a night away is paid. All four are in use, so it is a per-person mode.
OVERNIGHT_MODES = ("allowance", "hourly", "extra_day", "allowance_plus_hours")

MONEY_FIELDS = {
    "basicRate": "basic_rate",
    "fixedAllowance": "fixed_allowance",
    # The OT hourly base is dailyRate / otDivisor; the divisor is that
    # person's standard hours (8, 9 and 10 are all in use here).
    "otDivisor": "ot_divisor",
    "otMultiplier": "ot_multiplier",
    "overnightAllowance": "overnight_allowance",
    "overnightMultiplier": "overnight_multiplier",
    "overnightDayFactor": "overnight_day_factor",
}
FLAG_FIELDS = {"epfContributing": "epf_contributing", "socsoContributing": "socso_contributing"}
DATE_FIELDS = {"effectiveFrom": "effective_from"}
TEXT_FIELDS = {
    "payType": "pay_type",
    "allowanceNote": "allowance_note",
    "epfMemberNo": "epf_member_no",
    "socsoNo": "socso_no",
    "taxNo": "tax_no",
    "bankName": "bank_name",
    "bankAccountNo": "bank_account_no",
    "overnightMode": "overnight_mode",
    "notes": "notes",
}


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


def _ot_rule_text(salary):
    divisor = salary.ot_divisor or 8
    return (
        f"OT = daily / {_trim(divisor)} x {_trim(salary.ot_multiplier or 0)}"
        f"  |  overnight: {_overnight_text(salary)}"
    )


def _overnight_text(salary):
    mode = salary.overnight_mode or "allowance"
    if mode == "hourly":
        return f"hours x (daily / {_trim(salary.ot_divisor or 8)}) x {_trim(salary.overnight_multiplier or 0)}"
    if mode == "extra_day":
        return f"{_trim(salary.overnight_day_factor or 0)} x daily per night"
    if mode == "allowance_plus_hours":
        return (
            f"{_trim(salary.overnight_allowance or 0)} per night + "
            f"hours x (daily / {_trim(salary.ot_divisor or 8)}) x {_trim(salary.overnight_multiplier or 0)}"
        )
    return f"{_trim(salary.overnight_allowance or 0)} per night"


def _trim(value):
    """2 dp columns read badly as 8.00 / 1.50 in a rule sentence."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class SalaryDataStore:
    """
    Per-employee pay setup: what they earn and the identifiers a payroll run
    needs. Admin-only at the route layer.

    No statutory amount is stored here. EPF, SOCSO, EIS and PCB get calculated
    during a payroll run from maintained rate tables, so a rate change never
    means editing every employee.
    """

    def meta(self):
        return {"payTypes": list(PAY_TYPES), "overnightModes": list(OVERNIGHT_MODES)}

    def list_salaries(self, *, include_inactive=False):
        """
        Every employee with their setup, whether or not one exists yet, so the
        screen doubles as "who still needs setting up".
        """
        query = db.select(ErpEmployee).outerjoin(
            ErpEmployeeSalary, ErpEmployeeSalary.employee_id == ErpEmployee.id
        )
        if not include_inactive:
            query = query.where(ErpEmployee.status == "Active")

        employees = db.session.scalars(
            query.order_by(ErpEmployee.status, ErpEmployee.name, ErpEmployee.employee_code)
        ).unique()
        return [self._public_salary(employee, employee.salary) for employee in employees]

    def get_salary(self, employee_key):
        employee = self._find_employee(employee_key)
        if not employee:
            return None
        return self._public_salary(employee, employee.salary)

    def save_salary(self, employee_key, username, payload):
        """Create or update in one call -- there is at most one row per person."""
        if not isinstance(payload, dict):
            raise ValueError("JSON object payload is required.")

        employee = self._find_employee(employee_key)
        if not employee:
            return None

        pay_type = _string_or_empty(payload.get("payType")) or None
        if pay_type and pay_type not in PAY_TYPES:
            raise ValueError(f"Pay type must be one of: {', '.join(PAY_TYPES)}")

        mode = _string_or_empty(payload.get("overnightMode")) or None
        if mode and mode not in OVERNIGHT_MODES:
            raise ValueError(f"Overnight mode must be one of: {', '.join(OVERNIGHT_MODES)}")

        if "otDivisor" in payload:
            divisor = parse_money(payload.get("otDivisor"))
            if divisor is not None and divisor <= 0:
                raise ValueError("otDivisor must be greater than zero")

        for api_field in MONEY_FIELDS:
            if api_field in payload and parse_money(payload.get(api_field)) is None:
                if _string_or_empty(payload.get(api_field)) != "":
                    raise ValueError(f"{api_field} must be a number")

        timestamp = now()
        salary = employee.salary
        if salary is None:
            salary = ErpEmployeeSalary(
                employee_id=employee.id, created_at=timestamp, created_by=username or ""
            )
            db.session.add(salary)

        for api_field, column in TEXT_FIELDS.items():
            if api_field in payload:
                setattr(salary, column, _string_or_empty(payload.get(api_field)))
        for api_field, column in MONEY_FIELDS.items():
            if api_field in payload:
                setattr(salary, column, parse_money(payload.get(api_field)) or 0)
        for api_field, column in FLAG_FIELDS.items():
            if api_field in payload:
                setattr(salary, column, _bool(payload.get(api_field)))
        for api_field, column in DATE_FIELDS.items():
            if api_field in payload:
                setattr(salary, column, parse_date(payload.get(api_field)))

        if not salary.pay_type:
            salary.pay_type = "Monthly"
        if not salary.overnight_mode:
            salary.overnight_mode = "allowance"
        # A zero divisor would make the OT rate infinite; fall back to 8.
        if not salary.ot_divisor or salary.ot_divisor <= 0:
            salary.ot_divisor = 8

        salary.updated_at = timestamp
        salary.updated_by = username or ""
        db.session.commit()

        return self._public_salary(employee, salary)

    @staticmethod
    def _find_employee(employee_key):
        target = str(employee_key or "").strip()
        if not target:
            return None
        return db.session.scalars(
            db.select(ErpEmployee).where(
                db.or_(ErpEmployee.id == target, ErpEmployee.employee_code == target)
            )
        ).first()

    @staticmethod
    def _public_salary(employee, salary):
        payload = {
            "employeeId": employee.id,
            "employeeCode": employee.employee_code,
            "name": employee.name,
            "position": employee.position,
            "status": employee.status,
            # False until someone fills the form in; the list shows both so
            # nobody is quietly missed at payroll time.
            "hasSalarySetup": salary is not None,
        }
        if salary is None:
            payload.update(
                {
                    "payType": "",
                    "basicRate": "",
                    "fixedAllowance": "",
                    "allowanceNote": "",
                    "epfMemberNo": "",
                    "socsoNo": "",
                    "taxNo": "",
                    "epfContributing": True,
                    "socsoContributing": True,
                    "otDivisor": "",
                    "otMultiplier": "",
                    "overnightMode": "",
                    "overnightAllowance": "",
                    "overnightMultiplier": "",
                    "overnightDayFactor": "",
                    "bankName": "",
                    "bankAccountNo": "",
                    "effectiveFrom": "",
                    "notes": "",
                    "createdAt": "",
                    "updatedAt": "",
                    "createdBy": "",
                    "updatedBy": "",
                }
            )
            return payload

        payload.update(
            {
                "payType": salary.pay_type,
                "basicRate": money_or_empty(salary.basic_rate),
                "fixedAllowance": money_or_empty(salary.fixed_allowance),
                "allowanceNote": salary.allowance_note,
                "epfMemberNo": salary.epf_member_no,
                "socsoNo": salary.socso_no,
                "taxNo": salary.tax_no,
                "epfContributing": bool(salary.epf_contributing),
                "socsoContributing": bool(salary.socso_contributing),
                "otDivisor": money_or_empty(salary.ot_divisor),
                "otMultiplier": money_or_empty(salary.ot_multiplier),
                "overnightMode": salary.overnight_mode,
                "overnightAllowance": money_or_empty(salary.overnight_allowance),
                "overnightMultiplier": money_or_empty(salary.overnight_multiplier),
                "overnightDayFactor": money_or_empty(salary.overnight_day_factor),
                # Spelled out so the setup screen can show what the rule means
                # without the reader reconstructing it from four numbers.
                "otRuleText": _ot_rule_text(salary),
                "bankName": salary.bank_name,
                "bankAccountNo": salary.bank_account_no,
                "effectiveFrom": to_date_text(salary.effective_from),
                "notes": salary.notes,
                "createdAt": to_iso(salary.created_at),
                "updatedAt": to_iso(salary.updated_at),
                "createdBy": salary.created_by,
                "updatedBy": salary.updated_by,
            }
        )
        return payload
