# models/__init__.py
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

# Import every model module so that `db.metadata` is fully populated before
# Alembic autogenerates a migration. Keep this list in sync with the files in
# this package; each one mirrors the same-named module under function/.
from models import employee_data  # noqa: E402,F401
from models import project_data  # noqa: E402,F401
from models import project_photos  # noqa: E402,F401
from models import sengchong_content  # noqa: E402,F401
from models import sessions  # noqa: E402,F401
from models import user_data  # noqa: E402,F401
