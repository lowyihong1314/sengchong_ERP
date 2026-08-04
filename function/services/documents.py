"""
The document inbox: take a file, file it, read it later.

Upload and reading are deliberately separated. Somebody photographing fifty
delivery orders on a phone should not be watching a spinner while each one is
sent to a model -- the upload stores the file and returns, and a worker drains
the queue behind it. Everything the reader needs is in the row, so the worker
can be killed and restarted without losing work.

Nothing here posts to AutoCount, payroll or anywhere else. A document is
recorded and read; acting on it is a separate decision.
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from models import db
from models.documents import ErpDocument

from .ai_extract import ExtractionError, extract, is_readable, pdf_page_count
from .values import now, to_iso

# How many documents are read at once. Each one is an API call taking a couple
# of seconds; four keeps a fifty-file batch moving without burying the account
# in concurrent requests.
MAX_CONCURRENT = 4

# One worker drains the whole queue, so a second one starting while the first
# still runs has nothing to do. This key gates that.
WORKER_LOCK_KEY = 0x0E7D0C57

# A document claimed but never finished -- worker killed, machine rebooted --
# goes back on the queue after this long rather than sitting in `analysing`.
STALE_CLAIM_MINUTES = 15

MAX_BYTES = 40 * 1024 * 1024

# Nothing is turned away at the door. A file the reader cannot handle -- a
# video, a spreadsheet macro, somebody's stray .py -- is still stored, still
# listed and still deduplicated, and simply never leaves the machine. It lands
# as `skipped` rather than `failed`, because nothing went wrong: this inbox
# just has nothing to say about it.
SKIPPED_STATUS = "skipped"


class DocumentStore:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.root = self.base_dir / "var" / "documents"

    # ------------------------------------------------------------- uploading

    def store_upload(self, company, username, uploaded_file):
        """
        Save one file and queue it. Returns (payload, duplicate_of_existing).

        The same bytes uploaded twice return the first document rather than
        raising, because a duplicate in a batch of fifty is a normal accident
        and should not fail the other forty-nine.
        """
        company = str(company or "").strip().upper()
        if not company:
            raise ValueError("Company is required.")

        filename = str(getattr(uploaded_file, "filename", "") or "").strip()
        suffix = Path(filename).suffix.lower()
        readable = is_readable(filename)

        uploaded_file.stream.seek(0)
        data = uploaded_file.stream.read(MAX_BYTES + 1)
        if not data:
            raise ValueError(f"{filename or 'file'} is empty.")
        if len(data) > MAX_BYTES:
            raise ValueError(f"{filename} is larger than {MAX_BYTES // (1024 * 1024)}MB.")

        digest = hashlib.sha256(data).hexdigest()
        existing = db.session.scalars(
            db.select(ErpDocument).where(
                ErpDocument.company == company, ErpDocument.sha256 == digest
            )
        ).first()
        if existing:
            return self._public(existing), True

        document_id = uuid.uuid4().hex
        timestamp = now()
        folder = self.root / _safe(company) / f"{timestamp.year:04d}-{timestamp.month:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        stored = folder / f"{document_id}{suffix}"
        stored.write_bytes(data)

        # The original is kept byte for byte -- it is the evidence. The preview
        # is a separate, smaller file so a list of fifty does not pull fifty
        # phone-camera originals over the wire.
        preview = self._write_preview(folder, document_id, stored, suffix) if readable else None

        document = ErpDocument(
            id=document_id,
            company=company,
            original_filename=filename[:255],
            stored_path=str(stored.relative_to(self.base_dir)),
            preview_path=str(preview.relative_to(self.base_dir)) if preview else "",
            mime_type=(getattr(uploaded_file, "mimetype", "") or "")[:64],
            byte_size=len(data),
            sha256=digest,
            page_count=pdf_page_count(stored) if readable else 1,
            status="pending" if readable else SKIPPED_STATUS,
            error_text="" if readable else f"{suffix or 'This file type'} is not read by the inbox.",
            uploaded_at=timestamp,
            uploaded_by=username or "",
            updated_at=timestamp,
            updated_by=username or "",
        )
        db.session.add(document)
        db.session.commit()
        return self._public(document), False

    def _write_preview(self, folder, document_id, stored, suffix):
        target = folder / f"{document_id}-preview.jpg"
        try:
            if suffix == ".pdf":
                out = subprocess.run(
                    ["pdftoppm", "-r", "80", "-png", "-f", "1", "-l", "1",
                     str(stored), str(folder / f"{document_id}-p")],
                    capture_output=True, timeout=120,
                )
                if out.returncode != 0:
                    return None
                pages = sorted(folder.glob(f"{document_id}-p*.png"))
                if not pages:
                    return None
                with Image.open(pages[0]) as image:
                    image.convert("RGB").resize(_fit(image.size, 900)).save(
                        target, "JPEG", quality=80, optimize=True)
                for page in pages:
                    page.unlink(missing_ok=True)
            else:
                with Image.open(stored) as image:
                    # Phone photos carry their rotation in EXIF; without this
                    # every portrait shot previews on its side.
                    fixed = ImageOps.exif_transpose(image).convert("RGB")
                    fixed.thumbnail((900, 900))
                    fixed.save(target, "JPEG", quality=80, optimize=True)
        except (UnidentifiedImageError, OSError, ValueError, subprocess.SubprocessError):
            # A preview is a convenience. Losing it must not lose the upload.
            return None
        return target if target.exists() else None

    @staticmethod
    def spawn_worker():
        """
        Hand the queue to a detached process and return.

        Detached on purpose: gunicorn recycles workers, and a reading that
        outlives the request must not die with the worker that started it. If
        one is already draining the queue this one exits on the lock, so
        spawning per upload costs a process start and nothing else.
        """
        try:
            subprocess.Popen(
                [sys.executable, "-m", "function.jobs.analyse_documents"],
                cwd=str(Path(__file__).resolve().parents[2]),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=dict(os.environ),
            )
            return True
        except OSError:
            # The rows are already `pending`; the next upload or the cron
            # sweep will pick them up.
            return False

    # -------------------------------------------------------------- the queue

    @staticmethod
    def claim_batch(limit=MAX_CONCURRENT):
        """
        Take up to `limit` pending documents for this worker.

        SKIP LOCKED is what makes concurrency safe here: two workers running at
        once take different rows instead of colliding or blocking.
        """
        cutoff = now() - dt.timedelta(minutes=STALE_CLAIM_MINUTES)
        rows = db.session.execute(
            db.text("""
                WITH claimed AS (
                    SELECT id FROM erp_documents
                    WHERE status = 'pending'
                       OR (status = 'analysing' AND updated_at < :cutoff)
                    ORDER BY uploaded_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT :limit
                )
                UPDATE erp_documents d
                   SET status = 'analysing', updated_at = :ts
                  FROM claimed
                 WHERE d.id = claimed.id
             RETURNING d.id
            """),
            {"cutoff": cutoff, "limit": limit, "ts": now()},
        ).scalars().all()
        db.session.commit()
        return list(rows)

    @staticmethod
    def pending_count():
        return db.session.execute(db.text(
            "SELECT count(*) FROM erp_documents WHERE status IN ('pending', 'analysing')"
        )).scalar() or 0

    def analyse(self, document_id, *, api_key, model):
        """Read one claimed document and record the result. Never raises."""
        document = db.session.get(ErpDocument, document_id)
        if not document:
            return None

        try:
            fields, usage = extract(
                self.base_dir / document.stored_path, api_key=api_key, model=model
            )
        except ExtractionError as error:
            document.status = "failed"
            document.error_text = str(error)[:2000]
            document.updated_at = now()
            db.session.commit()
            return self._public(document)
        except Exception as error:  # noqa: BLE001 - a worker must not die on one bad file
            document.status = "failed"
            document.error_text = f"{type(error).__name__}: {error}"[:2000]
            document.updated_at = now()
            db.session.commit()
            return self._public(document)

        document.raw_json = json.dumps(fields, ensure_ascii=False, indent=2)
        document.doc_class = str(fields.get("doc_class") or "other")[:24]
        document.confidence = _decimal(fields.get("confidence"), Decimal("0"))
        document.issuer = str(fields.get("issuer") or "")[:255]
        document.bill_to = str(fields.get("bill_to") or "")[:255]
        document.doc_no = str(fields.get("doc_no") or "")[:64]
        document.doc_date = _date(fields.get("doc_date"))
        document.currency = str(fields.get("currency") or "")[:8]
        document.total = _decimal(fields.get("total"), None)
        document.summary = str(fields.get("summary") or "")[:500]
        document.model_used = usage["model"][:64]
        document.tokens_in = usage["tokens_in"]
        document.tokens_out = usage["tokens_out"]
        document.analysed_at = now()
        document.status = "analysed"
        document.error_text = ""
        document.duplicate_of = self._find_duplicate(document)
        document.updated_at = now()
        db.session.commit()
        return self._public(document)

    @staticmethod
    def _find_duplicate(document):
        """
        The same invoice photographed twice is two files and one document.

        Matched on issuer and document number, which is what identifies a
        document on paper. Only flagged, never enforced: two handwritten
        vouchers really can share a number, and refusing the upload would lose
        the second one.
        """
        if not document.doc_no or not document.issuer:
            return None
        earlier = db.session.scalars(
            db.select(ErpDocument)
            .where(
                ErpDocument.company == document.company,
                ErpDocument.id != document.id,
                ErpDocument.doc_no == document.doc_no,
                ErpDocument.issuer == document.issuer,
                ErpDocument.status == "analysed",
                ErpDocument.duplicate_of.is_(None),
            )
            .order_by(ErpDocument.uploaded_at, ErpDocument.id)
        ).first()
        return earlier.id if earlier else None

    # ------------------------------------------------------------------ reads

    def list_documents(self, company, *, doc_class="", status="", query="", limit=200):
        statement = db.select(ErpDocument)
        if company:
            statement = statement.where(ErpDocument.company == str(company).strip().upper())
        if doc_class:
            statement = statement.where(ErpDocument.doc_class == doc_class)
        if status:
            statement = statement.where(ErpDocument.status == status)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(db.or_(
                ErpDocument.issuer.ilike(like),
                ErpDocument.bill_to.ilike(like),
                ErpDocument.doc_no.ilike(like),
                ErpDocument.summary.ilike(like),
                ErpDocument.original_filename.ilike(like),
            ))
        # id breaks ties: a batch of fifty uploads shares a timestamp to the
        # second, and without it the order changes between requests.
        statement = statement.order_by(
            ErpDocument.uploaded_at.desc(), ErpDocument.id.desc()
        ).limit(max(1, min(int(limit or 200), 1000)))
        return [self._public(row) for row in db.session.scalars(statement)]

    def get_document(self, document_id):
        document = db.session.get(ErpDocument, str(document_id or "").strip())
        if not document:
            return None
        payload = self._public(document)
        payload["raw"] = _parse_raw(document.raw_json)
        return payload

    def counts(self, company):
        rows = db.session.execute(
            db.text("""SELECT doc_class, status, count(*) FROM erp_documents
                       WHERE company = :c GROUP BY doc_class, status"""),
            {"c": str(company or "").strip().upper()},
        ).all()
        by_class, by_status = {}, {}
        for doc_class, status, count in rows:
            by_class[doc_class] = by_class.get(doc_class, 0) + count
            by_status[status] = by_status.get(status, 0) + count
        return {"byClass": by_class, "byStatus": by_status,
                "total": sum(by_status.values()), "queued": self.pending_count()}

    def requeue(self, document_id, username):
        document = db.session.get(ErpDocument, str(document_id or "").strip())
        if not document:
            return None
        if not is_readable(document.original_filename or document.stored_path):
            raise ValueError("This file type is not read by the inbox.")
        document.status = "pending"
        document.error_text = ""
        document.updated_at = now()
        document.updated_by = username or ""
        db.session.commit()
        return self._public(document)

    def delete_document(self, document_id):
        document = db.session.get(ErpDocument, str(document_id or "").strip())
        if not document:
            return None
        payload = self._public(document)
        for relative in (document.stored_path, document.preview_path):
            if relative:
                Path(self.base_dir / relative).unlink(missing_ok=True)
        db.session.delete(document)
        db.session.commit()
        return payload

    def file_path(self, document, *, preview=False):
        relative = document.get("previewPath") if preview else document.get("storedPath")
        if not relative:
            relative = document.get("storedPath")
        return self.base_dir / relative

    @staticmethod
    def _public(document):
        return {
            "id": document.id,
            "company": document.company,
            "filename": document.original_filename,
            "storedPath": document.stored_path,
            "previewPath": document.preview_path,
            "mimeType": document.mime_type,
            "byteSize": int(document.byte_size or 0),
            "pageCount": int(document.page_count or 1),
            "sha256": document.sha256,
            "status": document.status,
            "error": document.error_text,
            "docClass": document.doc_class,
            "confidence": float(document.confidence or 0),
            "issuer": document.issuer,
            "billTo": document.bill_to,
            "docNo": document.doc_no,
            "docDate": document.doc_date.isoformat() if document.doc_date else "",
            "currency": document.currency,
            "total": float(document.total) if document.total is not None else None,
            "summary": document.summary,
            "duplicateOf": document.duplicate_of or "",
            "model": document.model_used,
            "tokensIn": int(document.tokens_in or 0),
            "tokensOut": int(document.tokens_out or 0),
            "analysedAt": to_iso(document.analysed_at),
            "uploadedAt": to_iso(document.uploaded_at),
            "uploadedBy": document.uploaded_by,
        }


def _safe(value):
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(value or ""))
    return cleaned.strip("-") or "unknown"


def _fit(size, longest):
    width, height = size
    if max(size) <= longest:
        return size
    scale = longest / max(size)
    return max(1, int(width * scale)), max(1, int(height * scale))


def _decimal(value, default):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_raw(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None
