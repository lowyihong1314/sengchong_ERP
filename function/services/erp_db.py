import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS erp_users (
        username TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL,
        default_company TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_sessions (
        token TEXT PRIMARY KEY,
        database_name TEXT NOT NULL,
        username TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL,
        server TEXT NOT NULL DEFAULT '',
        expires_at REAL NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_erp_sessions_expires_at ON erp_sessions (expires_at)",
    """
    CREATE TABLE IF NOT EXISTS erp_projects (
        id TEXT PRIMARY KEY,
        company TEXT NOT NULL,
        project_code TEXT NOT NULL,
        title TEXT NOT NULL,
        debtor_code TEXT NOT NULL DEFAULT '',
        debtor_name TEXT NOT NULL DEFAULT '',
        contact_person TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        site_address TEXT NOT NULL DEFAULT '',
        service_category TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Lead',
        expected_install_date TEXT NOT NULL DEFAULT '',
        completion_date TEXT NOT NULL DEFAULT '',
        quoted_total REAL,
        collected_total REAL,
        outstanding_amount REAL,
        estimated_cost REAL,
        actual_cost REAL,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        created_by TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT '',
        UNIQUE (company, project_code)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_erp_projects_company_updated ON erp_projects (company, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS erp_project_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        module TEXT NOT NULL,
        doc_no TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES erp_projects(id) ON DELETE CASCADE,
        UNIQUE (project_id, module, doc_no)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_erp_project_documents_lookup
    ON erp_project_documents (module, doc_no)
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_project_photos (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        company TEXT NOT NULL,
        stored_path TEXT NOT NULL,
        thumbnail_path TEXT NOT NULL DEFAULT '',
        content_type TEXT NOT NULL DEFAULT 'image/jpeg',
        original_filename TEXT NOT NULL DEFAULT '',
        service_category TEXT NOT NULL DEFAULT '',
        caption TEXT NOT NULL DEFAULT '',
        alt_text TEXT NOT NULL DEFAULT '',
        is_public INTEGER NOT NULL DEFAULT 0,
        website_visible INTEGER NOT NULL DEFAULT 0,
        is_cover INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        uploaded_by TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (project_id) REFERENCES erp_projects(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_erp_project_photos_project
    ON erp_project_photos (project_id, sort_order, created_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_erp_project_photos_public
    ON erp_project_photos (company, is_public, website_visible, sort_order)
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_website_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        project_code TEXT NOT NULL DEFAULT '',
        field_name TEXT NOT NULL DEFAULT '',
        old_value TEXT NOT NULL DEFAULT '',
        new_value TEXT NOT NULL DEFAULT '',
        username TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_erp_website_audit_company_created
    ON erp_website_audit_log (company, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS sengchong_services (
        no INTEGER PRIMARY KEY,
        service_name TEXT NOT NULL,
        bg TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sengchong_contacts (
        no INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        number TEXT NOT NULL,
        bg TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sengchong_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
)


class ErpDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect(initialize=False) as conn:
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.commit()
            self.path.chmod(0o600)
            self._initialized = True

    @contextmanager
    def connect(self, *, initialize=True):
        if initialize:
            self.initialize()

        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        self.initialize()
        with self._lock:
            with self.connect(initialize=False) as conn:
                try:
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise


def row_to_dict(row):
    return dict(row) if row is not None else None
