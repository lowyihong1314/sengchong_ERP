import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from models import db
from models.project_data import ErpProject
from models.project_photos import ErpProjectPhoto
from models.sengchong_content import ErpWebsiteAuditLog


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
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_or_zero(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _safe_segment(value, fallback):
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    text = text.strip(".-")[:80]
    return text or fallback


class ProjectPhotoStore:
    """
    Project photos: the image files on disk plus their metadata rows.

    Publishing is deliberately two-flag: a photo must be both is_public and
    website_visible before sengchong.com may render it, and every flag change
    is written to the website audit log.
    """

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.photo_root = self.base_dir / "var" / "project-photos"

    # ------------------------------------------------------------------ reads

    def list_photos(self, company, project_key):
        project = self._get_project(_normalize_company(company), project_key)
        if not project:
            return None
        return [self._photo_payload(photo) for photo in self._photos_for_project(project.id)]

    def file_path(self, photo_id, *, company=None, public_only=False, thumbnail=False):
        photo = (
            self._get_photo(_normalize_company(company), photo_id)
            if company
            else self._get_photo_by_id(photo_id)
        )
        if not photo:
            return None
        if public_only and (not photo.is_public or not photo.website_visible):
            return None

        relative_path = photo.thumbnail_path if thumbnail and photo.thumbnail_path else photo.stored_path
        path = self.base_dir / relative_path
        return path if path.exists() else None

    def public_gallery(self, company):
        company = _normalize_company(company)
        query = (
            db.select(ErpProjectPhoto)
            .join(ErpProject, ErpProject.id == ErpProjectPhoto.project_id)
            .where(ErpProjectPhoto.is_public == 1, ErpProjectPhoto.website_visible == 1)
        )
        # An empty company means "every company", used by the public site.
        if company:
            query = query.where(ErpProjectPhoto.company == company)
        query = query.order_by(
            ErpProjectPhoto.is_cover.desc(),
            ErpProjectPhoto.sort_order.asc(),
            ErpProjectPhoto.created_at.desc(),
        )
        return [self._photo_payload(photo, public=True) for photo in db.session.scalars(query)]

    def website_gallery(self, company):
        rows = db.session.execute(
            db.select(ErpProjectPhoto, ErpProject)
            .join(ErpProject, ErpProject.id == ErpProjectPhoto.project_id)
            .where(ErpProjectPhoto.company == _normalize_company(company))
            .order_by(
                ErpProjectPhoto.website_visible.desc(),
                ErpProjectPhoto.is_public.desc(),
                ErpProjectPhoto.is_cover.desc(),
                ErpProjectPhoto.sort_order.asc(),
                ErpProjectPhoto.created_at.desc(),
            )
        )
        photos = [self._gallery_photo_payload(photo, project) for photo, project in rows]
        return {
            "data": photos,
            "count": len(photos),
            "publicCount": sum(1 for photo in photos if photo["isPublic"]),
            "websiteVisibleCount": sum(1 for photo in photos if photo["websiteVisible"]),
        }

    def website_audit_log(self, company, limit=80):
        limit = max(1, min(_int_or_zero(limit) or 80, 200))
        entries = db.session.scalars(
            db.select(ErpWebsiteAuditLog)
            .where(ErpWebsiteAuditLog.company == _normalize_company(company))
            .order_by(ErpWebsiteAuditLog.id.desc())
            .limit(limit)
        )
        return {"data": [self._audit_payload(entry) for entry in entries]}

    # ----------------------------------------------------------------- writes

    def add_photos(self, company, project_key, username, files, payload):
        company = _normalize_company(company)
        files = [file for file in files if getattr(file, "filename", "")]
        if not files:
            raise ValueError("At least one image is required.")
        is_public = _bool(payload.get("isPublic"))
        website_visible = _bool(payload.get("websiteVisible"))
        if website_visible and not is_public:
            raise ValueError("Website visible photos must also be public.")

        project = self._get_project(company, project_key)
        if not project:
            return None

        existing_count = self._photo_count(project.id)
        saved = []
        for index, uploaded_file in enumerate(files):
            photo_id = uuid.uuid4().hex
            stored_path, thumbnail_path = self._save_image(
                company, project.project_code, photo_id, uploaded_file
            )
            now = _now_iso()
            photo = ErpProjectPhoto(
                id=photo_id,
                project_id=project.id,
                company=company,
                stored_path=stored_path,
                thumbnail_path=thumbnail_path,
                content_type="image/jpeg",
                original_filename=_string_or_empty(uploaded_file.filename),
                service_category=_string_or_empty(payload.get("serviceCategory")),
                caption=_string_or_empty(payload.get("caption")),
                alt_text=_string_or_empty(payload.get("altText")),
                is_public=1 if is_public else 0,
                website_visible=1 if website_visible else 0,
                # The first photo of an empty project becomes the cover.
                is_cover=1 if existing_count == 0 and index == 0 else 0,
                sort_order=_int_or_zero(payload.get("sortOrder")) or existing_count + index + 1,
                created_at=now,
                updated_at=now,
                uploaded_by=username or "",
                updated_by=username or "",
            )
            db.session.add(photo)
            db.session.flush()
            saved.append(self._photo_payload(photo))

        db.session.commit()
        return saved

    def update_photo(self, company, photo_id, username, payload):
        company = _normalize_company(company)
        photo_id = str(photo_id or "").strip()
        if not photo_id:
            raise ValueError("Photo id is required.")

        photo = self._get_photo(company, photo_id)
        if not photo:
            return None
        project_code = self._project_code_for_photo(photo)

        changed = False
        audit_entries = []

        for api_field, column in TEXT_FIELDS.items():
            if api_field in payload:
                next_value = _string_or_empty(payload.get(api_field))
                self._append_audit_if_changed(
                    audit_entries, "photo_metadata_changed", api_field,
                    getattr(photo, column), next_value,
                )
                setattr(photo, column, next_value)
                changed = True

        current_public = bool(photo.is_public)
        current_visible = bool(photo.website_visible)
        next_public = _bool(payload.get("isPublic")) if "isPublic" in payload else current_public
        next_visible = (
            _bool(payload.get("websiteVisible")) if "websiteVisible" in payload else current_visible
        )
        # Turning a photo private also pulls it off the website, unless the
        # caller said otherwise in the same request.
        if "isPublic" in payload and not next_public and "websiteVisible" not in payload:
            next_visible = False
        if next_visible and not next_public:
            raise ValueError("Website visible photos must also be public.")

        if "isPublic" in payload:
            self._append_audit_if_changed(
                audit_entries,
                "photo_public_enabled" if next_public else "photo_public_disabled",
                "isPublic", current_public, next_public,
            )
            photo.is_public = 1 if next_public else 0
            changed = True

            if not next_public and "websiteVisible" not in payload:
                self._append_audit_if_changed(
                    audit_entries, "photo_website_hidden", "websiteVisible", current_visible, False
                )
                photo.website_visible = 0

        if "websiteVisible" in payload:
            self._append_audit_if_changed(
                audit_entries,
                "photo_website_published" if next_visible else "photo_website_hidden",
                "websiteVisible", current_visible, next_visible,
            )
            photo.website_visible = 1 if next_visible else 0
            changed = True

        if "sortOrder" in payload:
            next_sort_order = _int_or_zero(payload.get("sortOrder"))
            self._append_audit_if_changed(
                audit_entries, "photo_sort_changed", "sortOrder", photo.sort_order, next_sort_order
            )
            photo.sort_order = next_sort_order
            changed = True

        if "isCover" in payload:
            is_cover = _bool(payload.get("isCover"))
            # Read the old flag before the bulk clear below overwrites it,
            # otherwise the audit entry always compares against 0.
            current_cover = bool(photo.is_cover)
            if is_cover:
                # Only one cover per project. This clears the *other* photos;
                # clearing this one too would leave the session thinking
                # is_cover is unchanged, so the assignment below would emit no
                # UPDATE and the row would keep the cleared value.
                db.session.execute(
                    db.update(ErpProjectPhoto)
                    .where(
                        ErpProjectPhoto.project_id == photo.project_id,
                        ErpProjectPhoto.id != photo.id,
                    )
                    .values(is_cover=0),
                    execution_options={"synchronize_session": False},
                )
            self._append_audit_if_changed(
                audit_entries, "photo_cover_changed", "isCover", current_cover, is_cover
            )
            photo.is_cover = 1 if is_cover else 0
            changed = True

        if not changed:
            return self._photo_payload(photo)

        photo.updated_at = _now_iso()
        photo.updated_by = username or ""
        for entry in audit_entries:
            self._insert_audit(
                company, username, entry["action"], "project_photo", photo_id,
                project_code, entry["fieldName"], entry["oldValue"], entry["newValue"],
            )

        db.session.commit()
        return self._photo_payload(photo)

    def delete_photo(self, company, photo_id):
        photo = self._get_photo(_normalize_company(company), photo_id)
        if not photo:
            return None

        payload = self._photo_payload(photo)
        stored_path, thumbnail_path = photo.stored_path, photo.thumbnail_path
        db.session.delete(photo)
        db.session.commit()

        self._delete_file(stored_path)
        self._delete_file(thumbnail_path)
        return payload

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

        project = self._get_project(company, "WEBSITE-GALLERY")
        if not project:
            now = _now_iso()
            project = ErpProject(
                id=uuid.uuid4().hex,
                company=company,
                project_code="WEBSITE-GALLERY",
                title="Website Gallery",
                service_category="展示柜",
                status="Completed",
                notes="Imported legacy sengchong.com product gallery images.",
                created_at=now,
                updated_at=now,
                created_by=username or "",
                updated_by=username or "",
            )
            db.session.add(project)
            db.session.flush()

        existing_filenames = {
            (name or "").lower()
            for name in db.session.scalars(
                db.select(ErpProjectPhoto.original_filename).where(
                    ErpProjectPhoto.project_id == project.id
                )
            )
        }
        existing_count = self._photo_count(project.id)

        imported_rows = []
        skipped_count = 0
        for path in image_paths:
            if path.name.lower() in existing_filenames:
                skipped_count += 1
                continue

            photo_id = uuid.uuid4().hex
            stored_path, thumbnail_path = self._save_image_from_path(
                company, project.project_code, photo_id, path
            )
            now = _now_iso()
            photo = ErpProjectPhoto(
                id=photo_id,
                project_id=project.id,
                company=company,
                stored_path=stored_path,
                thumbnail_path=thumbnail_path,
                content_type="image/jpeg",
                original_filename=path.name,
                service_category=project.service_category or "展示柜",
                caption="",
                alt_text="",
                is_public=1,
                website_visible=1,
                is_cover=1 if existing_count == 0 and len(imported_rows) == 0 else 0,
                sort_order=_int_or_zero(path.stem) or existing_count + len(imported_rows) + 1,
                created_at=now,
                updated_at=now,
                uploaded_by=username or "",
                updated_by=username or "",
            )
            db.session.add(photo)
            db.session.flush()

            self._insert_audit(
                company, username, "legacy_product_imported", "project_photo", photo_id,
                project.project_code, "websiteVisible", "", "true",
            )
            imported_rows.append(self._photo_payload(photo))

        result = {
            "projectCode": project.project_code,
            "importedCount": len(imported_rows),
            "skippedCount": skipped_count,
            "data": imported_rows,
        }
        db.session.commit()
        return result

    # ---------------------------------------------------------------- lookups

    @staticmethod
    def _get_project(company, project_key):
        target = str(project_key or "").strip()
        return db.session.scalars(
            db.select(ErpProject).where(
                ErpProject.company == company,
                db.or_(ErpProject.id == target, ErpProject.project_code == target),
            )
        ).first()

    @staticmethod
    def _get_photo(company, photo_id):
        return db.session.scalars(
            db.select(ErpProjectPhoto).where(
                ErpProjectPhoto.company == company,
                ErpProjectPhoto.id == str(photo_id or "").strip(),
            )
        ).first()

    @staticmethod
    def _get_photo_by_id(photo_id):
        return db.session.get(ErpProjectPhoto, str(photo_id or "").strip())

    @staticmethod
    def _project_code_for_photo(photo):
        project = db.session.get(ErpProject, photo.project_id)
        return project.project_code if project else ""

    @staticmethod
    def _photo_count(project_id):
        return db.session.scalar(
            db.select(db.func.count())
            .select_from(ErpProjectPhoto)
            .where(ErpProjectPhoto.project_id == project_id)
        )

    @staticmethod
    def _photos_for_project(project_id):
        return db.session.scalars(
            db.select(ErpProjectPhoto)
            .where(ErpProjectPhoto.project_id == project_id)
            .order_by(
                ErpProjectPhoto.is_cover.desc(),
                ErpProjectPhoto.sort_order.asc(),
                ErpProjectPhoto.created_at.desc(),
            )
        )

    # ------------------------------------------------------------------ files

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

    # --------------------------------------------------------------- payloads

    def _photo_payload(self, photo, public=False):
        payload = {
            "id": photo.id,
            "serviceCategory": photo.service_category,
            "caption": photo.caption,
            "altText": photo.alt_text,
            "isPublic": bool(photo.is_public),
            "websiteVisible": bool(photo.website_visible),
            "isCover": bool(photo.is_cover),
            "sortOrder": photo.sort_order,
            "thumbnailUrl": f"/public-api/project-photos/{photo.id}/file?size=thumbnail"
            if public
            else f"/api/project-photos/{photo.id}/file?size=thumbnail",
            "fileUrl": f"/public-api/project-photos/{photo.id}/file"
            if public
            else f"/api/project-photos/{photo.id}/file",
        }
        if not public:
            payload.update(
                {
                    "company": photo.company,
                    "projectId": photo.project_id,
                    "originalFilename": photo.original_filename,
                    "createdAt": photo.created_at,
                    "updatedAt": photo.updated_at,
                    "uploadedBy": photo.uploaded_by,
                    "updatedBy": photo.updated_by,
                }
            )
        return payload

    def _gallery_photo_payload(self, photo, project):
        payload = self._photo_payload(photo)
        payload.update(
            {
                "projectCode": project.project_code,
                "projectTitle": project.title,
                "projectServiceCategory": project.service_category,
                "projectStatus": project.status,
                "projectDebtorName": project.debtor_name,
            }
        )
        return payload

    def _insert_audit(
        self,
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
        db.session.add(
            ErpWebsiteAuditLog(
                company=company,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                project_code=project_code or "",
                field_name=field_name or "",
                old_value=self._audit_value(old_value),
                new_value=self._audit_value(new_value),
                username=username or "",
                created_at=_now_iso(),
            )
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
    def _audit_payload(entry):
        return {
            "id": entry.id,
            "company": entry.company,
            "action": entry.action,
            "entityType": entry.entity_type,
            "entityId": entry.entity_id,
            "projectCode": entry.project_code,
            "fieldName": entry.field_name,
            "oldValue": entry.old_value,
            "newValue": entry.new_value,
            "username": entry.username,
            "createdAt": entry.created_at,
        }
