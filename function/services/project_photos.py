import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


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
BOOLEAN_FIELDS = {"isPublic", "websiteVisible", "isCover"}
TEXT_FIELDS = {
    "serviceCategory": "service_category",
    "caption": "caption",
    "altText": "alt_text",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_company(company):
    return str(company or "").strip().upper()


def _string_or_empty(value):
    if value is None:
        return ""
    return str(value).strip()


def _bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_or_zero(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_segment(value, fallback):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    text = text.strip(".-")[:80]
    return text or fallback


class ProjectPhotoStore:
    def __init__(self, db, base_dir):
        self.db = db
        self.base_dir = Path(base_dir)
        self.photo_root = self.base_dir / "var" / "project-photos"
        self.db.initialize()

    def list_photos(self, company, project_key):
        company = _normalize_company(company)
        with self.db.connect() as conn:
            project = self._get_project(conn, company, project_key)
            if not project:
                return None
            rows = self._photo_rows_for_project(conn, project["id"])
            return [self._photo_payload(row) for row in rows]

    def add_photos(self, company, project_key, username, files, payload):
        company = _normalize_company(company)
        files = [file for file in files if getattr(file, "filename", "")]
        if not files:
            raise ValueError("At least one image is required.")
        is_public = _bool(payload.get("isPublic"))
        website_visible = _bool(payload.get("websiteVisible"))
        if website_visible and not is_public:
            raise ValueError("Website visible photos must also be public.")

        with self.db.transaction() as conn:
            project = self._get_project(conn, company, project_key)
            if not project:
                return None

            existing_count = conn.execute(
                "SELECT COUNT(*) AS total FROM erp_project_photos WHERE project_id = ?",
                (project["id"],),
            ).fetchone()["total"]
            saved_rows = []
            for index, uploaded_file in enumerate(files):
                photo_id = uuid.uuid4().hex
                stored_path, thumbnail_path = self._save_image(
                    company,
                    project["project_code"],
                    photo_id,
                    uploaded_file,
                )
                now = _now_iso()
                is_cover = 1 if existing_count == 0 and index == 0 else 0
                sort_order = _int_or_zero(payload.get("sortOrder")) or existing_count + index + 1
                conn.execute(
                    """
                    INSERT INTO erp_project_photos (
                        id, project_id, company, stored_path, thumbnail_path, content_type,
                        original_filename, service_category, caption, alt_text,
                        is_public, website_visible, is_cover, sort_order,
                        created_at, updated_at, uploaded_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        photo_id,
                        project["id"],
                        company,
                        stored_path,
                        thumbnail_path,
                        "image/jpeg",
                        _string_or_empty(uploaded_file.filename),
                        _string_or_empty(payload.get("serviceCategory")),
                        _string_or_empty(payload.get("caption")),
                        _string_or_empty(payload.get("altText")),
                        1 if is_public else 0,
                        1 if website_visible else 0,
                        is_cover,
                        sort_order,
                        now,
                        now,
                        username or "",
                        username or "",
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM erp_project_photos WHERE id = ?",
                    (photo_id,),
                ).fetchone()
                saved_rows.append(self._photo_payload(row))

            return saved_rows

    def update_photo(self, company, photo_id, username, payload):
        company = _normalize_company(company)
        photo_id = str(photo_id or "").strip()
        if not photo_id:
            raise ValueError("Photo id is required.")

        with self.db.transaction() as conn:
            existing = self._get_photo(conn, company, photo_id)
            if not existing:
                return None
            project_code = self._project_code_for_photo(conn, existing)

            updates = []
            values = []
            audit_entries = []
            for api_field, column in TEXT_FIELDS.items():
                if api_field in payload:
                    next_value = _string_or_empty(payload.get(api_field))
                    updates.append(f"{column} = ?")
                    values.append(next_value)
                    self._append_audit_if_changed(
                        audit_entries,
                        "photo_metadata_changed",
                        api_field,
                        existing[column],
                        next_value,
                    )

            current_public = bool(existing["is_public"])
            current_visible = bool(existing["website_visible"])
            next_public = _bool(payload.get("isPublic")) if "isPublic" in payload else current_public
            next_visible = (
                _bool(payload.get("websiteVisible"))
                if "websiteVisible" in payload
                else current_visible
            )
            if "isPublic" in payload and not next_public and "websiteVisible" not in payload:
                next_visible = False
            if next_visible and not next_public:
                raise ValueError("Website visible photos must also be public.")

            if "isPublic" in payload:
                updates.append("is_public = ?")
                values.append(1 if next_public else 0)
                self._append_audit_if_changed(
                    audit_entries,
                    "photo_public_enabled" if next_public else "photo_public_disabled",
                    "isPublic",
                    current_public,
                    next_public,
                )
                if not next_public and "websiteVisible" not in payload:
                    updates.append("website_visible = ?")
                    values.append(0)
                    self._append_audit_if_changed(
                        audit_entries,
                        "photo_website_hidden",
                        "websiteVisible",
                        current_visible,
                        False,
                    )

            if "websiteVisible" in payload:
                updates.append("website_visible = ?")
                values.append(1 if next_visible else 0)
                self._append_audit_if_changed(
                    audit_entries,
                    "photo_website_published" if next_visible else "photo_website_hidden",
                    "websiteVisible",
                    current_visible,
                    next_visible,
                )

            if "sortOrder" in payload:
                next_sort_order = _int_or_zero(payload.get("sortOrder"))
                updates.append("sort_order = ?")
                values.append(next_sort_order)
                self._append_audit_if_changed(
                    audit_entries,
                    "photo_sort_changed",
                    "sortOrder",
                    existing["sort_order"],
                    next_sort_order,
                )

            if "isCover" in payload:
                is_cover = _bool(payload.get("isCover"))
                if is_cover:
                    conn.execute(
                        "UPDATE erp_project_photos SET is_cover = 0 WHERE project_id = ?",
                        (existing["project_id"],),
                    )
                updates.append("is_cover = ?")
                values.append(1 if is_cover else 0)
                self._append_audit_if_changed(
                    audit_entries,
                    "photo_cover_changed",
                    "isCover",
                    bool(existing["is_cover"]),
                    is_cover,
                )

            if not updates:
                return self._photo_payload(existing)

            updates.extend(["updated_at = ?", "updated_by = ?"])
            values.extend([_now_iso(), username or "", photo_id])
            conn.execute(
                f"UPDATE erp_project_photos SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            for audit_entry in audit_entries:
                self._insert_audit(
                    conn,
                    company,
                    username,
                    audit_entry["action"],
                    "project_photo",
                    photo_id,
                    project_code,
                    audit_entry["fieldName"],
                    audit_entry["oldValue"],
                    audit_entry["newValue"],
                )
            row = conn.execute("SELECT * FROM erp_project_photos WHERE id = ?", (photo_id,)).fetchone()
            return self._photo_payload(row)

    def delete_photo(self, company, photo_id):
        company = _normalize_company(company)
        with self.db.transaction() as conn:
            row = self._get_photo(conn, company, photo_id)
            if not row:
                return None
            conn.execute("DELETE FROM erp_project_photos WHERE id = ?", (row["id"],))

        self._delete_file(row["stored_path"])
        self._delete_file(row["thumbnail_path"])
        return self._photo_payload(row)

    def file_path(self, photo_id, *, company=None, public_only=False, thumbnail=False):
        with self.db.connect() as conn:
            row = self._get_photo(conn, _normalize_company(company), photo_id) if company else self._get_photo_by_id(conn, photo_id)
            if not row:
                return None
            if public_only and (not row["is_public"] or not row["website_visible"]):
                return None
            relative_path = row["thumbnail_path"] if thumbnail and row["thumbnail_path"] else row["stored_path"]
            path = self.base_dir / relative_path
            return path if path.exists() else None

    def public_gallery(self, company):
        company = _normalize_company(company)
        company_filter = "AND ph.company = ?" if company else ""
        params = (company,) if company else ()
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT ph.*
                FROM erp_project_photos ph
                JOIN erp_projects p ON p.id = ph.project_id
                WHERE ph.is_public = 1
                  AND ph.website_visible = 1
                  {company_filter}
                ORDER BY ph.is_cover DESC, ph.sort_order ASC, ph.created_at DESC
                """,
                params,
            ).fetchall()
            return [self._photo_payload(row, public=True) for row in rows]

    def website_gallery(self, company):
        company = _normalize_company(company)
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ph.*,
                    p.project_code AS project_code,
                    p.title AS project_title,
                    p.service_category AS project_service_category,
                    p.status AS project_status,
                    p.debtor_name AS project_debtor_name
                FROM erp_project_photos ph
                JOIN erp_projects p ON p.id = ph.project_id
                WHERE ph.company = ?
                ORDER BY
                    ph.website_visible DESC,
                    ph.is_public DESC,
                    ph.is_cover DESC,
                    ph.sort_order ASC,
                    ph.created_at DESC
                """,
                (company,),
            ).fetchall()
            photos = [self._gallery_photo_payload(row) for row in rows]
            return {
                "data": photos,
                "count": len(photos),
                "publicCount": sum(1 for photo in photos if photo["isPublic"]),
                "websiteVisibleCount": sum(1 for photo in photos if photo["websiteVisible"]),
            }

    def website_audit_log(self, company, limit=80):
        company = _normalize_company(company)
        limit = max(1, min(_int_or_zero(limit) or 80, 200))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM erp_website_audit_log
                WHERE company = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (company, limit),
            ).fetchall()
            return {"data": [self._audit_payload(row) for row in rows]}

    def import_legacy_product_images(self, company, username, source_dir):
        company = _normalize_company(company)
        source_dir = Path(source_dir)
        if not source_dir.exists():
            raise ValueError("Legacy product image folder was not found.")

        image_paths = sorted(
            path
            for path in source_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            and path.name.lower() != "bg.jpg"
        )
        if not image_paths:
            return {
                "projectCode": "WEBSITE-GALLERY",
                "importedCount": 0,
                "skippedCount": 0,
                "data": [],
            }

        with self.db.transaction() as conn:
            project = self._get_project(conn, company, "WEBSITE-GALLERY")
            if not project:
                project_id = uuid.uuid4().hex
                now = _now_iso()
                conn.execute(
                    """
                    INSERT INTO erp_projects (
                        id, company, project_code, title, service_category, status,
                        notes, created_at, updated_at, created_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        company,
                        "WEBSITE-GALLERY",
                        "Website Gallery",
                        "展示柜",
                        "Completed",
                        "Imported legacy sengchong.com product gallery images.",
                        now,
                        now,
                        username or "",
                        username or "",
                    ),
                )
                project = self._get_project(conn, company, "WEBSITE-GALLERY")

            existing_filenames = {
                row["original_filename"].lower()
                for row in conn.execute(
                    """
                    SELECT original_filename
                    FROM erp_project_photos
                    WHERE project_id = ?
                    """,
                    (project["id"],),
                ).fetchall()
            }
            existing_count = conn.execute(
                "SELECT COUNT(*) AS total FROM erp_project_photos WHERE project_id = ?",
                (project["id"],),
            ).fetchone()["total"]

            imported_rows = []
            skipped_count = 0
            for path in image_paths:
                if path.name.lower() in existing_filenames:
                    skipped_count += 1
                    continue

                photo_id = uuid.uuid4().hex
                stored_path, thumbnail_path = self._save_image_from_path(
                    company,
                    project["project_code"],
                    photo_id,
                    path,
                )
                now = _now_iso()
                sort_order = _int_or_zero(path.stem) or existing_count + len(imported_rows) + 1
                conn.execute(
                    """
                    INSERT INTO erp_project_photos (
                        id, project_id, company, stored_path, thumbnail_path, content_type,
                        original_filename, service_category, caption, alt_text,
                        is_public, website_visible, is_cover, sort_order,
                        created_at, updated_at, uploaded_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        photo_id,
                        project["id"],
                        company,
                        stored_path,
                        thumbnail_path,
                        "image/jpeg",
                        path.name,
                        project["service_category"] or "展示柜",
                        "",
                        "",
                        1,
                        1,
                        1 if existing_count == 0 and len(imported_rows) == 0 else 0,
                        sort_order,
                        now,
                        now,
                        username or "",
                        username or "",
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM erp_project_photos WHERE id = ?",
                    (photo_id,),
                ).fetchone()
                self._insert_audit(
                    conn,
                    company,
                    username,
                    "legacy_product_imported",
                    "project_photo",
                    photo_id,
                    project["project_code"],
                    "websiteVisible",
                    "",
                    "true",
                )
                imported_rows.append(self._photo_payload(row))

            return {
                "projectCode": project["project_code"],
                "importedCount": len(imported_rows),
                "skippedCount": skipped_count,
                "data": imported_rows,
            }

    def _get_project(self, conn, company, project_key):
        target = str(project_key or "").strip()
        return conn.execute(
            """
            SELECT *
            FROM erp_projects
            WHERE company = ? AND (id = ? OR project_code = ?)
            """,
            (company, target, target),
        ).fetchone()

    def _get_photo(self, conn, company, photo_id):
        return conn.execute(
            "SELECT * FROM erp_project_photos WHERE company = ? AND id = ?",
            (company, str(photo_id or "").strip()),
        ).fetchone()

    def _get_photo_by_id(self, conn, photo_id):
        return conn.execute(
            "SELECT * FROM erp_project_photos WHERE id = ?",
            (str(photo_id or "").strip(),),
        ).fetchone()

    def _project_code_for_photo(self, conn, photo):
        row = conn.execute(
            "SELECT project_code FROM erp_projects WHERE id = ?",
            (photo["project_id"],),
        ).fetchone()
        return row["project_code"] if row else ""

    def _photo_rows_for_project(self, conn, project_id):
        return conn.execute(
            """
            SELECT *
            FROM erp_project_photos
            WHERE project_id = ?
            ORDER BY is_cover DESC, sort_order ASC, created_at DESC
            """,
            (project_id,),
        ).fetchall()

    def _save_image(self, company, project_code, photo_id, uploaded_file):
        project_dir = (
            self.photo_root
            / _safe_segment(company, "company")
            / _safe_segment(project_code, "project")
        )
        project_dir.mkdir(parents=True, exist_ok=True)
        stored = project_dir / f"{photo_id}.jpg"
        thumbnail = project_dir / f"{photo_id}-thumb.jpg"

        try:
            uploaded_file.stream.seek(0)
            with Image.open(uploaded_file.stream) as image:
                image = ImageOps.exif_transpose(image)
                image = image.convert("RGB")
                full = image.copy()
                full.thumbnail((1920, 1920))
                full.save(stored, format="JPEG", quality=88, optimize=True)
                thumb = image.copy()
                thumb.thumbnail((640, 480))
                thumb.save(thumbnail, format="JPEG", quality=82, optimize=True)
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError(f"Invalid image file: {uploaded_file.filename}") from error

        return (
            str(stored.relative_to(self.base_dir)),
            str(thumbnail.relative_to(self.base_dir)),
        )

    def _save_image_from_path(self, company, project_code, photo_id, source_path):
        project_dir = (
            self.photo_root
            / _safe_segment(company, "company")
            / _safe_segment(project_code, "project")
        )
        project_dir.mkdir(parents=True, exist_ok=True)
        stored = project_dir / f"{photo_id}.jpg"
        thumbnail = project_dir / f"{photo_id}-thumb.jpg"

        try:
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                image = image.convert("RGB")
                full = image.copy()
                full.thumbnail((1920, 1920))
                full.save(stored, format="JPEG", quality=88, optimize=True)
                thumb = image.copy()
                thumb.thumbnail((640, 480))
                thumb.save(thumbnail, format="JPEG", quality=82, optimize=True)
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError(f"Invalid image file: {source_path.name}") from error

        return (
            str(stored.relative_to(self.base_dir)),
            str(thumbnail.relative_to(self.base_dir)),
        )

    def _delete_file(self, relative_path):
        if not relative_path:
            return
        try:
            (self.base_dir / relative_path).unlink(missing_ok=True)
        except OSError:
            pass

    def _photo_payload(self, row, public=False):
        payload = {
            "id": row["id"],
            "serviceCategory": row["service_category"],
            "caption": row["caption"],
            "altText": row["alt_text"],
            "isPublic": bool(row["is_public"]),
            "websiteVisible": bool(row["website_visible"]),
            "isCover": bool(row["is_cover"]),
            "sortOrder": row["sort_order"],
            "thumbnailUrl": f"/public-api/project-photos/{row['id']}/file?size=thumbnail"
            if public
            else f"/api/project-photos/{row['id']}/file?size=thumbnail",
            "fileUrl": f"/public-api/project-photos/{row['id']}/file"
            if public
            else f"/api/project-photos/{row['id']}/file",
        }
        if not public:
            payload.update(
                {
                    "company": row["company"],
                    "projectId": row["project_id"],
                    "originalFilename": row["original_filename"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                    "uploadedBy": row["uploaded_by"],
                    "updatedBy": row["updated_by"],
                }
            )
        return payload

    def _gallery_photo_payload(self, row):
        payload = self._photo_payload(row)
        payload.update(
            {
                "projectCode": row["project_code"],
                "projectTitle": row["project_title"],
                "projectServiceCategory": row["project_service_category"],
                "projectStatus": row["project_status"],
                "projectDebtorName": row["project_debtor_name"],
            }
        )
        return payload

    def _insert_audit(
        self,
        conn,
        company,
        username,
        action,
        entity_type,
        entity_id,
        project_code,
        field_name="",
        old_value="",
        new_value="",
    ):
        conn.execute(
            """
            INSERT INTO erp_website_audit_log (
                company, action, entity_type, entity_id, project_code, field_name,
                old_value, new_value, username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                action,
                entity_type,
                entity_id,
                project_code or "",
                field_name or "",
                self._audit_value(old_value),
                self._audit_value(new_value),
                username or "",
                _now_iso(),
            ),
        )

    def _append_audit_if_changed(self, audit_entries, action, field_name, old_value, new_value):
        old_text = self._audit_value(old_value)
        new_text = self._audit_value(new_value)
        if old_text == new_text:
            return
        audit_entries.append(
            {
                "action": action,
                "fieldName": field_name,
                "oldValue": old_text,
                "newValue": new_text,
            }
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

    @staticmethod
    def _audit_payload(row):
        return {
            "id": row["id"],
            "company": row["company"],
            "action": row["action"],
            "entityType": row["entity_type"],
            "entityId": row["entity_id"],
            "projectCode": row["project_code"],
            "fieldName": row["field_name"],
            "oldValue": row["old_value"],
            "newValue": row["new_value"],
            "username": row["username"],
            "createdAt": row["created_at"],
        }
