import json
from datetime import datetime, timezone


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


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SengchongContentStore:
    def __init__(self, db):
        self.db = db
        self.db.initialize()
        self.ensure_defaults()

    def ensure_defaults(self):
        with self.db.transaction() as conn:
            has_services = conn.execute("SELECT 1 FROM sengchong_services LIMIT 1").fetchone()
            has_contacts = conn.execute("SELECT 1 FROM sengchong_contacts LIMIT 1").fetchone()

            if not has_services:
                for service in DEFAULT_SERVICES:
                    conn.execute(
                        """
                        INSERT INTO sengchong_services (no, service_name, bg)
                        VALUES (?, ?, ?)
                        """,
                        (service["no"], service["service_name"], service["bg"]),
                    )
            if not has_contacts:
                for contact in DEFAULT_CONTACTS:
                    conn.execute(
                        """
                        INSERT INTO sengchong_contacts (no, name, number, bg)
                        VALUES (?, ?, ?, ?)
                        """,
                        (contact["no"], contact["name"], contact["number"], contact["bg"]),
                    )

            for key, value in DEFAULT_FOOTER.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sengchong_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, str(value), _now_iso()),
                )

    def get_home_page_data(self):
        with self.db.connect() as conn:
            services = [
                dict(row)
                for row in conn.execute(
                    "SELECT no, service_name, bg FROM sengchong_services ORDER BY no"
                ).fetchall()
            ]
            contacts = [
                dict(row)
                for row in conn.execute(
                    "SELECT no, name, number, bg FROM sengchong_contacts ORDER BY no"
                ).fetchall()
            ]
        return {"our_service": services, "contact_us": contacts}

    def get_content(self):
        home_page_data = self.get_home_page_data()
        return {
            "services": home_page_data["our_service"],
            "contacts": home_page_data["contact_us"],
            "footer": self.get_footer(),
        }

    def update_service(self, no, *, service_name=None, bg=None, company="", username=""):
        updates = []
        values = []
        field_changes = {}
        if service_name is not None:
            updates.append("service_name = ?")
            field_changes["service_name"] = str(service_name).strip()
            values.append(field_changes["service_name"])
        if bg is not None:
            updates.append("bg = ?")
            field_changes["bg"] = str(bg).strip()
            values.append(field_changes["bg"])
        if not updates:
            return
        values.append(int(no))
        with self.db.transaction() as conn:
            old_row = conn.execute(
                "SELECT no, service_name, bg FROM sengchong_services WHERE no = ?",
                (int(no),),
            ).fetchone()
            conn.execute(
                f"UPDATE sengchong_services SET {', '.join(updates)} WHERE no = ?",
                values,
            )
            if old_row:
                self._insert_change_audit(
                    conn,
                    company,
                    username,
                    "website_service_changed",
                    "website_service",
                    str(no),
                    old_row,
                    field_changes,
                )

    def update_contact(self, no, *, name=None, number=None, bg=None, company="", username=""):
        updates = []
        values = []
        field_changes = {}
        if name is not None:
            updates.append("name = ?")
            field_changes["name"] = str(name).strip()
            values.append(field_changes["name"])
        if number is not None:
            updates.append("number = ?")
            field_changes["number"] = str(number).strip()
            values.append(field_changes["number"])
        if bg is not None:
            updates.append("bg = ?")
            field_changes["bg"] = str(bg).strip()
            values.append(field_changes["bg"])
        if not updates:
            return
        values.append(int(no))
        with self.db.transaction() as conn:
            old_row = conn.execute(
                "SELECT no, name, number, bg FROM sengchong_contacts WHERE no = ?",
                (int(no),),
            ).fetchone()
            conn.execute(
                f"UPDATE sengchong_contacts SET {', '.join(updates)} WHERE no = ?",
                values,
            )
            if old_row:
                self._insert_change_audit(
                    conn,
                    company,
                    username,
                    "website_contact_changed",
                    "website_contact",
                    str(no),
                    old_row,
                    field_changes,
                )

    def get_footer(self):
        footer = dict(DEFAULT_FOOTER)
        with self.db.connect() as conn:
            rows = conn.execute("SELECT key, value FROM sengchong_settings").fetchall()
        for row in rows:
            footer[row["key"]] = row["value"]
        return footer

    def update_footer(self, payload, *, company="", username=""):
        allowed = {
            "year",
            "company_name",
            "registration_no",
            "address",
            "contact_person",
            "phone",
            "business_hours",
        }
        now = _now_iso()
        with self.db.transaction() as conn:
            old_values = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value FROM sengchong_settings").fetchall()
            }
            for key in allowed:
                if key not in payload:
                    continue
                next_value = str(payload.get(key) or "")
                conn.execute(
                    """
                    INSERT INTO sengchong_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, next_value, now),
                )
                self._insert_audit_if_changed(
                    conn,
                    company,
                    username,
                    "website_footer_changed",
                    "website_footer",
                    "footer",
                    key,
                    old_values.get(key, DEFAULT_FOOTER.get(key, "")),
                    next_value,
                )

    def _insert_change_audit(
        self,
        conn,
        company,
        username,
        action,
        entity_type,
        entity_id,
        old_row,
        field_changes,
    ):
        for field_name, new_value in field_changes.items():
            self._insert_audit_if_changed(
                conn,
                company,
                username,
                action,
                entity_type,
                entity_id,
                field_name,
                old_row[field_name],
                new_value,
            )

    def _insert_audit_if_changed(
        self,
        conn,
        company,
        username,
        action,
        entity_type,
        entity_id,
        field_name,
        old_value,
        new_value,
    ):
        old_text = self._audit_value(old_value)
        new_text = self._audit_value(new_value)
        if old_text == new_text:
            return
        conn.execute(
            """
            INSERT INTO erp_website_audit_log (
                company, action, entity_type, entity_id, project_code, field_name,
                old_value, new_value, username, created_at
            )
            VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?)
            """,
            (
                company or "",
                action,
                entity_type,
                entity_id,
                field_name,
                old_text,
                new_text,
                username or "",
                _now_iso(),
            ),
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
