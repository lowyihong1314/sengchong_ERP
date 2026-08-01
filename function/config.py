import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_COMPANY_DATABASES = (
    {"value": "AED_SENG", "label": "SENG CHONG INTERIOR DESIGN"},
    {"value": "AED_MANSON", "label": "MANSON LIANG INTERIOR & RENOVATION"},
)


def load_env_file(path):
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name, default=""):
    return os.getenv(name, default)


def parse_company_databases(value):
    if not value:
        return DEFAULT_COMPANY_DATABASES

    companies = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if ":" in item:
            database, label = item.split(":", 1)
        else:
            database, label = item, item
        database = database.strip()
        label = label.strip() or database
        if database:
            companies.append({"value": database, "label": label})

    return tuple(companies) or DEFAULT_COMPANY_DATABASES


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    frontend_dist_dir: Path
    erp_db_path: Path
    database_url: str
    sengchong_static_dir: Path
    sengchong_template_dir: Path
    flask_secret_key: str
    autocount_timeout: float
    autocount_list_cache_ttl_seconds: float
    autocount_detail_cache_ttl_seconds: float
    autocount_sql_server: str
    autocount_sql_direct_server: str
    autocount_sql_direct_port: int
    autocount_sql_direct_enabled: bool
    autocount_sql_user: str
    autocount_sql_password: str
    autocount_app_user: str
    autocount_app_password: str
    autocount_default_database: str
    autocount_list_script: Path
    autocount_detail_script: Path
    autocount_create_script: Path
    autocount_bank_reconcile_script: Path
    autocount_export_pdf_script: Path
    powershell_exe: str
    session_ttl_seconds: int
    company_databases: tuple
    allowed_resources: tuple

    @classmethod
    def from_env(cls):
        load_env_file(BASE_DIR / ".env")

        return cls(
            base_dir=BASE_DIR,
            frontend_dist_dir=BASE_DIR / "frontend" / "dist",
            erp_db_path=BASE_DIR / "erp_data.db",
            # The single switch for the eventual Postgres move. Leave unset to
            # keep using the local SQLite file; set to
            # postgresql+psycopg://user:pass@host/dbname to move over.
            database_url=env("DATABASE_URL", "") or f"sqlite:///{BASE_DIR / 'erp_data.db'}",
            sengchong_static_dir=BASE_DIR / "sengchong" / "static",
            sengchong_template_dir=BASE_DIR / "sengchong" / "templates",
            flask_secret_key=env(
                "ERP_FLASK_SECRET_KEY",
                env("SENGCHONG_SECRET_KEY", "erp-gateway-local-secret"),
            ),
            autocount_timeout=float(env("AUTOCOUNT_PROXY_TIMEOUT", "30")),
            autocount_list_cache_ttl_seconds=float(env("AUTOCOUNT_LIST_CACHE_TTL_SECONDS", "120")),
            autocount_detail_cache_ttl_seconds=float(env("AUTOCOUNT_DETAIL_CACHE_TTL_SECONDS", "300")),
            autocount_sql_server=env("AUTOCOUNT_SQL_SERVER"),
            autocount_sql_direct_server=env("AUTOCOUNT_SQL_DIRECT_SERVER", ""),
            autocount_sql_direct_port=int(env("AUTOCOUNT_SQL_DIRECT_PORT", "0") or "0"),
            autocount_sql_direct_enabled=env("AUTOCOUNT_SQL_DIRECT_ENABLED", "1").lower()
            not in {"0", "false", "no", "off"},
            autocount_sql_user=env("AUTOCOUNT_SQL_USER"),
            autocount_sql_password=env("AUTOCOUNT_SQL_PASSWORD"),
            autocount_app_user=env("AUTOCOUNT_APP_USER", env("AUTOCOUNT_USER", "ADMIN")),
            autocount_app_password=env("AUTOCOUNT_APP_PASSWORD", env("AUTOCOUNT_PASSWORD", "")),
            autocount_default_database=env("AUTOCOUNT_DEFAULT_DATABASE", "AED_SENG"),
            autocount_list_script=BASE_DIR / "scripts" / "autocount_list.ps1",
            autocount_detail_script=BASE_DIR / "scripts" / "autocount_detail.ps1",
            autocount_create_script=BASE_DIR / "scripts" / "autocount_create.ps1",
            autocount_bank_reconcile_script=BASE_DIR / "scripts" / "autocount_bank_reconcile.ps1",
            autocount_export_pdf_script=BASE_DIR / "scripts" / "autocount_export_pdf.ps1",
            powershell_exe=env(
                "POWERSHELL_EXE",
                "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            ),
            session_ttl_seconds=int(env("AUTOCOUNT_SESSION_TTL_SECONDS", "28800")),
            company_databases=parse_company_databases(env("AUTOCOUNT_COMPANIES")),
            allowed_resources=(
                "invoices",
                "ar-payments",
                "ar-deposits",
                "ap-invoices",
                "ap-payments",
                "ap-deposits",
                "cash-book",
                "bank-transactions",
                "creditors",
                "payment-methods",
                "quotations",
                "items",
                "purchase-orders",
                "debtors",
            ),
        )

    @property
    def autocount_sdk_configured(self):
        return bool(
            self.autocount_sql_server
            and self.autocount_sql_user
            and self.autocount_sql_password
        )

    @property
    def autocount_bridge_configured(self):
        return self.autocount_sdk_configured and bool(
            self.autocount_app_user and self.autocount_app_password
        )
