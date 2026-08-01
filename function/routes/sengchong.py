from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)


sengchong_bp = Blueprint("sengchong", __name__)
SESSION_USER_KEY = "sengchong_user"
SESSION_DISPLAY_KEY = "sengchong_display_name"
SESSION_COMPANY_KEY = "sengchong_company"
PUBLIC_HOSTS = {"sengchong.com", "www.sengchong.com"}


def is_public_sengchong_host():
    host = (request.host or "").split(":", 1)[0].lower()
    return host in PUBLIC_HOSTS


def should_render_public_home(front_path):
    return is_public_sengchong_host() and front_path in {"", "index.html"}


def _project_photos():
    return current_app.extensions["project_photos"]


def _wants_json():
    if request.path.startswith(("/update_", "/upload_", "/delete_", "/get_")):
        return True
    return request.accept_mimetypes.best == "application/json"


def _erp_url():
    return "https://erp.sengchong.com"


def _website_backend_removed():
    if _wants_json():
        return (
            jsonify(
                {
                    "error": "website_backend_removed",
                    "detail": "Manage Sengchong website content from ERP.",
                }
            ),
            410,
        )
    return redirect(_erp_url())


def render_home():
    return render_template("index.html")


@sengchong_bp.get("/products")
def products():
    return render_template("products.html")


@sengchong_bp.get("/get_api_url")
def get_api_url():
    return jsonify(
        {
            "url": "/public-api/website",
            "galleryUrl": "/public-api/gallery",
        }
    )


@sengchong_bp.route("/register", methods=["GET", "POST"])
def register():
    return redirect(_erp_url())


@sengchong_bp.route("/login", methods=["GET", "POST"])
def login():
    return redirect(_erp_url())


@sengchong_bp.get("/backend")
def backend():
    return redirect(_erp_url())


@sengchong_bp.get("/logout")
def logout():
    session.pop(SESSION_USER_KEY, None)
    session.pop(SESSION_DISPLAY_KEY, None)
    session.pop(SESSION_COMPANY_KEY, None)
    return redirect(_erp_url())


@sengchong_bp.post("/update_image/index")
def update_image():
    return _website_backend_removed()


@sengchong_bp.post("/update_footer")
def update_footer():
    return _website_backend_removed()


@sengchong_bp.get("/get_all_products_img")
def get_products_img():
    gallery = _project_photos().public_gallery("")
    return jsonify({"login": False, "images": [], "gallery": gallery})


@sengchong_bp.post("/upload_product_image")
def upload_product_image():
    return _website_backend_removed()


@sengchong_bp.post("/delete_product_image")
def delete_product_image():
    return _website_backend_removed()
