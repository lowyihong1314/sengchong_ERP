"""
Per-employee pay setup.

Admin only, every endpoint -- this is the one module where a read is as
sensitive as a write, so there is no read-for-everyone tier here the way there
is for the employee list.
"""

from flask import Blueprint, jsonify, request

from .common import _require_admin_session, _salary_data


salary_bp = Blueprint("salary", __name__, url_prefix="/api")


@salary_bp.get("/salary/meta")
def salary_meta():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    return jsonify(_salary_data().meta())


@salary_bp.get("/salary")
def list_salaries():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    include_inactive = (request.args.get("includeInactive") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return jsonify({"data": _salary_data().list_salaries(include_inactive=include_inactive)})


@salary_bp.get("/salary/<path:employee_key>")
def get_salary(employee_key):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    salary = _salary_data().get_salary(employee_key)
    if not salary:
        return jsonify({"error": "employee_not_found"}), 404
    return jsonify(salary)


@salary_bp.patch("/salary/<path:employee_key>")
@salary_bp.put("/salary/<path:employee_key>")
@salary_bp.post("/salary/<path:employee_key>")
def save_salary(employee_key):
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        salary = _salary_data().save_salary(employee_key, session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not salary:
        return jsonify({"error": "employee_not_found"}), 404
    return jsonify(salary)
