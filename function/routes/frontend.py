import os

from flask import Blueprint, current_app, jsonify, send_from_directory

from .sengchong import render_home as render_sengchong_home
from .sengchong import should_render_public_home


frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.get("/")
@frontend_bp.get("/<path:front_path>")
def frontend(front_path=""):
    if front_path.startswith("api/"):
        return jsonify({"error": "not_found"}), 404

    if should_render_public_home(front_path):
        return render_sengchong_home()

    dist_dir = current_app.config["SETTINGS"].frontend_dist_dir
    requested_path = dist_dir / front_path
    if front_path and os.path.isfile(requested_path):
        return send_from_directory(dist_dir, front_path)

    index_path = dist_dir / "index.html"
    if index_path.exists():
        return send_from_directory(dist_dir, "index.html")

    return (
        jsonify(
            {
                "error": "frontend_not_built",
                "detail": "Run `npm install` and `npm run build` inside frontend/.",
            }
        ),
        503,
    )
