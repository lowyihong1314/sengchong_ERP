"""
Monthly payroll and payslip PDFs. Admin only, every endpoint.

A run is generated from the timesheet, adjusted by hand while it is a draft,
then locked. Locking snapshots every figure, so reprinting an old payslip
after a raise still shows what was actually paid.
"""

from flask import Blueprint, jsonify, request, send_file
from io import BytesIO

from ..services.payslip_pdf import build_payslips
from .common import _find_company, _payroll, _require_admin_session


payroll_bp = Blueprint("payroll", __name__, url_prefix="/api")


@payroll_bp.get("/payroll/meta")
def payroll_meta():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    return jsonify(_payroll().meta())


@payroll_bp.get("/payroll")
def list_payroll_runs():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    company = "" if request.args.get("company") == "all" else (
        request.args.get("company") or session["database"]
    )
    return jsonify({"data": _payroll().list_runs(company)})


@payroll_bp.post("/payroll")
def generate_payroll_run():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        run = _payroll().generate(
            payload.get("company") or session["database"],
            payload.get("period") or "",
            session["username"],
            replace=bool(payload.get("replace")),
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(run), 201


@payroll_bp.get("/payroll/<run_id>")
def get_payroll_run(run_id):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    run = _payroll().get_run(run_id)
    if not run:
        return jsonify({"error": "payroll_run_not_found"}), 404
    return jsonify(run)


@payroll_bp.post("/payroll/<run_id>/lock")
def lock_payroll_run(run_id):
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    try:
        run = _payroll().lock(run_id, session["username"])
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not run:
        return jsonify({"error": "payroll_run_not_found"}), 404
    return jsonify(run)


@payroll_bp.delete("/payroll/<run_id>")
def delete_payroll_run(run_id):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    try:
        deleted = _payroll().delete_run(run_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not deleted:
        return jsonify({"error": "payroll_run_not_found"}), 404
    return jsonify({"deleted": deleted})


@payroll_bp.patch("/payroll/items/<item_id>")
def update_payroll_item(item_id):
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        item = _payroll().update_item(item_id, session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not item:
        return jsonify({"error": "payroll_item_not_found"}), 404
    return jsonify(item)


@payroll_bp.get("/payroll/<run_id>/payslips.pdf")
def payslips_pdf(run_id):
    """
    Every payslip in the run, one to a page. `employee=<code>` narrows it to
    one person, which is what the reprint-for-one-worker case needs.
    """
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    run = _payroll().get_run(run_id)
    if not run:
        return jsonify({"error": "payroll_run_not_found"}), 404

    items = run["items"]
    wanted = (request.args.get("employee") or "").strip()
    if wanted:
        items = [i for i in items if i["employeeCode"].lower() == wanted.lower()]
        if not items:
            return jsonify({"error": "employee_not_in_run"}), 404
    if not items:
        return jsonify({"error": "payroll_run_empty"}), 400

    company = _find_company(run["company"]) or {}
    pdf = build_payslips(run, items, company_label=company.get("label") or run["company"])

    suffix = f"-{wanted}" if wanted else ""
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"payslips-{run['company']}-{run['period']}{suffix}.pdf",
    )
