import json

from models import db
from models.sengchong_content import (
    ErpWebsiteAuditLog,
    SengchongContact,
    SengchongService,
    SengchongSetting,
)

from .values import now


DEFAULT_SERVICES = (
    {"no": 1, "service_name": "电视机橱", "bg": "1.jpg"},
    {"no": 2, "service_name": "商场橱", "bg": "2.jpg"},
    {"no": 3, "service_name": "厨房橱", "bg": "3.jpg"},
    {"no": 4, "service_name": "衣橱", "bg": "4.jpg"},
    {"no": 5, "service_name": "床头柜", "bg": "5.jpg"},
    {"no": 6, "service_name": "拱门", "bg": "6.jpg"},
    {"no": 7, "service_name": "水盆橱", "bg": "7.jpg"},
    {"no": 8, "service_name": "展示柜", "bg": "8.jpg"},
    {"no": 9, "service_name": "设计", "bg": "9.jpg"},
)
DEFAULT_CONTACTS = (
    {"no": 1, "name": "Hong Zai", "number": "012-654 5265", "bg": "1.jpg"},
)
DEFAULT_FOOTER = {
    "year": "",
    "company_name": "Seng Chong Interior Design",
    "registration_no": "[JM0901797-D]",
    "address": "14 Jalan Canggih 5,\nTaman Perindustrian Cemerlang,\n81800 Ulutiram Johor",
    "contact_person": "Hongzai",
    "phone": "012-654 5265",
    "business_hours": "Monday to Friday 10am to 6pm",
}
FOOTER_KEYS = frozenset(DEFAULT_FOOTER)


class SengchongContentStore:
    """
    The public site's content: service cards, contacts and footer settings.

    sengchong.com only renders; everything here is edited from the ERP, and
    every edit is written to the website audit log.
    """

    def ensure_defaults(self):
        """
        Seed first-run content. Called from create_app inside an app context,
        not from __init__, because db.session needs one.
        """
        has_services = db.session.scalar(db.select(SengchongService.no).limit(1))
        has_contacts = db.session.scalar(db.select(SengchongContact.no).limit(1))

        if not has_services:
            db.session.add_all(SengchongService(**service) for service in DEFAULT_SERVICES)
        if not has_contacts:
            db.session.add_all(SengchongContact(**contact) for contact in DEFAULT_CONTACTS)

        # INSERT OR IGNORE: existing keys keep their edited value.
        existing_keys = set(db.session.scalars(db.select(SengchongSetting.key)))
        for key, value in DEFAULT_FOOTER.items():
            if key not in existing_keys:
                db.session.add(SengchongSetting(key=key, value=str(value), updated_at=now()))

        db.session.commit()

    def get_home_page_data(self):
        services = db.session.scalars(db.select(SengchongService).order_by(SengchongService.no))
        contacts = db.session.scalars(db.select(SengchongContact).order_by(SengchongContact.no))
        return {
            "our_service": [
                {"no": s.no, "service_name": s.service_name, "bg": s.bg} for s in services
            ],
            "contact_us": [
                {"no": c.no, "name": c.name, "number": c.number, "bg": c.bg} for c in contacts
            ],
        }

    def get_content(self):
        home_page_data = self.get_home_page_data()
        return {
            "services": home_page_data["our_service"],
            "contacts": home_page_data["contact_us"],
            "footer": self.get_footer(),
        }

    def update_service(self, no, *, service_name=None, bg=None, company="", username=""):
        field_changes = {}
        if service_name is not None:
            field_changes["service_name"] = str(service_name).strip()
        if bg is not None:
            field_changes["bg"] = str(bg).strip()
        if not field_changes:
            return

        service = db.session.get(SengchongService, int(no))
        if service is None:
            # Nothing to update and nothing to audit, matching the old
            # UPDATE ... WHERE no = ? that matched no rows.
            return

        before = {"service_name": service.service_name, "bg": service.bg}
        for field, value in field_changes.items():
            setattr(service, field, value)
        self._audit_changes(
            company, username, "website_service_changed", "website_service",
            str(no), before, field_changes,
        )
        db.session.commit()

    def update_contact(self, no, *, name=None, number=None, bg=None, company="", username=""):
        field_changes = {}
        if name is not None:
            field_changes["name"] = str(name).strip()
        if number is not None:
            field_changes["number"] = str(number).strip()
        if bg is not None:
            field_changes["bg"] = str(bg).strip()
        if not field_changes:
            return

        contact = db.session.get(SengchongContact, int(no))
        if contact is None:
            return

        before = {"name": contact.name, "number": contact.number, "bg": contact.bg}
        for field, value in field_changes.items():
            setattr(contact, field, value)
        self._audit_changes(
            company, username, "website_contact_changed", "website_contact",
            str(no), before, field_changes,
        )
        db.session.commit()

    def get_footer(self):
        footer = dict(DEFAULT_FOOTER)
        for setting in db.session.scalars(db.select(SengchongSetting)):
            footer[setting.key] = setting.value
        return footer

    def update_footer(self, payload, *, company="", username=""):
        timestamp = now()
        settings = {s.key: s for s in db.session.scalars(db.select(SengchongSetting))}
        old_values = {key: setting.value for key, setting in settings.items()}

        for key in FOOTER_KEYS:
            if key not in payload:
                continue
            next_value = str(payload.get(key) or "")

            setting = settings.get(key)
            if setting is None:
                setting = SengchongSetting(key=key, value=next_value, updated_at=timestamp)
                db.session.add(setting)
            else:
                setting.value = next_value
                setting.updated_at = timestamp

            self._audit_if_changed(
                company, username, "website_footer_changed", "website_footer", "footer",
                key, old_values.get(key, DEFAULT_FOOTER.get(key, "")), next_value,
            )

        db.session.commit()

    def _audit_changes(self, company, username, action, entity_type, entity_id, before, field_changes):
        for field_name, new_value in field_changes.items():
            self._audit_if_changed(
                company, username, action, entity_type, entity_id,
                field_name, before[field_name], new_value,
            )

    def _audit_if_changed(
        self, company, username, action, entity_type, entity_id, field_name, old_value, new_value
    ):
        old_text = self._audit_value(old_value)
        new_text = self._audit_value(new_value)
        if old_text == new_text:
            return

        db.session.add(
            ErpWebsiteAuditLog(
                company=company or "",
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                project_code="",
                field_name=field_name,
                old_value=old_text,
                new_value=new_text,
                username=username or "",
                created_at=now(),
            )
        )

    @staticmethod
    def _audit_value(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)
