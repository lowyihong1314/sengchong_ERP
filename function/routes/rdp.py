"""
The RDP allow-list. Admin only, and it shells out to the firewall.
"""

from flask import Blueprint, jsonify, request

from ..services import rdp_allow_list


from .common import _require_session

rdp_bp = Blueprint("rdp", __name__, url_prefix="/api")


@rdp_bp.get("/rdp-allow-list")
def get_rdp_allow_list():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    return jsonify(rdp_allow_list.status_payload())

@rdp_bp.put("/rdp-allow-list")
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

@rdp_bp.post("/rdp-allow-list/ip")
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

@rdp_bp.delete("/rdp-allow-list/ip/<ip>")
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

@rdp_bp.post("/rdp-allow-list/apply")
def apply_rdp_allow_list():
    _, auth_error = _require_session()
    if auth_error:
        return auth_error

    apply_result = rdp_allow_list.trigger_apply()
    return jsonify({**rdp_allow_list.status_payload(), "apply": apply_result})
