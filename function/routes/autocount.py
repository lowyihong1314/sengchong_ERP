"""
Everything that talks to AutoCount: SDK login, PDF export, bank
reconciliation, and the generic resource passthrough.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Blueprint, after_this_request, current_app, jsonify, request, send_file


from .auth import auth_login
from .common import (
    _refresh_requested,
    _require_session,
    _sdk,
    _settings,
    _sql_reader,
)
from .projects import _number_value, _parse_date

autocount_bp = Blueprint("autocount", __name__, url_prefix="/api/autocount")


PDF_RESOURCES = {"invoices", "ar-payments", "quotations", "purchase-orders", "debtors"}

def _bank_recon_state(row):
    status = str(row.get("bankReconStatus") or "").strip()
    label = str(row.get("bankReconStatusLabel") or "").strip().lower()
    return "reconciled" if status == "1" or label == "reconciled" else "open"

def _bank_recon_label(state):
    return "Reconciled" if state == "reconciled" else "Open"

@autocount_bp.post("/login")
def autocount_login():
    return auth_login()

@autocount_bp.get("/<resource>/pdf")
def autocount_pdf_by_query(resource):
    return _send_autocount_pdf(resource, request.args.get("key") or "")

@autocount_bp.get("/<resource>/<path:key>/pdf")
def autocount_pdf(resource, key):
    return _send_autocount_pdf(resource, key)

@autocount_bp.post("/invoices/payment-request/pdf")
def invoice_payment_request_pdf():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or payload.get("invoiceDocNo") or "").strip()
    if not key:
        return jsonify({"error": "Invoice key is required."}), 400

    try:
        amount = Decimal(str(payload.get("amount") or "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return jsonify({"error": "Invalid amount."}), 400

    if amount <= 0:
        return jsonify({"error": "Request amount must be greater than zero."}), 400

    ok, pdf_result = _sdk().export_invoice_payment_request_pdf(key, amount, session)
    if not ok:
        status_code = 400 if str(pdf_result.get("error", "")).startswith("Request amount") else 502
        return jsonify(pdf_result), status_code

    local_path = Path(pdf_result["local_path"])
    if not local_path.exists():
        return jsonify({"error": "Payment request PDF file was not created."}), 502

    @after_this_request
    def cleanup(response):
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Unable to remove payment request PDF %s", local_path)
        return response

    return send_file(
        local_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_result.get("filename") or f"payment-request-{key}.pdf",
    )

@autocount_bp.post("/bank-transactions/reconcile-preview")
def bank_transactions_reconcile_preview():
    settings = _settings()
    if "bank-transactions" not in settings.allowed_resources:
        return jsonify({"error": "resource_not_allowed"}), 404

    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON object payload is required."}), 400

    keys = []
    seen = set()
    for raw_key in payload.get("bankTransKeys") or payload.get("keys") or []:
        key = str(raw_key or "").strip()
        normalized = key.lower()
        if key and normalized not in seen:
            keys.append(key)
            seen.add(normalized)

    if not keys:
        return jsonify({"error": "At least one bank transaction is required."}), 400
    if len(keys) > 200:
        return jsonify({"error": "Preview supports up to 200 bank transactions."}), 400

    recon_status = str(payload.get("reconStatus") or "reconciled").strip().lower()
    if recon_status not in {"reconciled", "open"}:
        return jsonify({"error": "Recon status must be reconciled or open."}), 400

    statement_date_text = str(payload.get("statementDate") or "").strip()
    statement_date = _parse_date(statement_date_text) if statement_date_text else datetime.today().date()
    if not statement_date:
        return jsonify({"error": "Invalid statement date."}), 400
    statement_date_text = statement_date.isoformat()

    ok, result = _sql_reader().list_bank_transactions_by_keys(session, keys)
    if not ok:
        return jsonify(result), 502

    rows = result.get("data") or []
    rows_by_key = {
        str(row.get("bankTransKey") or "").strip().lower(): row
        for row in rows
        if str(row.get("bankTransKey") or "").strip()
    }
    rows_by_doc_no = {
        str(row.get("docNo") or "").strip().lower(): row
        for row in rows
        if str(row.get("docNo") or "").strip()
    }

    target_status_value = 1 if recon_status == "reconciled" else 0
    target_label = _bank_recon_label(recon_status)
    target_statement_date = statement_date_text if recon_status == "reconciled" else ""
    preview_rows = []
    missing_keys = []
    total_amount = 0

    for key in keys:
        lookup_key = key.lower()
        row = rows_by_key.get(lookup_key) or rows_by_doc_no.get(lookup_key)
        if not row:
            missing_keys.append(key)
            continue

        current_state = _bank_recon_state(row)
        current_statement_date = row.get("bankStatementDate") or ""
        next_state = recon_status
        amount = _number_value(row.get("bankAmount")) or 0
        total_amount += amount

        preview_rows.append(
            {
                "bankTransKey": row.get("bankTransKey"),
                "docNo": row.get("docNo"),
                "docDate": row.get("docDate"),
                "bankAccount": row.get("bankAccount"),
                "bankAccountName": row.get("bankAccountName"),
                "description": row.get("description"),
                "bankAmount": row.get("bankAmount"),
                "cashBookKey": row.get("cashBookKey"),
                "cashBookDocNo": row.get("cashBookDocNo"),
                "sourceDocumentModule": row.get("sourceDocumentModule"),
                "sourceDocumentKey": row.get("sourceDocumentKey"),
                "sourceDocumentNo": row.get("sourceDocumentNo"),
                "currentReconStatus": row.get("bankReconStatus"),
                "currentReconStatusLabel": _bank_recon_label(current_state),
                "currentBankStatementDate": current_statement_date,
                "nextReconStatus": target_status_value,
                "nextReconStatusLabel": target_label,
                "nextBankStatementDate": target_statement_date,
                "action": (
                    "unchanged"
                    if current_state == next_state
                    and str(current_statement_date or "")[:10] == target_statement_date
                    else "update"
                ),
            }
        )

    return jsonify(
        {
            "ok": True,
            "mode": "preview",
            "writeEnabled": False,
            "writePath": "autocount_api_required",
            "statementDate": statement_date_text,
            "reconStatus": recon_status,
            "requestedCount": len(keys),
            "matchedCount": len(preview_rows),
            "missingKeys": missing_keys,
            "totalAmount": round(total_amount, 2),
            "data": preview_rows,
        }
    )

@autocount_bp.post("/bank-transactions/reconcile")
def bank_transactions_reconcile():
    settings = _settings()
    if "bank-transactions" not in settings.allowed_resources:
        return jsonify({"error": "resource_not_allowed"}), 404

    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON object payload is required."}), 400

    keys = []
    seen = set()
    for raw_key in payload.get("bankTransKeys") or payload.get("keys") or []:
        key = str(raw_key or "").strip()
        normalized = key.lower()
        if key and normalized not in seen:
            keys.append(key)
            seen.add(normalized)

    if not keys:
        return jsonify({"error": "At least one bank transaction is required."}), 400
    if len(keys) > 200:
        return jsonify({"error": "Reconcile supports up to 200 bank transactions."}), 400

    statement_date_text = str(payload.get("statementDate") or "").strip()
    statement_date = _parse_date(statement_date_text)
    if not statement_date:
        return jsonify({"error": "Statement date is required."}), 400
    statement_date_text = statement_date.isoformat()

    raw_actual_balance = payload.get("actualBankStatementBalance")
    if raw_actual_balance is None or str(raw_actual_balance).strip() == "":
        return jsonify({"error": "Actual bank statement balance is required."}), 400
    try:
        actual_balance = Decimal(str(raw_actual_balance))
    except (InvalidOperation, ValueError):
        return jsonify({"error": "Invalid actual bank statement balance."}), 400

    ok, result = _sql_reader().list_bank_transactions_by_keys(session, keys)
    if not ok:
        return jsonify(result), 502

    rows = result.get("data") or []
    rows_by_key = {
        str(row.get("bankTransKey") or "").strip().lower(): row
        for row in rows
        if str(row.get("bankTransKey") or "").strip()
    }

    selected_rows = []
    missing_keys = []
    for key in keys:
        row = rows_by_key.get(key.lower())
        if row:
            selected_rows.append(row)
        else:
            missing_keys.append(key)

    if missing_keys:
        return jsonify({"error": "Some bank transactions were not found.", "missingKeys": missing_keys}), 400

    bank_accounts = {
        str(row.get("bankAccount") or "").strip()
        for row in selected_rows
        if str(row.get("bankAccount") or "").strip()
    }
    if len(bank_accounts) != 1:
        return jsonify({"error": "Select bank transactions from one bank account only."}), 400
    bank_account = next(iter(bank_accounts))

    already_reconciled = [
        row.get("bankTransKey")
        for row in selected_rows
        if _bank_recon_state(row) == "reconciled"
    ]
    if already_reconciled:
        return (
            jsonify(
                {
                    "error": "Some bank transactions are already reconciled.",
                    "bankTransKeys": already_reconciled,
                }
            ),
            400,
        )

    future_keys = []
    for row in selected_rows:
        doc_date = _parse_date(row.get("docDate"))
        if doc_date and doc_date > statement_date:
            future_keys.append(row.get("bankTransKey"))
    if future_keys:
        return (
            jsonify(
                {
                    "error": "Bank transaction date cannot be later than statement date.",
                    "bankTransKeys": future_keys,
                }
            ),
            400,
        )

    ok, result = _sdk().reconcile_bank_transactions(
        {
            "bankTransKeys": keys,
            "bankAccount": bank_account,
            "statementDate": statement_date_text,
            "actualBankStatementBalance": str(actual_balance),
        },
        session,
    )
    if not ok:
        return jsonify(result), 502

    return jsonify(result)

def _send_autocount_pdf(resource, key):
    settings = _settings()

    if resource not in settings.allowed_resources or resource not in PDF_RESOURCES:
        return (
            jsonify(
                {
                    "error": "pdf_export_not_supported",
                    "supported_resources": sorted(PDF_RESOURCES),
                }
            ),
            404,
        )

    if not key:
        return jsonify({"error": "Document key is required."}), 400

    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    ok, result = _sdk().export_pdf(resource, key, session)
    if not ok:
        return jsonify(result), 502

    local_path = Path(result["local_path"])
    if not local_path.exists():
        return jsonify({"error": "PDF file was not created."}), 502

    @after_this_request
    def cleanup(response):
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Unable to remove PDF export %s", local_path)
        return response

    return send_file(
        local_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=result.get("filename") or f"{resource}-{key}.pdf",
    )

@autocount_bp.route(
    "/<resource>",
    defaults={"subpath": ""},
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@autocount_bp.route(
    "/<resource>/<path:subpath>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def autocount_resource(resource, subpath):
    settings = _settings()

    if resource not in settings.allowed_resources:
        return (
            jsonify(
                {
                    "error": "resource_not_allowed",
                    "allowed_resources": sorted(settings.allowed_resources),
                }
            ),
            404,
        )

    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    if request.method == "GET" and subpath:
        ok, result = _sql_reader().get_resource_detail(resource, subpath, session)
        if not ok:
            ok, result = _sdk().get_resource_detail(
                resource,
                subpath,
                session,
                refresh=_refresh_requested(),
            )
        if not ok:
            return jsonify(result), 502
        return jsonify(result)

    if request.method == "GET":
        ok, result = _sql_reader().list_resource(resource, session)
        if not ok:
            ok, result = _sdk().list_resource(resource, session, refresh=_refresh_requested())
        if not ok:
            return jsonify(result), 502
        return jsonify(result)

    if request.method == "POST" and not subpath:
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON object payload is required."}), 400

        ok, result = _sdk().create_resource(resource, payload, session)
        if not ok:
            return jsonify(result), 502
        return jsonify(result), 201

    return (
        jsonify(
            {
                "error": "method_not_supported",
                "detail": "Only list, detail, and create actions are available for this resource.",
            }
        ),
        405,
    )
