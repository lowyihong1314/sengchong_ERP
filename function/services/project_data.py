import re
import uuid
from datetime import datetime

from models import db
from models.project_data import ErpProject, ErpProjectDocument

from .values import money_or_empty, now, parse_date, parse_money, to_date_text, to_iso


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
DATE_FIELDS = {"expectedInstallDate", "completionDate"}
DOCUMENT_FIELDS = {
    "quotationDocNo": "quotations",
    "invoiceDocNo": "invoices",
    "purchaseOrderDocNos": "purchase-orders",
    "arPaymentDocNos": "ar-payments",
    "apInvoiceDocNos": "ap-invoices",
}


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


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


class ProjectDataStore:
    """
    The ERP-owned project/job layer.

    A project groups the AutoCount documents raised for one customer job. The
    document links live in erp_project_documents and are matched by document
    number, so nothing here writes to AutoCount.
    """

    def meta(self):
        return {
            "serviceCategories": list(SERVICE_CATEGORIES),
            "statuses": list(PROJECT_STATUSES),
            "documentModules": sorted(DOCUMENT_MODULE_FIELDS),
        }

    def list_projects(self, company):
        projects = db.session.scalars(
            db.select(ErpProject)
            .where(ErpProject.company == _normalize_company(company))
            .order_by(ErpProject.updated_at.desc())
        )
        return [self._public_project(project) for project in projects]

    def get_project(self, company, project_key):
        project = self._find(company, project_key)
        return self._public_project(project) if project else None

    def create_project(self, company, username, payload):
        company = _normalize_company(company)
        if not company:
            raise ValueError("Company is required.")

        fields, documents = self._normalize_payload(payload, apply_defaults=True)
        if not fields.get("title"):
            raise ValueError("Project title is required.")

        timestamp = now()
        project_code = fields.get("projectCode") or self._next_project_code(company)
        self._ensure_unique_project_code(company, project_code)

        project = ErpProject(
            id=uuid.uuid4().hex,
            company=company,
            project_code=project_code,
            title=fields.get("title") or "",
            debtor_code=fields.get("debtorCode") or "",
            debtor_name=fields.get("debtorName") or "",
            contact_person=fields.get("contactPerson") or "",
            phone=fields.get("phone") or "",
            site_address=fields.get("siteAddress") or "",
            service_category=fields.get("serviceCategory") or SERVICE_CATEGORIES[0],
            status=fields.get("status") or "Lead",
            expected_install_date=fields.get("expectedInstallDate"),
            completion_date=fields.get("completionDate"),
            quoted_total=fields.get("quotedTotal"),
            collected_total=fields.get("collectedTotal"),
            outstanding_amount=fields.get("outstandingAmount"),
            estimated_cost=fields.get("estimatedCost"),
            actual_cost=fields.get("actualCost"),
            notes=fields.get("notes") or "",
            created_at=timestamp,
            updated_at=timestamp,
            created_by=username or "",
            updated_by=username or "",
        )
        db.session.add(project)
        db.session.flush()

        self._replace_documents(project.id, documents)
        db.session.commit()

        return self._public_project(project)

    def update_project(self, company, project_key, username, payload):
        company = _normalize_company(company)
        fields, documents = self._normalize_payload(payload)

        project = self._find(company, project_key)
        if not project:
            return None

        next_code = fields.get("projectCode") or project.project_code
        if _normalize_key(next_code) != _normalize_key(project.project_code):
            self._ensure_unique_project_code(company, next_code, exclude_id=project.id)

        # project_code is always written back, the rest only when supplied.
        project.project_code = next_code
        for api_field, column in PROJECT_COLUMNS.items():
            if api_field == "projectCode" or api_field not in fields:
                continue
            setattr(project, column, fields[api_field])

        project.updated_at = now()
        project.updated_by = username or ""

        if documents:
            self._replace_documents(project.id, documents)

        db.session.commit()
        return self._public_project(project)

    def find_by_document(self, company, module, document_key):
        company = _normalize_company(company)
        module = str(module or "").strip()
        target = str(document_key or "").strip()
        if not target or module not in DOCUMENT_MODULE_FIELDS:
            return []

        projects = db.session.scalars(
            db.select(ErpProject)
            .join(ErpProjectDocument, ErpProjectDocument.project_id == ErpProject.id)
            .where(
                ErpProject.company == company,
                ErpProjectDocument.module == module,
                db.func.lower(ErpProjectDocument.doc_no) == db.func.lower(target),
            )
            .distinct()
            .order_by(ErpProject.updated_at.desc())
        )
        return [self._public_project(project) for project in projects]

    def linked_document_keys(self, company, modules=None):
        company = _normalize_company(company)
        modules = [str(module or "").strip() for module in (modules or DOCUMENT_MODULE_FIELDS)]
        modules = [module for module in modules if module]
        if not modules:
            return set()

        rows = db.session.execute(
            db.select(ErpProjectDocument.module, ErpProjectDocument.doc_no)
            .join(ErpProject, ErpProject.id == ErpProjectDocument.project_id)
            .where(ErpProject.company == company, ErpProjectDocument.module.in_(modules))
        )
        return {
            (str(module or "").strip(), _normalize_key(doc_no))
            for module, doc_no in rows
            if module and doc_no
        }

    def _find(self, company, project_key):
        """A project is addressable by either its uuid or its project code."""
        target = str(project_key or "").strip()
        return db.session.scalars(
            db.select(ErpProject).where(
                ErpProject.company == _normalize_company(company),
                db.or_(ErpProject.id == target, ErpProject.project_code == target),
            )
        ).first()

    def _normalize_payload(self, payload, apply_defaults=False):
        if not isinstance(payload, dict):
            raise ValueError("JSON object payload is required.")

        project = {}
        documents = {}
        for api_field in PROJECT_COLUMNS:
            if api_field not in payload:
                continue
            value = payload.get(api_field)
            if api_field in VALUE_FIELDS:
                project[api_field] = parse_money(value)
            elif api_field in DATE_FIELDS:
                project[api_field] = parse_date(value)
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

    def _replace_documents(self, project_id, documents):
        """Replace the links for exactly the modules named in `documents`."""
        if not documents:
            return

        db.session.execute(
            db.delete(ErpProjectDocument).where(
                ErpProjectDocument.project_id == project_id,
                ErpProjectDocument.module.in_(list(documents)),
            )
        )
        for module, doc_nos in documents.items():
            for doc_no in doc_nos:
                db.session.add(
                    ErpProjectDocument(project_id=project_id, module=module, doc_no=doc_no)
                )
        db.session.flush()

    def _next_project_code(self, company):
        prefix = datetime.now().strftime("JOB-%y%m")
        codes = db.session.scalars(
            db.select(ErpProject.project_code).where(
                ErpProject.company == company,
                ErpProject.project_code.like(f"{prefix}-%"),
            )
        )
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
        current = 0
        for code in codes:
            match = pattern.match(code or "")
            if match:
                current = max(current, int(match.group(1)))
        return f"{prefix}-{current + 1:03d}"

    def _ensure_unique_project_code(self, company, project_code, exclude_id=None):
        code = str(project_code or "").strip()
        if not code:
            raise ValueError("Project code is required.")

        clash = db.session.scalars(
            db.select(ErpProject.id).where(
                ErpProject.company == company,
                db.func.lower(ErpProject.project_code) == db.func.lower(code),
            )
        ).first()
        if clash and clash != exclude_id:
            raise ValueError(f"Project code already exists: {project_code}")

    @staticmethod
    def _documents_by_module(project_id):
        rows = db.session.execute(
            db.select(ErpProjectDocument.module, ErpProjectDocument.doc_no)
            .where(ErpProjectDocument.project_id == project_id)
            .order_by(ErpProjectDocument.id)
        )
        documents = {}
        for module, doc_no in rows:
            documents.setdefault(module, []).append(doc_no)
        return documents

    def _public_project(self, project):
        documents = self._documents_by_module(project.id)
        quotations = documents.get("quotations", [])
        invoices = documents.get("invoices", [])
        payload = {
            "id": project.id,
            "company": project.company,
            "projectCode": project.project_code,
            "title": project.title,
            "debtorCode": project.debtor_code,
            "debtorName": project.debtor_name,
            "contactPerson": project.contact_person,
            "phone": project.phone,
            "siteAddress": project.site_address,
            "serviceCategory": project.service_category,
            "status": project.status,
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
            "expectedInstallDate": to_date_text(project.expected_install_date),
            "completionDate": to_date_text(project.completion_date),
            "quotedTotal": money_or_empty(project.quoted_total),
            "collectedTotal": money_or_empty(project.collected_total),
            "outstandingAmount": money_or_empty(project.outstanding_amount),
            "estimatedCost": money_or_empty(project.estimated_cost),
            "actualCost": money_or_empty(project.actual_cost),
            "notes": project.notes,
            "createdAt": to_iso(project.created_at),
            "updatedAt": to_iso(project.updated_at),
            "createdBy": project.created_by,
            "updatedBy": project.updated_by,
        }
        collected = project.collected_total
        actual_cost = project.actual_cost
        payload["margin"] = (
            float(round(collected - actual_cost, 2))
            if collected is not None and actual_cost is not None
            else ""
        )
        return payload
