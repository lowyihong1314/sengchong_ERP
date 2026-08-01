"""
Read-only endpoints for sengchong.com. These must never expose customer,
accounting, cost or document data -- only what the public page renders.
"""

from flask import Blueprint, jsonify, request, send_file


from .common import _project_photos, _sengchong_content

public_bp = Blueprint("public", __name__, url_prefix="/public-api")


@public_bp.get("/gallery")
def public_gallery():
    company = request.args.get("company") or ""
    return jsonify({"data": _project_photos().public_gallery(company)})

@public_bp.get("/website")
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

@public_bp.get("/project-photos/<photo_id>/file")
def public_project_photo_file(photo_id):
    path = _project_photos().file_path(
        photo_id,
        public_only=True,
        thumbnail=(request.args.get("size") == "thumbnail"),
    )
    if not path:
        return jsonify({"error": "photo_not_found"}), 404
    return send_file(path, mimetype="image/jpeg", conditional=True, max_age=86400)
