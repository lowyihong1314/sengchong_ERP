"""
Employee records. ERP-owned, like projects -- AutoCount has no staff master
(its SalesAgent and PurchaseAgent tables are empty).

An employee may be linked to an ERP login, but most of the crew never sign in,
so the link is optional. Editing employees is admin-only; reading is not,
because other modules will want the name list.
"""

from flask import Blueprint, jsonify, request

from .common import _employee_data, _require_admin_session, _require_session


employees_bp = Blueprint("employees", __name__, url_prefix="/api")


@employees_bp.get("/employees/meta")
def employees_meta():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_employee_data().meta())


@employees_bp.get("/employees")
def list_employees():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    active_only = (request.args.get("activeOnly") or "").strip().lower() in {"1", "true", "yes"}
    return jsonify({"data": _employee_data().list_employees(include_inactive=not active_only)})


@employees_bp.post("/employees")
def create_employee():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        employee = _employee_data().create_employee(session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(employee), 201


@employees_bp.get("/employees/<path:employee_key>")
def get_employee(employee_key):
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    employee = _employee_data().get_employee(employee_key)
    if not employee:
        return jsonify({"error": "employee_not_found"}), 404
    return jsonify(employee)


@employees_bp.patch("/employees/<path:employee_key>")
@employees_bp.put("/employees/<path:employee_key>")
def update_employee(employee_key):
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        employee = _employee_data().update_employee(employee_key, session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not employee:
        return jsonify({"error": "employee_not_found"}), 404
    return jsonify(employee)
