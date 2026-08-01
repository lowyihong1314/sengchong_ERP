import re
import uuid
from datetime import datetime, timezone


SERVICE_CATEGORIES = (
    "电视机橱",
    "商场橱",
    "厨房橱",
    "衣橱",
    "床头柜",
    "拱门",
    "水盆橱",
    "展示柜",
    "设计",
)
PROJECT_STATUSES = (
    "Lead",
    "Quoted",
    "Confirmed",
    "In Progress",
    "Installed",
    "Completed",
    "On Hold",
    "Cancelled",
)
DOCUMENT_MODULE_FIELDS = {
    "quotations": ("quotationDocNo",),
    "invoices": ("invoiceDocNo",),
    "ar-payments": ("arPaymentDocNos",),
    "purchase-orders": ("purchaseOrderDocNos",),
    "ap-invoices": ("apInvoiceDocNos",),
}
PROJECT_COLUMNS = {
    "projectCode": "project_code",
    "title": "title",
    "debtorCode": "debtor_code",
    "debtorName": "debtor_name",
    "contactPerson": "contact_person",
    "phone": "phone",
    "siteAddress": "site_address",
    "serviceCategory": "service_category",
    "status": "status",
    "expectedInstallDate": "expected_install_date",
    "completionDate": "completion_date",
    "quotedTotal": "quoted_total",
    "collectedTotal": "collected_total",
    "outstandingAmount": "outstanding_amount",
    "estimatedCost": "estimated_cost",
    "actualCost": "actual_cost",
    "notes": "notes",
}
VALUE_FIELDS = {
    "quotedTotal",
    "collectedTotal",
    "outstandingAmount",
    "estimatedCost",
    "actualCost",
}
DOCUMENT_FIELDS = {
    "quotationDocNo": "quotations",
    "invoiceDocNo": "invoices",
    "purchaseOrderDocNos": "purchase-orders",
    "arPaymentDocNos": "ar-payments",
    "apInvoiceDocNos": "ap-invoices",
}
LIST_DOCUMENT_FIELDS = {
    "purchaseOrderDocNos",
    "arPaymentDocNos",
    "apInvoiceDocNos",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_company(company):
    return str(company or "").strip().upper()


def _normalize_key(value):
    return str(value or "").strip().lower()


def _split_doc_list(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = re.split(r"[\n,;]+", str(value))

    items = []
    seen = set()
    for raw_item in raw_items:
        item = str(raw_item or "").strip()
        key = _normalize_key(item)
        if item and key not in seen:
            items.append(item)
            seen.add(key)
    return items


def _number_or_none(value):
    if value in (None, ""):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _number_or_empty(value):
    return "" if value is None else value


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


class ProjectDataStore:
    def __init__(self, db):
        self.db = db
        self.db.initialize()

    def meta(self):
        return {
            "serviceCategories": list(SERVICE_CATEGORIES),
            "statuses": list(PROJECT_STATUSES),
            "documentModules": sorted(DOCUMENT_MODULE_FIELDS),
        }

    def list_projects(self, company):
        company = _normalize_company(company)
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM erp_projects
                WHERE company = ?
                ORDER BY updated_at DESC
                """,
                (company,),
            ).fetchall()
            return [self._public_project(conn, row) for row in rows]

    def get_project(self, company, project_key):
        company = _normalize_company(company)
        target = str(project_key or "").strip()
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM erp_projects
                WHERE company = ? AND (id = ? OR project_code = ?)
                """,
                (company, target, target),
            ).fetchone()
            return self._public_project(conn, row) if row else None

    def create_project(self, company, username, payload):
        company = _normalize_company(company)
        if not company:
            raise ValueError("Company is required.")

        project, documents = self._normalize_payload(payload, apply_defaults=True)
        if not project.get("title"):
            raise ValueError("Project title is required.")

        now = _now_iso()
        project_id = uuid.uuid4().hex
        with self.db.transaction() as conn:
            project_code = project.get("projectCode") or self._next_project_code(conn, company)
            self._ensure_unique_project_code(conn, company, project_code)
            conn.execute(
                """
                INSERT INTO erp_projects (
                    id, company, project_code, title, debtor_code, debtor_name, contact_person,
                    phone, site_address, service_category, status, expected_install_date,
                    completion_date, quoted_total, collected_total, outstanding_amount,
                    estimated_cost, actual_cost, notes, created_at, updated_at, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._project_insert_values(
                    project_id,
                    company,
                    project_code,
                    project,
                    now,
                    username or "",
                ),
            )
            self._replace_documents(conn, project_id, documents)
            row = conn.execute("SELECT * FROM erp_projects WHERE id = ?", (project_id,)).fetchone()
            return self._public_project(conn, row)

    def update_project(self, company, project_key, username, payload):
        company = _normalize_company(company)
        target = str(project_key or "").strip()
        project, documents = self._normalize_payload(payload)

        with self.db.transaction() as conn:
            existing = conn.execute(
                """
                SELECT *
                FROM erp_projects
                WHERE company = ? AND (id = ? OR project_code = ?)
                """,
                (company, target, target),
            ).fetchone()
            if not existing:
                return None

            next_code = project.get("projectCode") or existing["project_code"]
            if _normalize_key(next_code) != _normalize_key(existing["project_code"]):
                self._ensure_unique_project_code(conn, company, next_code, exclude_id=existing["id"])

            assignments = []
            values = []
            for api_field, column in PROJECT_COLUMNS.items():
                if api_field == "projectCode":
                    assignments.append("project_code = ?")
                    values.append(next_code)
                    continue
                if api_field not in project:
                    continue
                assignments.append(f"{column} = ?")
                values.append(project[api_field])

            assignments.extend(["updated_at = ?", "updated_by = ?"])
            values.extend([_now_iso(), username or ""])
            values.append(existing["id"])
            conn.execute(
                f"UPDATE erp_projects SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            if documents:
                self._replace_documents(conn, existing["id"], documents)
            row = conn.execute("SELECT * FROM erp_projects WHERE id = ?", (existing["id"],)).fetchone()
            return self._public_project(conn, row)

    def find_by_document(self, company, module, document_key):
        company = _normalize_company(company)
        module = str(module or "").strip()
        target = str(document_key or "").strip()
        if not target or module not in DOCUMENT_MODULE_FIELDS:
            return []

        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT p.*
                FROM erp_projects p
                JOIN erp_project_documents d ON d.project_id = p.id
                WHERE p.company = ? AND d.module = ? AND LOWER(d.doc_no) = LOWER(?)
                ORDER BY p.updated_at DESC
                """,
                (company, module, target),
            ).fetchall()
            return [self._public_project(conn, row) for row in rows]

    def linked_document_keys(self, company, modules=None):
        company = _normalize_company(company)
        modules = [str(module or "").strip() for module in (modules or DOCUMENT_MODULE_FIELDS)]
        modules = [module for module in modules if module]
        if not modules:
            return set()

        placeholders = ",".join("?" for _ in modules)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT d.module, d.doc_no
                FROM erp_project_documents d
                JOIN erp_projects p ON p.id = d.project_id
                WHERE p.company = ? AND d.module IN ({placeholders})
                """,
                (company, *modules),
            ).fetchall()
            return {
                (str(row["module"] or "").strip(), _normalize_key(row["doc_no"]))
                for row in rows
                if row["module"] and row["doc_no"]
            }

    def _normalize_payload(self, payload, apply_defaults=False):
        if not isinstance(payload, dict):
            raise ValueError("JSON object payload is required.")

        project = {}
        documents = {}
        for api_field, column in PROJECT_COLUMNS.items():
            if api_field not in payload:
                continue
            value = payload.get(api_field)
            if api_field in VALUE_FIELDS:
                project[api_field] = _number_or_none(value)
            else:
                project[api_field] = _string_or_empty(value)

        for api_field, module in DOCUMENT_FIELDS.items():
            if api_field not in payload:
                continue
            documents[module] = _split_doc_list(payload.get(api_field))

        if apply_defaults and not project.get("status"):
            project["status"] = "Lead"
        if apply_defaults and not project.get("serviceCategory"):
            project["serviceCategory"] = SERVICE_CATEGORIES[0]

        return project, documents

    def _project_insert_values(self, project_id, company, project_code, project, now, username):
        return (
            project_id,
            company,
            project_code,
            project.get("title") or "",
            project.get("debtorCode") or "",
            project.get("debtorName") or "",
            project.get("contactPerson") or "",
            project.get("phone") or "",
            project.get("siteAddress") or "",
            project.get("serviceCategory") or SERVICE_CATEGORIES[0],
            project.get("status") or "Lead",
            project.get("expectedInstallDate") or "",
            project.get("completionDate") or "",
            project.get("quotedTotal"),
            project.get("collectedTotal"),
            project.get("outstandingAmount"),
            project.get("estimatedCost"),
            project.get("actualCost"),
            project.get("notes") or "",
            now,
            now,
            username,
            username,
        )

    def _replace_documents(self, conn, project_id, documents):
        if not documents:
            return

        modules = list(documents)
        placeholders = ",".join("?" for _ in modules)
        conn.execute(
            f"DELETE FROM erp_project_documents WHERE project_id = ? AND module IN ({placeholders})",
            [project_id, *modules],
        )
        for module, doc_nos in documents.items():
            for doc_no in doc_nos:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO erp_project_documents (project_id, module, doc_no)
                    VALUES (?, ?, ?)
                    """,
                    (project_id, module, doc_no),
                )

    def _next_project_code(self, conn, company):
        prefix = datetime.now().strftime("JOB-%y%m")
        rows = conn.execute(
            """
            SELECT project_code
            FROM erp_projects
            WHERE company = ? AND project_code LIKE ?
            """,
            (company, f"{prefix}-%"),
        ).fetchall()
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
        current = 0
        for row in rows:
            match = pattern.match(row["project_code"] or "")
            if match:
                current = max(current, int(match.group(1)))
        return f"{prefix}-{current + 1:03d}"

    def _ensure_unique_project_code(self, conn, company, project_code, exclude_id=None):
        code = str(project_code or "").strip()
        if not code:
            raise ValueError("Project code is required.")
        row = conn.execute(
            """
            SELECT id
            FROM erp_projects
            WHERE company = ? AND LOWER(project_code) = LOWER(?)
            """,
            (company, code),
        ).fetchone()
        if row and row["id"] != exclude_id:
            raise ValueError(f"Project code already exists: {project_code}")

    def _documents_by_module(self, conn, project_id):
        rows = conn.execute(
            """
            SELECT module, doc_no
            FROM erp_project_documents
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()
        documents = {}
        for row in rows:
            documents.setdefault(row["module"], []).append(row["doc_no"])
        return documents

    def _public_project(self, conn, row):
        documents = self._documents_by_module(conn, row["id"])
        quotations = documents.get("quotations", [])
        invoices = documents.get("invoices", [])
        project = {
            "id": row["id"],
            "company": row["company"],
            "projectCode": row["project_code"],
            "title": row["title"],
            "debtorCode": row["debtor_code"],
            "debtorName": row["debtor_name"],
            "contactPerson": row["contact_person"],
            "phone": row["phone"],
            "siteAddress": row["site_address"],
            "serviceCategory": row["service_category"],
            "status": row["status"],
            "quotationDocNo": (quotations or [""])[0],
            "quotationDocNos": quotations,
            "quotationDocNosText": ", ".join(quotations),
            "invoiceDocNo": (invoices or [""])[0],
            "invoiceDocNos": invoices,
            "invoiceDocNosText": ", ".join(invoices),
            "purchaseOrderDocNos": documents.get("purchase-orders", []),
            "purchaseOrderDocNosText": ", ".join(documents.get("purchase-orders", [])),
            "arPaymentDocNos": documents.get("ar-payments", []),
            "arPaymentDocNosText": ", ".join(documents.get("ar-payments", [])),
            "apInvoiceDocNos": documents.get("ap-invoices", []),
            "apInvoiceDocNosText": ", ".join(documents.get("ap-invoices", [])),
            "expectedInstallDate": row["expected_install_date"],
            "completionDate": row["completion_date"],
            "quotedTotal": _number_or_empty(row["quoted_total"]),
            "collectedTotal": _number_or_empty(row["collected_total"]),
            "outstandingAmount": _number_or_empty(row["outstanding_amount"]),
            "estimatedCost": _number_or_empty(row["estimated_cost"]),
            "actualCost": _number_or_empty(row["actual_cost"]),
            "notes": row["notes"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "createdBy": row["created_by"],
            "updatedBy": row["updated_by"],
        }
        collected = row["collected_total"]
        actual_cost = row["actual_cost"]
        project["margin"] = (
            round(collected - actual_cost, 2)
            if collected is not None and actual_cost is not None
            else ""
        )
        return project
