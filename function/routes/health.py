"""
Liveness endpoint and nothing else.
"""

from flask import Blueprint, jsonify


from .common import _settings, _sql_reader

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
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
