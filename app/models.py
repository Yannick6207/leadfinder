from datetime import datetime, timezone
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(160), index=True)
    company_name = db.Column(db.String(180), nullable=False, index=True)
    category = db.Column(db.String(120), index=True)
    address = db.Column(db.String(255)); city = db.Column(db.String(120), index=True)
    municipality = db.Column(db.String(120), index=True); province = db.Column(db.String(120), default="Gelderland", index=True)
    phone = db.Column(db.String(80), index=True); email = db.Column(db.String(180)); website = db.Column(db.String(500), index=True)
    instagram = db.Column(db.String(500)); facebook = db.Column(db.String(500))
    google_rating = db.Column(db.Float); google_review_count = db.Column(db.Integer, default=0)
    website_status = db.Column(db.String(80), default="Nog niet gecontroleerd", index=True); website_score = db.Column(db.Integer)
    lead_score = db.Column(db.Integer, default=0, index=True); pipeline_status = db.Column(db.String(80), default="Nieuw", index=True)
    favorite = db.Column(db.Boolean, default=False, index=True); contact_person = db.Column(db.String(180))
    notes = db.Column(db.Text); internal_comments = db.Column(db.Text)
    last_contact_date = db.Column(db.Date); next_contact_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False); updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    analysis = db.relationship("WebsiteAnalysis", back_populates="lead", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class WebsiteAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True); lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), unique=True, nullable=False)
    reachable = db.Column(db.Boolean, default=False); https = db.Column(db.Boolean, default=False); response_time = db.Column(db.Float)
    mobile_friendly = db.Column(db.Boolean, default=False); viewport_present = db.Column(db.Boolean, default=False)
    title_present = db.Column(db.Boolean, default=False); meta_description_present = db.Column(db.Boolean, default=False)
    contact_details_present = db.Column(db.Boolean, default=False); contact_form_present = db.Column(db.Boolean, default=False)
    social_links_present = db.Column(db.Boolean, default=False); broken_links_count = db.Column(db.Integer, default=0)
    detected_copyright_year = db.Column(db.Integer); outdated_html_signals = db.Column(db.Text)
    score = db.Column(db.Integer, default=0); recommendations = db.Column(db.Text); checked_at = db.Column(db.DateTime, default=utcnow)
    lead = db.relationship("Lead", back_populates="analysis")


class Setting(db.Model):
    key = db.Column(db.String(120), primary_key=True); value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
