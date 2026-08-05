from models import db


class ErpDocument(db.Model):
    """
    One uploaded document: the file as it arrived, plus whatever the extraction
    made of it.

    This table only records. Nothing downstream reads it to post an invoice or
    build a payroll line -- a document sitting here has been filed and read,
    not acted on. That separation is deliberate: the extraction is a machine's
    reading of a photograph and has to be reviewable before anything is done
    with it.

    The original file is never modified. `raw_json` keeps the extraction
    verbatim, including fields this table has no column for, so a later change
    of mind about classification or about which fields matter can be answered
    from what is already stored instead of paying to read every document again.
    """

    __tablename__ = "erp_documents"
    __table_args__ = (
        # Same bytes, same document. Scoped per company because the two firms
        # keep separate books and the same supplier statement can legitimately
        # be filed under both.
        db.UniqueConstraint("company", "sha256", name="uq_erp_documents_company_sha256"),
        db.Index("ix_erp_documents_company_class", "company", "doc_class"),
        db.Index("ix_erp_documents_company_uploaded", "company", "uploaded_at"),
        # Drives the second dedupe pass: the same invoice photographed twice is
        # two different files but one document number.
        db.Index("ix_erp_documents_dupe", "company", "issuer", "doc_no"),
    )

    id = db.Column(db.String(32), primary_key=True)  # uuid4().hex
    company = db.Column(db.String(64), nullable=False)

    # --- the file as it arrived -----------------------------------------
    original_filename = db.Column(db.String(255), nullable=False, default="", server_default="")
    stored_path = db.Column(db.String(255), nullable=False)
    preview_path = db.Column(db.String(255), nullable=False, default="", server_default="")
    mime_type = db.Column(db.String(64), nullable=False, default="", server_default="")
    byte_size = db.Column(db.BigInteger, nullable=False, default=0, server_default="0")
    sha256 = db.Column(db.String(64), nullable=False)
    page_count = db.Column(db.Integer, nullable=False, default=1, server_default="1")

    # --- what the extraction made of it ---------------------------------
    # pending -> analysing -> analysed | failed
    status = db.Column(db.String(16), nullable=False, default="pending", server_default="pending")
    error_text = db.Column(db.Text, nullable=False, default="", server_default="")

    # sales | purchase | project_image | salary | other | unclassified
    doc_class = db.Column(
        db.String(24), nullable=False, default="unclassified", server_default="unclassified"
    )
    confidence = db.Column(db.Numeric(4, 3), nullable=False, default=0, server_default="0")

    # Denormalised out of raw_json so the list can be searched and sorted
    # without opening every payload. raw_json stays authoritative.
    issuer = db.Column(db.String(255), nullable=False, default="", server_default="")
    bill_to = db.Column(db.String(255), nullable=False, default="", server_default="")
    doc_no = db.Column(db.String(64), nullable=False, default="", server_default="")
    doc_date = db.Column(db.Date)
    currency = db.Column(db.String(8), nullable=False, default="", server_default="")
    total = db.Column(db.Numeric(14, 2))
    summary = db.Column(db.String(500), nullable=False, default="", server_default="")

    raw_json = db.Column(db.Text, nullable=False, default="", server_default="")

    # Everything the reader actually saw, before it was turned into fields.
    #
    # For a PDF with a text layer, a spreadsheet or a Word file this is the
    # text that was sent. For a photograph it is the model's transcription,
    # which is the only reading of those pixels that will ever exist -- the
    # original is a JPEG and re-reading it costs another call and may not
    # agree. Anything the structured fields have no column for is still in
    # here, which is what makes a later change of mind answerable without
    # paying to read the archive again.
    ocr_text = db.Column(db.Text, nullable=False, default="", server_default="")

    # Which document this one appears to repeat. Set by the second dedupe pass
    # and never enforced as a constraint -- two vouchers really can share a
    # number, so this flags for a human rather than refusing the upload.
    duplicate_of = db.Column(
        db.String(32), db.ForeignKey("erp_documents.id", ondelete="SET NULL"), index=True
    )

    # --- provenance of the extraction itself ----------------------------
    model_used = db.Column(db.String(64), nullable=False, default="", server_default="")
    tokens_in = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    tokens_out = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    analysed_at = db.Column(db.DateTime(timezone=True))

    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False)
    uploaded_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    def __repr__(self):
        return f"<ErpDocument {self.id} {self.company} {self.doc_class} {self.status}>"
