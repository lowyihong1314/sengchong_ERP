from models import db
from models.employee_data import ErpEmployee
from models.salary_data import ErpEmployeeSalary

from .values import money_or_empty, now, parse_date, parse_money, to_date_text, to_iso


PAY_TYPES = ("Monthly", "Daily", "Hourly")

MONEY_FIELDS = {"basicRate": "basic_rate", "fixedAllowance": "fixed_allowance"}
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
    "notes": "notes",
}


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


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
        return {"payTypes": list(PAY_TYPES)}

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
            query.order_by(ErpEmployee.status, ErpEmployee.name)
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
