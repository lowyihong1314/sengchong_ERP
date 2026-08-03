from flask import Flask

from models import db

from .config import Settings
from .routes.auth import auth_bp
from .routes.autocount import autocount_bp
from .routes.employees import employees_bp
from .routes.health import health_bp
from .routes.projects import projects_bp
from .routes.payroll import payroll_bp
from .routes.public import public_bp
from .routes.salary import salary_bp
from .routes.work_entries import work_entries_bp
from .routes.rdp import rdp_bp
from .routes.users import users_bp
from .routes.website import website_bp
from .routes.frontend import frontend_bp
from .routes.sengchong import sengchong_bp
from .sessions import SessionStore
from .services.autocount_sdk import AutoCountSdk
from .services.employee_data import EmployeeDataStore
from .services.project_data import ProjectDataStore
from .services.salary_data import SalaryDataStore
from .services.payroll import PayrollStore
from .services.work_entry import WorkEntryStore
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
    app.extensions["employee_data"] = EmployeeDataStore()
    app.extensions["project_data"] = ProjectDataStore()
    app.extensions["salary_data"] = SalaryDataStore()
    app.extensions["work_entries"] = WorkEntryStore()
    app.extensions["payroll"] = PayrollStore()
    app.extensions["project_photos"] = ProjectPhotoStore(settings.base_dir)
    app.extensions["sengchong_content"] = SengchongContentStore()

    # Seeding needs db.session, so it runs in an app context rather than in
    # the store's constructor.
    with app.app_context():
        app.extensions["sengchong_content"].ensure_defaults()

    for blueprint in (
        health_bp,
        auth_bp,
        users_bp,
        rdp_bp,
        website_bp,
        projects_bp,
        employees_bp,
        salary_bp,
        work_entries_bp,
        payroll_bp,
        public_bp,
        autocount_bp,
    ):
        app.register_blueprint(blueprint)
    app.register_blueprint(sengchong_bp)
    app.register_blueprint(frontend_bp)

    return app
