"""
Login, the current session, and switching the active AutoCount company.
"""

from flask import Blueprint, jsonify, request


from .common import (
    _bearer_token,
    _company_databases,
    _find_company,
    _require_session,
    _sessions,
    _settings,
    _user_data,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


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


@auth_bp.get("/companies")
def companies():
    return jsonify({"companies": _company_databases()})


@auth_bp.post("/auth/login")
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


@auth_bp.get("/auth/me")
def auth_me():
    token = _bearer_token()
    session, auth_error = _require_session()
    if auth_error:
        return auth_error
    return jsonify(_session_payload(token, session))


@auth_bp.put("/session/company")
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
