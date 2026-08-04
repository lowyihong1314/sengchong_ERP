"""
The document inbox. Admin only, every endpoint.

Upload returns as soon as the files are on disk. Reading them happens in a
detached worker, so a phone uploading fifty photographs is not holding a
request open while each one is sent to a model. Poll the list for status.
"""
from flask import Blueprint, jsonify, request, send_file

from .common import _documents, _require_admin_session

documents_bp = Blueprint("documents", __name__, url_prefix="/api")


@documents_bp.get("/documents/meta")
def documents_meta():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    company = request.args.get("company") or session["database"]
    return jsonify(_documents().counts(company))


@documents_bp.get("/documents")
def list_documents():
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    company = "" if request.args.get("company") == "all" else (
        request.args.get("company") or session["database"]
    )
    return jsonify({"data": _documents().list_documents(
        company,
        doc_class=(request.args.get("class") or "").strip(),
        status=(request.args.get("status") or "").strip(),
        query=(request.args.get("q") or "").strip(),
        limit=request.args.get("limit") or 200,
    )})


@documents_bp.post("/documents")
def upload_documents():
    """
    Take the files and return. Nothing is read inside this request.

    Every file is stored, including the ones the reader cannot handle -- those
    land as `skipped` and are never sent anywhere. A file already on record is
    reported as a duplicate rather than failing the batch, because one repeat
    in fifty is an accident, not an error.
    """
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    files = request.files.getlist("files") or request.files.getlist("file")
    if not files:
        return jsonify({"error": "no_files"}), 400

    company = (request.form.get("company") or session["database"]).strip().upper()
    store = _documents()

    stored, duplicates, rejected = [], [], []
    for uploaded in files:
        if not getattr(uploaded, "filename", ""):
            continue
        try:
            payload, is_duplicate = store.store_upload(company, session["username"], uploaded)
        except ValueError as error:
            rejected.append({"filename": uploaded.filename, "error": str(error)})
            continue
        (duplicates if is_duplicate else stored).append(payload)

    queued = sum(1 for row in stored if row["status"] == "pending")
    if queued:
        store.spawn_worker()

    return jsonify({
        "stored": stored,
        "duplicates": duplicates,
        "rejected": rejected,
        "queued": queued,
        "skipped": sum(1 for row in stored if row["status"] == "skipped"),
    }), 201


@documents_bp.get("/documents/<document_id>")
def get_document(document_id):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    document = _documents().get_document(document_id)
    if not document:
        return jsonify({"error": "document_not_found"}), 404
    return jsonify(document)


@documents_bp.get("/documents/<document_id>/file")
def download_document(document_id):
    """
    The original file, always as a download.

    Never inline: an uploaded .html or .svg served inline would run its own
    script on this origin, with the viewer's session. The only thing shown in
    the page is the preview below, which this server generated itself.
    """
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    store = _documents()
    document = store.get_document(document_id)
    if not document:
        return jsonify({"error": "document_not_found"}), 404
    path = store.file_path(document)
    if not path.exists():
        return jsonify({"error": "file_missing"}), 404
    return send_file(
        path,
        as_attachment=True,
        download_name=document["filename"] or path.name,
        mimetype="application/octet-stream",
    )


@documents_bp.get("/documents/<document_id>/preview")
def preview_document(document_id):
    """The generated JPEG preview. Safe to show inline; this server made it."""
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    store = _documents()
    document = store.get_document(document_id)
    if not document:
        return jsonify({"error": "document_not_found"}), 404
    if not document["previewPath"]:
        return jsonify({"error": "no_preview"}), 404
    path = store.file_path(document, preview=True)
    if not path.exists():
        return jsonify({"error": "file_missing"}), 404
    return send_file(path, mimetype="image/jpeg")


@documents_bp.post("/documents/<document_id>/analyse")
def reanalyse_document(document_id):
    """Put a document back on the queue -- after a failure, or a prompt change."""
    session, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    store = _documents()
    try:
        document = store.requeue(document_id, session["username"])
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if not document:
        return jsonify({"error": "document_not_found"}), 404
    store.spawn_worker()
    return jsonify(document)


@documents_bp.delete("/documents/<document_id>")
def delete_document(document_id):
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    deleted = _documents().delete_document(document_id)
    if not deleted:
        return jsonify({"error": "document_not_found"}), 404
    return jsonify({"deleted": deleted})
