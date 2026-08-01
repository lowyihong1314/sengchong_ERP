import json
import uuid
import copy
from pathlib import Path
import subprocess
import time
from threading import Lock


PDF_OUTPUT_DIR = Path("/mnt/c/ProgramData/WSLGuard/ERPExports")


class AutoCountSdk:
    def __init__(self, settings):
        self.settings = settings
        self._cache = {}
        self._cache_lock = Lock()

    def login(self, *, database, username, password):
        if not username:
            return False, {"error": "Username is required."}

        return self._run_json(
            [
                "-File",
                str(self.settings.autocount_login_script),
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                database or self.settings.autocount_default_database,
                "-User",
                username,
                "-Password",
                password or "",
            ]
        )

    def list_resource(self, resource, session, *, refresh=False):
        if not self.settings.autocount_bridge_configured:
            return False, {"error": "AutoCount bridge account is not configured."}

        cache_key = ("list", session["database"], resource)
        if not refresh:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return True, cached

        ok, result = self._run_json(
            [
                "-File",
                str(self.settings.autocount_list_script),
                "-Resource",
                resource,
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                session["database"],
                "-User",
                self.settings.autocount_app_user,
                "-Password",
                self.settings.autocount_app_password,
            ]
        )

        if ok:
            self._cache_set(cache_key, result, self.settings.autocount_list_cache_ttl_seconds)

        return ok, result

    def get_resource_detail(self, resource, key, session, *, refresh=False):
        if not self.settings.autocount_bridge_configured:
            return False, {"error": "AutoCount bridge account is not configured."}

        cache_key = ("detail", session["database"], resource, key)
        if not refresh:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return True, cached

        ok, result = self._run_json(
            [
                "-File",
                str(self.settings.autocount_detail_script),
                "-Resource",
                resource,
                "-Key",
                key,
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                session["database"],
                "-User",
                self.settings.autocount_app_user,
                "-Password",
                self.settings.autocount_app_password,
            ]
        )

        if ok:
            self._cache_set(cache_key, result, self.settings.autocount_detail_cache_ttl_seconds)

        return ok, result

    def create_resource(self, resource, payload, session):
        if not self.settings.autocount_bridge_configured:
            return False, {"error": "AutoCount bridge account is not configured."}

        ok, result = self._run_json(
            [
                "-File",
                str(self.settings.autocount_create_script),
                "-Resource",
                resource,
                "-PayloadJson",
                json.dumps(payload),
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                session["database"],
                "-User",
                self.settings.autocount_app_user,
                "-Password",
                self.settings.autocount_app_password,
            ]
        )

        if ok:
            self._cache_delete_prefix(("list", session["database"]))
            self._cache_delete_prefix(("detail", session["database"], resource))
            if resource == "ar-payments":
                self._cache_delete_prefix(("detail", session["database"], "invoices"))

        return ok, result

    def reconcile_bank_transactions(self, payload, session):
        if not self.settings.autocount_bridge_configured:
            return False, {"error": "AutoCount bridge account is not configured."}

        ok, result = self._run_json(
            [
                "-File",
                str(self.settings.autocount_bank_reconcile_script),
                "-PayloadJson",
                json.dumps(payload),
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                session["database"],
                "-User",
                self.settings.autocount_app_user,
                "-Password",
                self.settings.autocount_app_password,
            ]
        )

        if ok:
            self._cache_delete_prefix(("list", session["database"]))
            self._cache_delete_prefix(("detail", session["database"], "bank-transactions"))
            self._cache_delete_prefix(("detail", session["database"], "cash-book"))

        return ok, result

    def export_pdf(self, resource, key, session):
        if not self.settings.autocount_bridge_configured:
            return False, {"error": "AutoCount bridge account is not configured."}

        PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = PDF_OUTPUT_DIR / f"{uuid.uuid4().hex}.pdf"

        ok, result = self._run_json(
            [
                "-File",
                str(self.settings.autocount_export_pdf_script),
                "-Resource",
                resource,
                "-Key",
                key,
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                session["database"],
                "-User",
                self.settings.autocount_app_user,
                "-Password",
                self.settings.autocount_app_password,
                "-OutputPath",
                self._to_windows_path(output_path),
            ]
        )

        if not ok:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False, result

        result["local_path"] = str(output_path)
        return True, result

    def export_invoice_payment_request_pdf(self, key, amount, session):
        if not self.settings.autocount_bridge_configured:
            return False, {"error": "AutoCount bridge account is not configured."}

        PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = PDF_OUTPUT_DIR / f"{uuid.uuid4().hex}.pdf"

        ok, result = self._run_json(
            [
                "-File",
                str(self.settings.autocount_export_pdf_script),
                "-Resource",
                "invoices",
                "-Key",
                key,
                "-PaymentRequestAmount",
                str(amount),
                "-SqlServer",
                self.settings.autocount_sql_server,
                "-SqlUser",
                self.settings.autocount_sql_user,
                "-SqlPassword",
                self.settings.autocount_sql_password,
                "-Database",
                session["database"],
                "-User",
                self.settings.autocount_app_user,
                "-Password",
                self.settings.autocount_app_password,
                "-OutputPath",
                self._to_windows_path(output_path),
            ]
        )

        if not ok:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False, result

        result["local_path"] = str(output_path)
        safe_key = str(result.get("docNo") or key).replace("/", "-").replace("\\", "-").replace(" ", "-")
        result["filename"] = f"payment-request-{safe_key}.pdf"
        return True, result

    def _run_json(self, args):
        try:
            completed = subprocess.run(
                [
                    self.settings.powershell_exe,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    *args,
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.settings.autocount_timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, {"error": f"AutoCount SDK bridge failed: {exc}"}

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        try:
            result = json.loads(stdout.splitlines()[-1]) if stdout else {}
        except json.JSONDecodeError:
            result = {"error": stdout or stderr}

        if completed.returncode != 0:
            if not result:
                result = {"error": stderr or stdout or "AutoCount SDK bridge failed."}
            return False, result

        return True, result

    def _cache_get(self, key):
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(key)
            if not entry:
                return None

            expires_at, result = entry
            if expires_at <= now:
                self._cache.pop(key, None)
                return None

            return copy.deepcopy(result)

    def _cache_set(self, key, result, ttl_seconds):
        if ttl_seconds <= 0:
            return

        with self._cache_lock:
            self._cache[key] = (time.monotonic() + ttl_seconds, copy.deepcopy(result))

    def _cache_delete_prefix(self, prefix):
        with self._cache_lock:
            for key in list(self._cache):
                if key[: len(prefix)] == prefix:
                    self._cache.pop(key, None)

    @staticmethod
    def _to_windows_path(path):
        path = Path(path)
        text = str(path)
        if text.startswith("/mnt/c/"):
            return "C:\\" + text[len("/mnt/c/") :].replace("/", "\\")
        return text
