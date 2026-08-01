"""
Managing what sengchong.com shows: content, gallery publishing, audit log.
The public site only renders; every edit happens here.
"""
import re
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request
from PIL import Image, ImageOps, UnidentifiedImageError

from ..services import rdp_allow_list


api_bp = Blueprint("api", __name__)
from .common import (
    _project_photos,
    _require_session,
    _sengchong_content,
    _settings,
)

website_bp = Blueprint("website", __name__, url_prefix="/api")


WEBSITE_ASSET_KINDS = {"service", "contact"}

WEBSITE_ASSET_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

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

@website_bp.get("/website-content")
def get_website_content():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_sengchong_content().get_content())

@website_bp.get("/website-content/assets/<kind>")
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

@website_bp.post("/website-content/assets/<kind>")
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

@website_bp.patch("/website-content/footer")
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

@website_bp.patch("/website-content/services/<int:service_no>")
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

@website_bp.patch("/website-content/contacts/<int:contact_no>")
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

@website_bp.get("/website-gallery")
def website_gallery():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_project_photos().website_gallery(session["database"]))

@website_bp.post("/website-gallery/import-legacy-products")
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

@website_bp.get("/website-audit-log")
def website_audit_log():
    session, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(_project_photos().website_audit_log(session["database"], request.args.get("limit")))
