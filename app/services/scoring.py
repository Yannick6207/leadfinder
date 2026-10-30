import json
from flask import current_app
from ..constants import DEFAULT_SCORE_RULES
from ..extensions import db
from ..models import Setting


def get_score_rules():
    setting = db.session.get(Setting, "leadscore_rules")
    if not setting: return DEFAULT_SCORE_RULES.copy()
    try: return {**DEFAULT_SCORE_RULES, **json.loads(setting.value)}
    except (TypeError, ValueError): return DEFAULT_SCORE_RULES.copy()


def calculate_lead_score(lead, rules=None):
    rules = rules or get_score_rules(); reasons = []
    def add(condition, key, label):
        if condition and rules.get(key, 0): reasons.append({"label": label, "points": int(rules[key])})
    add(not lead.website or lead.website_status == "Geen website", "no_website", "Geen website")
    add(bool(lead.website) and lead.website_status == "Slechte website", "bad_website", "Slechte website")
    add(bool(lead.phone), "phone", "Telefoonnummer gevonden")
    add(bool(lead.email), "email", "E-mailadres gevonden")
    add(bool(lead.instagram or lead.facebook), "social", "Socialmedia-profiel gevonden")
    add((lead.google_review_count or 0) > 10, "reviews_over_10", f"{lead.google_review_count} Google-reviews")
    add((lead.google_rating or 0) >= 4.0, "rating_4", f"Rating {lead.google_rating:.1f}")
    add((lead.google_rating or 0) >= 4.5, "rating_45_extra", "Uitstekende rating")
    return min(100, sum(item["points"] for item in reasons)), reasons


def update_lead_score(lead):
    lead.lead_score, _ = calculate_lead_score(lead)
    return lead.lead_score
