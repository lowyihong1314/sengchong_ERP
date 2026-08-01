# models/project_photos.py
from models import db


class ErpProjectPhoto(db.Model):
    """
    A photo attached to a project.

    New photos default to private and not website-visible. Only a photo with
    both is_public and website_visible set may be rendered on sengchong.com.
    """

    __tablename__ = "erp_project_photos"
    __table_args__ = (
        # Gallery order within one project.
        db.Index("idx_erp_project_photos_project", "project_id", "sort_order", "created_at"),
        # The public sengchong.com gallery query.
        db.Index(
            "idx_erp_project_photos_public",
            "company",
            "is_public",
            "website_visible",
            "sort_order",
        ),
    )

    id = db.Column(db.String(32), primary_key=True)  # uuid4().hex
    project_id = db.Column(
        db.String(32),
        db.ForeignKey("erp_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    company = db.Column(db.String(64), nullable=False)

    stored_path = db.Column(db.String(512), nullable=False)
    thumbnail_path = db.Column(db.String(512), nullable=False, default="", server_default="")
    content_type = db.Column(
        db.String(64), nullable=False, default="image/jpeg", server_default="image/jpeg"
    )
    original_filename = db.Column(db.String(255), nullable=False, default="", server_default="")

    service_category = db.Column(db.String(64), nullable=False, default="", server_default="")
    caption = db.Column(db.Text, nullable=False, default="", server_default="")
    alt_text = db.Column(db.Text, nullable=False, default="", server_default="")

    is_public = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    website_visible = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    is_cover = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    uploaded_by = db.Column(db.String(64), nullable=False, default="", server_default="")
    updated_by = db.Column(db.String(64), nullable=False, default="", server_default="")

    project = db.relationship("ErpProject", back_populates="photos")

    def __repr__(self):
        return f"<ErpProjectPhoto {self.id} public={self.is_public}>"
