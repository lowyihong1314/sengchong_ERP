"""
The project/job layer and its photos, including the scoring that suggests
which AutoCount document belongs to which project.
"""
import re
from datetime import datetime
from difflib import SequenceMatcher

from flask import Blueprint, jsonify, request, send_file

from ..services import rdp_allow_list


api_bp = Blueprint("api", __name__)
from .common import (
    _project_data,
    _project_photos,
    _refresh_requested,
    _require_request_session,
    _require_session,
    _sdk,
    _sql_reader,
    _truthy_arg,
)

projects_bp = Blueprint("projects", __name__, url_prefix="/api")


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

@projects_bp.get("/projects/meta")
def projects_meta():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_project_data().meta())

@projects_bp.get("/projects/by-document")
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

@projects_bp.get("/projects/candidates/from-debtors")
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

@projects_bp.get("/projects/candidates/from-documents")
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

@projects_bp.get("/projects/<path:project_key>/photos")
def list_project_photos(project_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    photos = _project_photos().list_photos(session["database"], project_key)
    if photos is None:
        return jsonify({"error": "project_not_found"}), 404
    return jsonify({"data": photos})

@projects_bp.post("/projects/<path:project_key>/photos")
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

@projects_bp.get("/projects/draft-from-debtor/<path:debtor_key>")
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

@projects_bp.get("/projects")
def list_projects():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify({"data": _project_data().list_projects(session["database"])})

@projects_bp.post("/projects")
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

@projects_bp.get("/projects/<path:project_key>")
def get_project(project_key):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    project = _project_data().get_project(session["database"], project_key)
    if not project:
        return jsonify({"error": "project_not_found"}), 404
    project["photos"] = _project_photos().list_photos(session["database"], project_key) or []
    return jsonify(project)

@projects_bp.patch("/projects/<path:project_key>")
@projects_bp.put("/projects/<path:project_key>")
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

@projects_bp.patch("/project-photos/<photo_id>")
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

@projects_bp.delete("/project-photos/<photo_id>")
def delete_project_photo(photo_id):
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    photo = _project_photos().delete_photo(session["database"], photo_id)
    if not photo:
        return jsonify({"error": "photo_not_found"}), 404
    return jsonify({"deleted": photo})

@projects_bp.get("/project-photos/<photo_id>/file")
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
