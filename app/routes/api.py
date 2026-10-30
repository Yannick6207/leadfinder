from datetime import date
from flask import Blueprint, jsonify, request
from sqlalchemy import or_
from ..extensions import db
from ..models import Lead, WebsiteAnalysis
from ..services.providers import ProviderError, get_provider
from ..services.scoring import calculate_lead_score, update_lead_score
from ..services.website_analyzer import analyze_website, website_status

bp = Blueprint("api", __name__)


@bp.post("/search")
def search():
    data = request.get_json(silent=True) or {}
    city = str(data.get("city", "Arnhem")).strip()[:120]
    category = str(data.get("category", "Lokale ondernemer")).strip()[:120]
    try:
        limit = min(max(int(data.get("limit", 10)), 1), 50)
        results = get_provider().search_businesses(city, category, limit)
    except (TypeError, ValueError):
        return jsonify({"message": "Het maximale aantal resultaten is ongeldig."}), 400
    except ProviderError as exc:
        return jsonify({"message": str(exc)}), 502
    created = []; duplicates = 0
    for item in results:
        duplicate_checks = [Lead.external_id == item.get("external_id")]
        if item.get("phone"):
            duplicate_checks.append(Lead.phone == item["phone"])
        if item.get("website"):
            duplicate_checks.append(Lead.website == item["website"])
        duplicate = Lead.query.filter(or_(*duplicate_checks)).first()
        if duplicate: duplicates += 1; continue
        lead = Lead(**{key: value for key, value in item.items() if hasattr(Lead, key)})
        lead.website_status = "Nog niet gecontroleerd" if lead.website else "Geen website"; update_lead_score(lead); db.session.add(lead); db.session.flush(); created.append({"id": lead.id, "name": lead.company_name})
    db.session.commit(); return jsonify({"created": created, "duplicates": duplicates, "total": len(results)})


@bp.post("/leads/<int:lead_id>/favorite")
def favorite(lead_id):
    lead = db.get_or_404(Lead, lead_id); lead.favorite = not lead.favorite; db.session.commit(); return jsonify({"favorite": lead.favorite})


@bp.patch("/leads/<int:lead_id>/status")
def status(lead_id):
    lead = db.get_or_404(Lead, lead_id); lead.pipeline_status = (request.get_json() or {}).get("status", lead.pipeline_status)
    if lead.pipeline_status == "Gebeld": lead.last_contact_date = date.today()
    db.session.commit(); return jsonify({"status": lead.pipeline_status})


@bp.post("/leads/<int:lead_id>/analyze")
def analyze(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    if not lead.website: lead.website_status = "Geen website"; update_lead_score(lead); db.session.commit(); return jsonify({"status": lead.website_status, "score": None})
    try: result = analyze_website(lead.website)
    except Exception as exc:
        result = {"reachable": False, "https": lead.website.startswith("https://"), "score": 0, "recommendations": f"Analyse mislukt: {str(exc)[:180]}"}
    analysis = lead.analysis or WebsiteAnalysis(lead_id=lead.id)
    for key, value in result.items():
        if hasattr(analysis, key): setattr(analysis, key, value)
    lead.website_score = result["score"]; lead.website_status = website_status(result["score"]); update_lead_score(lead); db.session.add(analysis); db.session.commit()
    return jsonify({"status": lead.website_status, "score": lead.website_score, "recommendations": result["recommendations"]})


@bp.get("/leads/<int:lead_id>/demo-prompt")
def demo_prompt(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    style = "een warme, toegankelijke lokale stijl" if lead.category in {"Kapper", "Schoonheidssalon", "Restaurant"} else "een strakke, betrouwbare vakmanschapstijl"
    cta = "Reserveer direct" if lead.category == "Restaurant" else "Plan een afspraak"
    prompt = f"Maak een moderne website voor {lead.company_name} uit {lead.city}. Het bedrijf is actief als {lead.category.lower()} en heeft een Google-rating van {lead.google_rating or 'onbekend'} op basis van {lead.google_review_count or 0} reviews. Kies {style}, met diep petrol, helder wit en een rustige zandgrijze steunkleur. Voeg Home, Diensten, Over ons, Reviews en Contact toe. Gebruik duidelijke CTA's zoals '{cta}' en 'Bel direct'. Zorg voor een snelle mobiele ervaring, lokale SEO en zichtbare contactgegevens."
    return jsonify({"prompt": prompt})
