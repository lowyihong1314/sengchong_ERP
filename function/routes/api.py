import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from flask import Blueprint, after_this_request, current_app, jsonify, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError

from ..services import rdp_allow_list


api_bp = Blueprint("api", __name__)
PDF_RESOURCES = {"invoices", "ar-payments", "quotations", "purchase-orders", "debtors"}
WEBSITE_ASSET_KINDS = {"service", "contact"}
WEBSITE_ASSET_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PROJECT_DOCUMENT_CANDIDATE_MODULES = {
    "quotations": {
        "label": "Quotation",
        "status": "Quoted",
        "docField": "quotationDocNo",
        "amountField": "quotedTotal",
        "sourceAmountField": "finalTotal",
    },
    "invoices": {
        "label": "Invoice",
        "status": "Confirmed",
        "docField": "invoiceDocNo",
        "amountField": "quotedTotal",
        "sourceAmountField": "netTotal",
    },
}


def _settings():
    return current_app.config["SETTINGS"]


def _sdk():
    return current_app.extensions["autocount_sdk"]


def _sql_reader():
    return current_app.extensions["sql_reader"]


def _sessions():
    return current_app.extensions["sessions"]


def _user_data():
    return current_app.extensions["user_data"]


def _project_data():
    return current_app.extensions["project_data"]


def _project_photos():
    return current_app.extensions["project_photos"]


def _sengchong_content():
    return current_app.extensions["sengchong_content"]


def _bearer_token():
    auth_header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if auth_header.startswith(prefix):
        return auth_header[len(prefix) :].strip()
    return ""


def _request_token():
    return _bearer_token() or (request.args.get("token") or "").strip()


def _require_session():
    session = _sessions().get(_bearer_token())
    if not session:
        return None, (jsonify({"error": "not_authenticated"}), 401)
    return session, None


def _require_admin_session():
    session, auth_error = _require_session()
    if auth_error:
        return None, auth_error
    if str(session.get("role") or "").strip().lower() != "admin":
        return None, (jsonify({"error": "admin_required"}), 403)
    return session, None


def _require_request_session():
    session = _sessions().get(_request_token())
    if not session:
        return None, (jsonify({"error": "not_authenticated"}), 401)
    return session, None


def _refresh_requested():
    value = (request.args.get("refresh") or "").strip().lower()
    if value in {"1", "true", "yes", "force"}:
        return True

    cache_control = (request.headers.get("Cache-Control") or "").lower()
    return "no-cache" in cache_control


def _website_asset_dir(kind):
    kind = str(kind or "").strip().lower()
    if kind not in WEBSITE_ASSET_KINDS:
        raise ValueError("invalid_asset_kind")
    return _settings().sengchong_static_dir / "images" / kind


def _website_asset_url(kind, filename):
    return f"/static/images/{kind}/{filename}"


def _safe_asset_stem(filename, fallback):
    stem = Path(str(filename or "")).stem
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip(".-")[:64]
    return text or fallback


def _save_website_asset(kind, uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        raise ValueError("image_required")

    asset_dir = _website_asset_dir(kind)
    asset_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_asset_stem(uploaded_file.filename, kind)}-{uuid.uuid4().hex[:8]}.jpg"
    target = asset_dir / filename

    try:
        uploaded_file.stream.seek(0)
        with Image.open(uploaded_file.stream) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail((1600, 1600))
            image.save(target, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("invalid_image") from error

    return filename


def _truthy_arg(name):
    return (request.args.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _company_databases():
    return list(_settings().company_databases)


def _find_company(database):
    requested = database or _settings().autocount_default_database
    for company in _company_databases():
        if company["value"] == requested:
            return company
    return None


def _compact_address(source):
    parts = []
    for key in ("address1", "address2", "address3", "address4", "address"):
        value = str(source.get(key) or "").strip()
        if value:
            parts.append(value)
    return "\n".join(parts)


def _project_draft_from_debtor(debtor):
    debtor_code = str(debtor.get("debtorCode") or "").strip()
    debtor_name = str(
        debtor.get("debtorName") or debtor.get("companyName") or debtor_code
    ).strip()
    address = _compact_address(debtor)
    first_address_line = address.splitlines()[0] if address else ""
    title_parts = [debtor_name, first_address_line]
    phone = str(debtor.get("phone") or debtor.get("phone2") or "").strip()

    return {
        "title": " - ".join(part for part in title_parts if part),
        "status": "Lead",
        "debtorCode": debtor_code,
        "debtorName": debtor_name,
        "contactPerson": debtor_name,
        "phone": phone,
        "siteAddress": address,
        "notes": f"Created from AutoCount debtor {debtor_code}" if debtor_code else "",
        "lines": [],
        "__mode": "create",
        "__sourceModule": "debtors",
        "__sourceKey": debtor_code,
    }


def _project_candidate_from_debtor(debtor, existing_projects):
    draft = _project_draft_from_debtor(debtor)
    existing = [
        {
            "projectCode": project.get("projectCode") or "",
            "title": project.get("title") or "",
            "status": project.get("status") or "",
        }
        for project in existing_projects
    ]

    return {
        "debtorCode": draft["debtorCode"],
        "debtorName": draft["debtorName"],
        "phone": draft["phone"],
        "area": debtor.get("area") or "",
        "agent": debtor.get("agent") or "",
        "currencyCode": debtor.get("currencyCode") or "",
        "displayTerm": debtor.get("displayTerm") or "",
        "siteAddress": draft["siteAddress"],
        "title": draft["title"],
        "existingProjectCount": len(existing),
        "existingProjects": existing,
        "draft": draft,
    }


def _is_cancelled(document):
    value = document.get("cancelled")
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _normalize_match_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _match_tokens(value):
    text = _normalize_match_text(value)
    return {
        token
        for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text)
        if len(token) > 1
    }


def _text_match_score(left, right, points):
    left_text = _normalize_match_text(left)
    right_text = _normalize_match_text(right)
    if not left_text or not right_text:
        return 0

    ratio = SequenceMatcher(None, left_text, right_text).ratio()
    left_tokens = _match_tokens(left_text)
    right_tokens = _match_tokens(right_text)
    overlap = 0
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    return round(points * max(ratio, overlap))


def _number_value(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _bank_recon_state(row):
    status = str(row.get("bankReconStatus") or "").strip()
    label = str(row.get("bankReconStatusLabel") or "").strip().lower()
    return "reconciled" if status == "1" or label == "reconciled" else "open"


def _bank_recon_label(state):
    return "Reconciled" if state == "reconciled" else "Open"


def _amount_match_score(document_amount, project):
    amount = _number_value(document_amount)
    if amount is None or amount == 0:
        return 0, ""

    project_amounts = [
        ("quoted total", _number_value(project.get("quotedTotal"))),
        ("outstanding", _number_value(project.get("outstandingAmount"))),
        ("collected", _number_value(project.get("collectedTotal"))),
    ]
    best_score = 0
    best_label = ""
    for label, project_amount in project_amounts:
        if project_amount is None:
            continue
        diff_ratio = abs(project_amount - amount) / max(abs(amount), 1)
        if diff_ratio <= 0.01:
            score = 15
        elif diff_ratio <= 0.05:
            score = 10
        elif diff_ratio <= 0.12:
            score = 5
        else:
            score = 0
        if score > best_score:
            best_score = score
            best_label = label
    return best_score, best_label


def _date_match_score(document_date, project):
    doc_date = _parse_date(document_date)
    if not doc_date:
        return 0

    best_days = None
    for key in ("expectedInstallDate", "completionDate", "createdAt", "updatedAt"):
        project_date = _parse_date(project.get(key))
        if not project_date:
            continue
        days = abs((project_date - doc_date).days)
        best_days = days if best_days is None else min(best_days, days)

    if best_days is None:
        return 0
    if best_days <= 30:
        return 5
    if best_days <= 90:
        return 3
    return 0


def _score_project_document_match(candidate, project):
    score = 0
    reasons = []

    if str(candidate.get("debtorCode") or "").strip().lower() == str(
        project.get("debtorCode") or ""
    ).strip().lower():
        score += 35
        reasons.append("same debtor")

    description_score = _text_match_score(
        candidate.get("description") or candidate.get("docNo"),
        " ".join(
            str(project.get(key) or "")
            for key in ("title", "notes", "quotationDocNo", "invoiceDocNo")
        ),
        25,
    )
    if description_score >= 8:
        score += description_score
        reasons.append("description/title")

    address_score = _text_match_score(
        candidate.get("debtorAddress"),
        project.get("siteAddress"),
        20,
    )
    if address_score >= 6:
        score += address_score
        reasons.append("address")

    amount_score, amount_label = _amount_match_score(candidate.get("amount"), project)
    if amount_score:
        score += amount_score
        reasons.append(f"amount/{amount_label}")

    date_score = _date_match_score(candidate.get("docDate"), project)
    if date_score:
        score += date_score
        reasons.append("date")

    return min(score, 100), reasons


def _project_draft_from_document(module, document):
    config = PROJECT_DOCUMENT_CANDIDATE_MODULES[module]
    doc_no = str(document.get("docNo") or "").strip()
    debtor_code = str(document.get("debtorCode") or "").strip()
    debtor_name = str(document.get("debtorName") or debtor_code).strip()
    description = str(document.get("description") or "").strip()
    title = " - ".join(part for part in (debtor_name, description or doc_no) if part)
    amount = (
        document.get(config["sourceAmountField"])
        or document.get("finalTotal")
        or document.get("netTotal")
        or document.get("total")
        or ""
    )

    draft = {
        "title": title,
        "status": config["status"],
        "debtorCode": debtor_code,
        "debtorName": debtor_name,
        "notes": f"Created from AutoCount {config['label']} {doc_no}" if doc_no else "",
        "lines": [],
        "__mode": "create",
        "__sourceModule": module,
        "__sourceKey": doc_no,
    }
    draft[config["docField"]] = doc_no
    draft[config["amountField"]] = amount

    if module == "invoices":
        draft["collectedTotal"] = document.get("paymentAmt") or ""
        draft["outstandingAmount"] = document.get("outstanding") or ""

    return draft


def _project_candidate_from_document(module, document, existing_projects, debtor_profile, all_projects):
    draft = _project_draft_from_document(module, document)
    config = PROJECT_DOCUMENT_CANDIDATE_MODULES[module]
    debtor_address = _compact_address(debtor_profile or {})
    candidate = {
        "module": module,
        "moduleLabel": config["label"],
        "docNo": draft["__sourceKey"],
        "docDate": document.get("docDate") or "",
        "debtorCode": draft["debtorCode"],
        "debtorName": draft["debtorName"],
        "debtorAddress": debtor_address,
        "description": document.get("description") or "",
        "currencyCode": document.get("currencyCode") or "",
        "amount": draft.get(config["amountField"]) or "",
        "outstanding": document.get("outstanding") or "",
        "status": document.get("status") or "",
        "draft": draft,
    }

    scored_projects = []
    same_debtor_keys = {
        str(project.get("projectCode") or "").strip().lower()
        for project in existing_projects
    }
    for project in all_projects:
        score, reasons = _score_project_document_match(candidate, project)
        project_code = str(project.get("projectCode") or "").strip()
        same_debtor = project_code.lower() in same_debtor_keys
        if score >= 25 and (same_debtor or score >= 55):
            scored_projects.append(
                {
                    "projectCode": project.get("projectCode") or "",
                    "title": project.get("title") or "",
                    "status": project.get("status") or "",
                    "matchScore": score,
                    "matchReasons": reasons,
                    "recommended": False,
                }
            )

    scored_projects.sort(key=lambda item: item["matchScore"], reverse=True)
    recommended = scored_projects[0] if scored_projects and scored_projects[0]["matchScore"] >= 45 else None
    if recommended:
        recommended["recommended"] = True

    candidate["existingProjectCount"] = len(existing_projects)
    candidate["existingProjects"] = scored_projects[:5]
    candidate["recommendedProject"] = recommended
    candidate["matchScore"] = recommended["matchScore"] if recommended else 0
    candidate["matchReasons"] = recommended["matchReasons"] if recommended else []
    return candidate


def _session_payload(token, session):
    company = _find_company(session["database"]) or {
        "value": session["database"],
        "label": session["database"],
    }
    return {
        "ok": True,
        "token": token,
        "user": session["username"],
        "username": session["username"],
        "displayName": session.get("display_name") or session["username"],
        "role": session.get("role") or "user",
        "database": company["value"],
        "company": company,
        "companies": _company_databases(),
    }


@api_bp.get("/health")
def health():
    settings = _settings()
    return jsonify(
        {
            "status": "ok",
            "autocount_sdk_configured": settings.autocount_sdk_configured,
            "autocount_bridge_configured": settings.autocount_bridge_configured,
            "sql_direct_reader_configured": _sql_reader().configured,
            "allowed_resources": sorted(settings.allowed_resources),
        }
    )


@api_bp.get("/api/companies")
def companies():
    return jsonify({"companies": _company_databases()})


@api_bp.post("/api/auth/login")
def auth_login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username") or ""
    password = payload.get("password")

    try:
        user = _user_data().authenticate(username, password)
    except ValueError as error:
        return jsonify({"error": str(error)}), 500

    if not user:
        return jsonify({"error": "Invalid username or password."}), 401

    company = _find_company(payload.get("database") or user.get("defaultCompany"))
    if not company:
        return jsonify({"error": "Company database is not allowed."}), 400

    token = _sessions().create(
        database=company["value"],
        username=user["username"],
        display_name=user.get("displayName") or user["username"],
        role=user.get("role") or "user",
        server=_settings().autocount_sql_server,
    )

    if user.get("defaultCompany") != company["value"]:
        _user_data().set_default_company(user["username"], company["value"])

    session = _sessions().get(token)
    return jsonify(_session_payload(token, session))


@api_bp.get("/api/auth/me")
def auth_me():
    token = _bearer_token()
    session, auth_error = _require_session()
    if auth_error:
        return auth_error
    return jsonify(_session_payload(token, session))


@api_bp.put("/api/session/company")
def switch_company():
    token = _bearer_token()
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    company = _find_company(payload.get("database"))
    if not company:
        return jsonify({"error": "Company database is not allowed."}), 400

    session = _sessions().update_database(token, company["value"])
    _user_data().set_default_company(session["username"], company["value"])
    return jsonify(_session_payload(token, session))


@api_bp.get("/api/users")
def list_users():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    return jsonify({"data": _user_data().list_users()})


@api_bp.post("/api/users")
def save_user():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    default_company = payload.get("defaultCompany")
    if default_company is None:
        default_company = payload.get("default_company")

    if default_company:
        company = _find_company(default_company)
        if not company:
            return jsonify({"error": "Company database is not allowed."}), 400
        default_company = company["value"]

    display_name = payload.get("displayName")
    if display_name is None:
        display_name = payload.get("display_name")

    try:
        user = _user_data().upsert_user(
            payload.get("username"),
            payload.get("password"),
            display_name=str(display_name or "").strip() or None,
            role=payload.get("role") or "user",
            default_company=default_company or "",
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(user), 201


@api_bp.delete("/api/users/<path:username>")
def delete_user(username):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    try:
        deleted = _user_data().delete_user(username)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not deleted:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"deleted": deleted})


@api_bp.get("/api/rdp-allow-list")
def get_rdp_allow_list():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(rdp_allow_list.status_payload())


@api_bp.put("/api/rdp-allow-list")
def update_rdp_allow_list():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    external_ips = payload.get("externalIps")
    if not isinstance(external_ips, list):
        return jsonify({"error": "externalIps must be a list."}), 400

    try:
        config = rdp_allow_list.write_config(external_ips=external_ips)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    apply_result = rdp_allow_list.trigger_apply()
    return jsonify(
        {
            **rdp_allow_list.status_payload(),
            "config": config,
            "apply": apply_result,
        }
    )


@api_bp.post("/api/rdp-allow-list/ip")
def add_rdp_allow_ip():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        rdp_allow_list.add_external_ip(payload.get("ip"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    apply_result = rdp_allow_list.trigger_apply()
    return jsonify({**rdp_allow_list.status_payload(), "apply": apply_result})


@api_bp.delete("/api/rdp-allow-list/ip/<ip>")
def remove_rdp_allow_ip(ip):
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    try:
        rdp_allow_list.remove_external_ip(ip)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    apply_result = rdp_allow_list.trigger_apply()
    return jsonify({**rdp_allow_list.status_payload(), "apply": apply_result})


@api_bp.post("/api/rdp-allow-list/apply")
def apply_rdp_allow_list():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    apply_result = rdp_allow_list.trigger_apply()
    return jsonify({**rdp_allow_list.status_payload(), "apply": apply_result})


@api_bp.get("/api/website-content")
def get_website_content():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_sengchong_content().get_content())


@api_bp.get("/api/website-content/assets/<kind>")
def list_website_assets(kind):
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    try:
        asset_dir = _website_asset_dir(kind)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    assets = []
    if asset_dir.exists():
        for path in sorted(asset_dir.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or path.suffix.lower() not in WEBSITE_ASSET_EXTENSIONS:
                continue
            stat = path.stat()
            assets.append(
                {
                    "kind": kind,
                    "filename": path.name,
                    "url": _website_asset_url(kind, path.name),
                    "size": stat.st_size,
                    "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                }
            )
    return jsonify({"data": assets, "count": len(assets)})


@api_bp.post("/api/website-content/assets/<kind>")
def upload_website_asset(kind):
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    uploaded_file = request.files.get("image") or request.files.get("file")
    try:
        filename = _save_website_asset(kind, uploaded_file)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return (
        jsonify(
            {
                "kind": kind,
                "filename": filename,
                "url": _website_asset_url(kind, filename),
            }
        ),
        201,
    )


@api_bp.patch("/api/website-content/footer")
def update_website_footer():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    _sengchong_content().update_footer(
        request.get_json(silent=True) or {},
        company=session["database"],
        username=session["username"],
    )
    return jsonify(_sengchong_content().get_content())


@api_bp.patch("/api/website-content/services/<int:service_no>")
def update_website_service(service_no):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    service_name = payload.get("serviceName")
    if service_name is None:
        service_name = payload.get("service_name")
    _sengchong_content().update_service(
        service_no,
        service_name=service_name,
        bg=payload.get("bg") if "bg" in payload else None,
        company=session["database"],
        username=session["username"],
    )
    return jsonify(_sengchong_content().get_content())


@api_bp.patch("/api/website-content/contacts/<int:contact_no>")
def update_website_contact(contact_no):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    _sengchong_content().update_contact(
        contact_no,
        name=payload.get("name") if "name" in payload else None,
        number=payload.get("number") if "number" in payload else None,
        bg=payload.get("bg") if "bg" in payload else None,
        company=session["database"],
        username=session["username"],
    )
    return jsonify(_sengchong_content().get_content())


@api_bp.get("/api/website-gallery")
def website_gallery():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_project_photos().website_gallery(session["database"]))


@api_bp.post("/api/website-gallery/import-legacy-products")
def import_legacy_website_gallery():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    source_dir = _settings().sengchong_static_dir / "images" / "products"
    try:
        result = _project_photos().import_legacy_product_images(
            session["database"],
            session["username"],
            source_dir,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({**result, "gallery": _project_photos().website_gallery(session["database"])})


@api_bp.get("/api/website-audit-log")
def website_audit_log():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_project_photos().website_audit_log(session["database"], request.args.get("limit")))


@api_bp.get("/api/projects/meta")
def projects_meta():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_project_data().meta())


@api_bp.get("/api/projects/by-document")
def projects_by_document():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    projects = _project_data().find_by_document(
        session["database"],
        request.args.get("module") or "",
        request.args.get("key") or "",
    )
    return jsonify({"data": projects})


@api_bp.get("/api/projects/candidates/from-debtors")
def project_candidates_from_debtors():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    try:
        limit = int(request.args.get("limit") or 200)
    except ValueError:
        return jsonify({"error": "limit must be a number."}), 400
    limit = min(max(limit, 1), 500)
    include_existing = _truthy_arg("includeExisting") or _truthy_arg("include_existing")

    ok, result = _sql_reader().list_debtor_project_candidates(session, limit=limit)
    if not ok:
        ok, result = _sql_reader().list_resource("debtors", session)
    if not ok:
        ok, result = _sdk().list_resource("debtors", session, refresh=_refresh_requested())
    if not ok:
        return jsonify(result), 502

    debtors = result.get("data") if isinstance(result, dict) else result
    if not isinstance(debtors, list):
        debtors = []

    existing_by_debtor = {}
    for project in _project_data().list_projects(session["database"]):
        debtor_code = str(project.get("debtorCode") or "").strip().lower()
        if debtor_code:
            existing_by_debtor.setdefault(debtor_code, []).append(project)

    candidates = []
    seen = set()
    for debtor in debtors:
        debtor_code = str((debtor or {}).get("debtorCode") or "").strip()
        debtor_key = debtor_code.lower()
        if not debtor_key or debtor_key in seen:
            continue
        seen.add(debtor_key)
        existing_projects = existing_by_debtor.get(debtor_key, [])
        if existing_projects and not include_existing:
            continue
        candidates.append(_project_candidate_from_debtor(debtor, existing_projects))

    return jsonify(
        {
            "data": candidates,
            "sourceCount": len(debtors),
            "candidateCount": len(candidates),
            "existingDebtorProjectCount": len(existing_by_debtor),
        }
    )


@api_bp.get("/api/projects/candidates/from-documents")
def project_candidates_from_documents():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    requested_modules = [
        item.strip()
        for item in (request.args.get("modules") or "quotations,invoices").split(",")
        if item.strip()
    ]
    modules = [module for module in requested_modules if module in PROJECT_DOCUMENT_CANDIDATE_MODULES]
    if not modules:
        return jsonify({"error": "No supported document modules requested."}), 400

    try:
        limit = int(request.args.get("limit") or 200)
    except ValueError:
        return jsonify({"error": "limit must be a number."}), 400
    limit = min(max(limit, 1), 500)
    include_linked = _truthy_arg("includeLinked") or _truthy_arg("include_linked")
    include_cancelled = _truthy_arg("includeCancelled") or _truthy_arg("include_cancelled")

    projects = _project_data().list_projects(session["database"])
    linked_keys = _project_data().linked_document_keys(session["database"], modules)
    existing_by_debtor = {}
    for project in projects:
        debtor_code = str(project.get("debtorCode") or "").strip().lower()
        if debtor_code:
            existing_by_debtor.setdefault(debtor_code, []).append(project)

    candidate_sources = []
    debtor_codes = set()
    source_counts = {}
    for module in modules:
        ok, result = _sql_reader().list_resource(module, session)
        if not ok:
            ok, result = _sdk().list_resource(module, session, refresh=_refresh_requested())
        if not ok:
            return jsonify(result), 502

        documents = result.get("data") if isinstance(result, dict) else result
        if not isinstance(documents, list):
            documents = []
        source_counts[module] = len(documents)

        for document in documents:
            if len(candidate_sources) >= limit:
                break
            doc_no = str((document or {}).get("docNo") or "").strip()
            if not doc_no:
                continue
            if _is_cancelled(document or {}) and not include_cancelled:
                continue
            if (module, doc_no.lower()) in linked_keys and not include_linked:
                continue
            debtor_code = str((document or {}).get("debtorCode") or "").strip().lower()
            if debtor_code:
                debtor_codes.add(debtor_code)
            candidate_sources.append((module, document or {}, debtor_code))

    debtor_profiles = {}
    ok, debtor_result = _sql_reader().list_debtors_by_codes(session, debtor_codes)
    if ok:
        for debtor in debtor_result.get("data") or []:
            debtor_code = str((debtor or {}).get("debtorCode") or "").strip().lower()
            if debtor_code:
                debtor_profiles[debtor_code] = debtor or {}

    candidates = [
        _project_candidate_from_document(
            module,
            document,
            existing_by_debtor.get(debtor_code, []),
            debtor_profiles.get(debtor_code, {}),
            projects,
        )
        for module, document, debtor_code in candidate_sources
    ]

    return jsonify(
        {
            "data": candidates,
            "sourceCounts": source_counts,
            "candidateCount": len(candidates),
            "linkedDocumentCount": len(linked_keys),
        }
    )


@api_bp.get("/api/projects/<path:project_key>/photos")
def list_project_photos(project_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    photos = _project_photos().list_photos(session["database"], project_key)
    if photos is None:
        return jsonify({"error": "project_not_found"}), 404
    return jsonify({"data": photos})


@api_bp.post("/api/projects/<path:project_key>/photos")
def upload_project_photos(project_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    files = request.files.getlist("images") or request.files.getlist("photos")
    payload = {
        "serviceCategory": request.form.get("serviceCategory"),
        "caption": request.form.get("caption"),
        "altText": request.form.get("altText"),
        "isPublic": request.form.get("isPublic"),
        "websiteVisible": request.form.get("websiteVisible"),
        "sortOrder": request.form.get("sortOrder"),
    }
    try:
        photos = _project_photos().add_photos(
            session["database"],
            project_key,
            session["username"],
            files,
            payload,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if photos is None:
        return jsonify({"error": "project_not_found"}), 404
    return jsonify({"data": photos}), 201


@api_bp.get("/api/projects/draft-from-debtor/<path:debtor_key>")
def project_draft_from_debtor(debtor_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    ok, result = _sql_reader().get_resource_detail("debtors", debtor_key, session)
    if not ok:
        ok, result = _sdk().get_resource_detail(
            "debtors",
            debtor_key,
            session,
            refresh=_refresh_requested(),
        )
    if not ok:
        return jsonify(result), 502

    debtor = result.get("data") if isinstance(result, dict) else result
    if not debtor:
        return jsonify({"error": f"Debtor not found: {debtor_key}"}), 404
    return jsonify(_project_draft_from_debtor(debtor))


@api_bp.get("/api/projects")
def list_projects():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify({"data": _project_data().list_projects(session["database"])})


@api_bp.post("/api/projects")
def create_project():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        project = _project_data().create_project(session["database"], session["username"], payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(project), 201


@api_bp.get("/api/projects/<path:project_key>")
def get_project(project_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    project = _project_data().get_project(session["database"], project_key)
    if not project:
        return jsonify({"error": "project_not_found"}), 404
    project["photos"] = _project_photos().list_photos(session["database"], project_key) or []
    return jsonify(project)


@api_bp.patch("/api/projects/<path:project_key>")
@api_bp.put("/api/projects/<path:project_key>")
def update_project(project_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        project = _project_data().update_project(
            session["database"],
            project_key,
            session["username"],
            payload,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not project:
        return jsonify({"error": "project_not_found"}), 404
    return jsonify(project)


@api_bp.patch("/api/project-photos/<photo_id>")
def update_project_photo(photo_id):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    try:
        photo = _project_photos().update_photo(
            session["database"],
            photo_id,
            session["username"],
            payload,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not photo:
        return jsonify({"error": "photo_not_found"}), 404
    return jsonify(photo)


@api_bp.delete("/api/project-photos/<photo_id>")
def delete_project_photo(photo_id):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    photo = _project_photos().delete_photo(session["database"], photo_id)
    if not photo:
        return jsonify({"error": "photo_not_found"}), 404
    return jsonify({"deleted": photo})


@api_bp.get("/api/project-photos/<photo_id>/file")
def project_photo_file(photo_id):
    session, auth_error = _require_request_session()
    if auth_error:
        return auth_error

    path = _project_photos().file_path(
        photo_id,
        company=session["database"],
        thumbnail=(request.args.get("size") == "thumbnail"),
    )
    if not path:
        return jsonify({"error": "photo_not_found"}), 404
    return send_file(path, mimetype="image/jpeg", conditional=True, max_age=3600)


@api_bp.get("/public-api/gallery")
def public_gallery():
    company = request.args.get("company") or ""
    return jsonify({"data": _project_photos().public_gallery(company)})


@api_bp.get("/public-api/website")
def public_website_payload():
    company = request.args.get("company") or ""
    content = _sengchong_content().get_content()
    services = [
        {
            "no": service.get("no"),
            "serviceName": service.get("service_name") or "",
            "imageUrl": f"/static/images/service/{service.get('bg') or ''}",
        }
        for service in content.get("services", [])
    ]
    contacts = [
        {
            "no": contact.get("no"),
            "name": contact.get("name") or "",
            "number": contact.get("number") or "",
            "imageUrl": f"/static/images/contact/{contact.get('bg') or ''}",
        }
        for contact in content.get("contacts", [])
    ]
    gallery = _project_photos().public_gallery(company)
    return jsonify(
        {
            "services": services,
            "contacts": contacts,
            "footer": content.get("footer") or {},
            "gallery": gallery,
            "galleryCount": len(gallery),
        }
    )


@api_bp.get("/public-api/project-photos/<photo_id>/file")
def public_project_photo_file(photo_id):
    path = _project_photos().file_path(
        photo_id,
        public_only=True,
        thumbnail=(request.args.get("size") == "thumbnail"),
    )
    if not path:
        return jsonify({"error": "photo_not_found"}), 404
    return send_file(path, mimetype="image/jpeg", conditional=True, max_age=86400)


@api_bp.post("/api/autocount/login")
def autocount_login():
    return auth_login()


@api_bp.get("/api/autocount/<resource>/pdf")
def autocount_pdf_by_query(resource):
    return _send_autocount_pdf(resource, request.args.get("key") or "")


@api_bp.get("/api/autocount/<resource>/<path:key>/pdf")
def autocount_pdf(resource, key):
    return _send_autocount_pdf(resource, key)


@api_bp.post("/api/autocount/invoices/payment-request/pdf")
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


@api_bp.post("/api/autocount/bank-transactions/reconcile-preview")
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


@api_bp.post("/api/autocount/bank-transactions/reconcile")
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


@api_bp.route(
    "/api/autocount/<resource>",
    defaults={"subpath": ""},
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@api_bp.route(
    "/api/autocount/<resource>/<path:subpath>",
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
