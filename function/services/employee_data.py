import re
import uuid

from sqlalchemy.exc import IntegrityError

from models import db
from models.employee_data import ErpEmployee
from models.user_data import ErpUser

from .values import now, parse_date, to_date_text, to_iso


POSITIONS = (
    "设计",
    "量尺",
    "木工",
    "安装",
    "油漆",
    "采购",
    "行政",
    "司机",
)
STATUSES = ("Active", "On Leave", "Resigned")

# employee_code is not here on purpose: the system issues it and it never
# changes afterwards. Everything else is editable.
EMPLOYEE_COLUMNS = {
    "name": "name",
    "position": "position",
    "phone": "phone",
    "email": "email",
    "icNo": "ic_no",
    "hiredOn": "hired_on",
    "leftOn": "left_on",
    "status": "status",
    "notes": "notes",
}
DATE_FIELDS = {"hiredOn", "leftOn"}


def _normalize_key(value):
    return str(value or "").strip().lower()


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


class EmployeeDataStore:
    """
    People who work for Seng Chong.

    Not the same thing as an ERP login: most of the crew never sign in, and a
    login can exist without an employee record. The two are joined by an
    optional erp_employees.username, and an employee is retired by status
    rather than deleted.
    """

    def meta(self):
        return {"positions": list(POSITIONS), "statuses": list(STATUSES)}

    def list_employees(self, *, include_inactive=True):
        query = db.select(ErpEmployee)
        if not include_inactive:
            query = query.where(ErpEmployee.status == "Active")
        employees = db.session.scalars(
            query.order_by(ErpEmployee.status, ErpEmployee.name, ErpEmployee.employee_code)
        )
        return [self._public_employee(employee) for employee in employees]

    def get_employee(self, employee_key):
        employee = self._find(employee_key)
        return self._public_employee(employee) if employee else None

    def create_employee(self, username, payload):
        fields = self._normalize_payload(payload)
        if not fields.get("name"):
            raise ValueError("Employee name is required.")

        link = self._resolve_username(payload.get("username"))

        timestamp = now()
        employee = ErpEmployee(
            id=uuid.uuid4().hex,
            employee_code="",  # filled in by _create_with_code below
            name=fields["name"],
            username=link,
            position=fields.get("position") or "",
            phone=fields.get("phone") or "",
            email=fields.get("email") or "",
            ic_no=fields.get("icNo") or "",
            hired_on=fields.get("hiredOn"),
            left_on=fields.get("leftOn"),
            status=fields.get("status") or "Active",
            notes=fields.get("notes") or "",
            created_at=timestamp,
            updated_at=timestamp,
            created_by=username or "",
            updated_by=username or "",
        )
        return self._create_with_code(employee)

    def _create_with_code(self, employee, attempts=5):
        """
        Issue the next code and insert.

        Codes are allocated as max+1, which two simultaneous creates can read
        the same value for. The unique constraint stops the duplicate reaching
        the table; this retries around it rather than surfacing a 500.
        """
        for attempt in range(attempts):
            # no_autoflush: reading max+1 issues a SELECT, and an autoflush on
            # that SELECT would push the pending row -- still carrying the code
            # that just collided -- straight back at the unique constraint,
            # raising from here instead of from commit().
            with db.session.no_autoflush:
                employee.employee_code = self._next_employee_code()

            db.session.add(employee)
            try:
                db.session.commit()
                return self._public_employee(employee)
            except IntegrityError:
                # rollback detaches the pending row; the next pass re-adds it
                # once it has a fresh code.
                db.session.rollback()
                if attempt == attempts - 1:
                    raise ValueError("Could not allocate an employee code; try again.")
        return None

    def update_employee(self, employee_key, username, payload):
        employee = self._find(employee_key)
        if not employee:
            return None

        fields = self._normalize_payload(payload)

        # employee_code is system-issued and stays put: it is how a person is
        # referred to on paper, and renaming it would strand those references.
        for api_field, column in EMPLOYEE_COLUMNS.items():
            if api_field not in fields:
                continue
            setattr(employee, column, fields[api_field])

        # An omitted username leaves the link alone; an explicit "" clears it.
        if "username" in payload:
            employee.username = self._resolve_username(
                payload.get("username"), exclude_id=employee.id
            )

        employee.updated_at = now()
        employee.updated_by = username or ""
        db.session.commit()
        return self._public_employee(employee)

    def _find(self, employee_key):
        """Addressable by uuid or by employee code."""
        target = str(employee_key or "").strip()
        if not target:
            return None
        return db.session.scalars(
            db.select(ErpEmployee).where(
                db.or_(ErpEmployee.id == target, ErpEmployee.employee_code == target)
            )
        ).first()

    def _normalize_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("JSON object payload is required.")

        fields = {}
        for api_field in EMPLOYEE_COLUMNS:
            if api_field not in payload:
                continue
            value = payload.get(api_field)
            if api_field in DATE_FIELDS:
                fields[api_field] = parse_date(value)
            else:
                fields[api_field] = _string_or_empty(value)

        status = fields.get("status")
        if status and status not in STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}")

        return fields

    def _resolve_username(self, value, exclude_id=None):
        """
        Validate the optional ERP login this employee signs in with.

        Returns None for "no login". Refuses a username that does not exist,
        and refuses one already taken by another employee -- the unique
        constraint would catch that, but with a far worse error message.
        """
        target = _normalize_key(value)
        if not target:
            return None

        if not db.session.get(ErpUser, target):
            raise ValueError(f"No such ERP user: {value}")

        clash = db.session.scalars(
            db.select(ErpEmployee).where(ErpEmployee.username == target)
        ).first()
        if clash and clash.id != exclude_id:
            raise ValueError(f"User {target} is already linked to {clash.employee_code}")

        return target

    def _next_employee_code(self):
        prefix = "EMP-"
        codes = db.session.scalars(
            db.select(ErpEmployee.employee_code).where(ErpEmployee.employee_code.like(f"{prefix}%"))
        )
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$", re.IGNORECASE)
        current = 0
        for code in codes:
            match = pattern.match(code or "")
            if match:
                current = max(current, int(match.group(1)))
        return f"{prefix}{current + 1:03d}"

    @staticmethod
    def _public_employee(employee):
        user = employee.user
        return {
            "id": employee.id,
            "employeeCode": employee.employee_code,
            "name": employee.name,
            "position": employee.position,
            "phone": employee.phone,
            "email": employee.email,
            "icNo": employee.ic_no,
            "hiredOn": to_date_text(employee.hired_on),
            "leftOn": to_date_text(employee.left_on),
            "status": employee.status,
            "notes": employee.notes,
            # The linked ERP login, if any. displayName and role come from the
            # account so the list never shows a stale copy.
            "username": employee.username or "",
            "userDisplayName": (user.display_name if user else "") or "",
            "userRole": (user.role if user else "") or "",
            "hasLogin": bool(employee.username),
            "createdAt": to_iso(employee.created_at),
            "updatedAt": to_iso(employee.updated_at),
            "createdBy": employee.created_by,
            "updatedBy": employee.updated_by,
        }
