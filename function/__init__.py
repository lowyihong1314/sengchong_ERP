from flask import Flask

from models import db

from .config import Settings
from .routes.api import api_bp
from .routes.frontend import frontend_bp
from .routes.sengchong import sengchong_bp
from .sessions import SessionStore
from .services.autocount_sdk import AutoCountSdk
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

    # ORM layer. Schema changes go through Alembic (see migrations/), never
    # through create_all() -- a fresh checkout runs `alembic upgrade head`.
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    app.extensions["sessions"] = SessionStore(settings.session_ttl_seconds)
    app.extensions["autocount_sdk"] = AutoCountSdk(settings)
    app.extensions["sql_reader"] = SqlReadService(settings)
    app.extensions["user_data"] = UserDataStore()
    app.extensions["project_data"] = ProjectDataStore()
    app.extensions["project_photos"] = ProjectPhotoStore(settings.base_dir)
    app.extensions["sengchong_content"] = SengchongContentStore()

    # Seeding needs db.session, so it runs in an app context rather than in
    # the store's constructor.
    with app.app_context():
        app.extensions["sengchong_content"].ensure_defaults()

    app.register_blueprint(api_bp)
    app.register_blueprint(sengchong_bp)
    app.register_blueprint(frontend_bp)

    return app
