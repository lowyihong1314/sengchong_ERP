from flask import Flask

from .config import Settings
from .routes.api import api_bp
from .routes.frontend import frontend_bp
from .routes.sengchong import sengchong_bp
from .sessions import SessionStore
from .services.autocount_sdk import AutoCountSdk
from .services.erp_db import ErpDatabase
from .services.project_data import ProjectDataStore
from .services.project_photos import ProjectPhotoStore
from .services.sengchong_content import SengchongContentStore
from .services.sql_reader import SqlReadService
from .services.user_data import UserDataStore


def create_app():
    settings = Settings.from_env()

    app = Flask(
        __name__,
        static_folder=str(settings.sengchong_static_dir),
        static_url_path="/static",
        template_folder=str(settings.sengchong_template_dir),
    )
    app.secret_key = settings.flask_secret_key
    app.config["SETTINGS"] = settings
    erp_db = ErpDatabase(settings.erp_db_path)
    erp_db.initialize()
    app.extensions["erp_db"] = erp_db
    app.extensions["sessions"] = SessionStore(
        settings.session_ttl_seconds,
        erp_db,
    )
    app.extensions["autocount_sdk"] = AutoCountSdk(settings)
    app.extensions["sql_reader"] = SqlReadService(settings)
    app.extensions["user_data"] = UserDataStore(erp_db)
    app.extensions["project_data"] = ProjectDataStore(erp_db)
    app.extensions["project_photos"] = ProjectPhotoStore(erp_db, settings.base_dir)
    app.extensions["sengchong_content"] = SengchongContentStore(erp_db)

    app.register_blueprint(api_bp)
    app.register_blueprint(sengchong_bp)
    app.register_blueprint(frontend_bp)

    return app
