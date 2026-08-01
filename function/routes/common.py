"""
Shared plumbing for the API blueprints: extension accessors and the
session guards every protected endpoint calls.
"""

from flask import Blueprint, current_app, jsonify, request


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
