"""
Attendance, overtime and overnight.

Admin only. The pay figures these endpoints derive come straight from salary
setup, so reading a timesheet is as sensitive as reading a salary.

Two ways in, because both are how the work actually gets recorded:
  - /api/work-entries        one row at a time, filterable
  - /api/work-entries/day    the whole crew for one date and company at once
"""

from flask import Blueprint, jsonify, request

from .common import _require_admin_session, _work_entries


work_entries_bp = Blueprint("work_entries", __name__, url_prefix="/api")


@work_entries_bp.get("/work-entries/meta")
def work_entries_meta():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    return jsonify(_work_entries().meta())


@work_entries_bp.get("/work-entries")
def list_work_entries():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    store = _work_entries()
    entries = store.list_entries(
        # Defaults to the company the session is looking at; pass company=all
        # to see both at once, which is how you spot a double-booked day.
        company="" if request.args.get("company") == "all" else (
            request.args.get("company") or session["database"]
        ),
        employee_key=request.args.get("employee") or "",
        project_key=request.args.get("project") or "",
        date_from=request.args.get("from") or "",
        date_to=request.args.get("to") or "",
    )
    return jsonify({"data": entries, "summary": store.summary(entries)})


@work_entries_bp.post("/work-entries")
def create_work_entry():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    payload.setdefault("company", session["database"])
    try:
        entry = _work_entries().save_entry("", session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(entry), 201


@work_entries_bp.get("/work-entries/day")
def get_day_sheet():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    try:
        sheet = _work_entries().day_sheet(
            request.args.get("date") or "",
            request.args.get("company") or session["database"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(sheet)


@work_entries_bp.post("/work-entries/day")
def save_day_sheet():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        sheet = _work_entries().save_day_sheet(
            payload.get("workDate") or "",
            payload.get("company") or session["database"],
            session["username"],
            payload.get("rows") or [],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(sheet)


@work_entries_bp.get("/work-entries/<entry_id>")
def get_work_entry(entry_id):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    entry = _work_entries().get_entry(entry_id)
    if not entry:
        return jsonify({"error": "work_entry_not_found"}), 404
    return jsonify(entry)


@work_entries_bp.patch("/work-entries/<entry_id>")
@work_entries_bp.put("/work-entries/<entry_id>")
def update_work_entry(entry_id):
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        entry = _work_entries().save_entry(entry_id, session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not entry:
        return jsonify({"error": "work_entry_not_found"}), 404
    return jsonify(entry)


@work_entries_bp.delete("/work-entries/<entry_id>")
def delete_work_entry(entry_id):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    deleted = _work_entries().delete_entry(entry_id)
    if not deleted:
        return jsonify({"error": "work_entry_not_found"}), 404
    return jsonify({"deleted": deleted})
