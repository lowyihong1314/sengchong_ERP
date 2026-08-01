"""
ERP user accounts. Admin only; these are not AutoCount logins.
"""

from flask import Blueprint, jsonify, request

from .common import _find_company, _require_admin_session, _sessions, _user_data

users_bp = Blueprint("users", __name__, url_prefix="/api")


@users_bp.get("/users")
def list_users():
    _, auth_error = _require_admin_session()
    if auth_error:
        return auth_error

    return jsonify({"data": _user_data().list_users()})

@users_bp.post("/users")
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

@users_bp.delete("/users/<path:username>")
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

    # A deleted account is already refused at lookup time, but clear its
    # tokens rather than leaving dead rows in erp_sessions.
    signed_out = _sessions().delete_for_user(deleted["username"])
    return jsonify({"deleted": deleted, "signedOutSessions": signed_out})
