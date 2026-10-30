import csv
import io
import json
from datetime import datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from sqlalchemy import asc, desc, func, or_

from ..constants import DEFAULT_SCORE_RULES, GELDERLAND_CITIES, PIPELINE_STATUSES, WEBSITE_STATUSES
from ..extensions import db
from ..models import Lead, Setting
from ..services.scoring import update_lead_score

bp = Blueprint("main", __name__)


def _filters(query):
    q = request.args.get("q", "").strip()
    if q:
        pattern = f"%{q}%"; query = query.filter(or_(Lead.company_name.ilike(pattern), Lead.city.ilike(pattern), Lead.category.ilike(pattern), Lead.phone.ilike(pattern), Lead.website.ilike(pattern)))
    for arg, field in [("city", Lead.city), ("municipality", Lead.municipality), ("province", Lead.province), ("category", Lead.category), ("website_status", Lead.website_status), ("pipeline_status", Lead.pipeline_status)]:
        value = request.args.get(arg, "").strip()
        if value: query = query.filter(field == value)
    if request.args.get("favorite"): query = query.filter(Lead.favorite.is_(True))
    for arg, field, caster in [("min_rating", Lead.google_rating, float), ("min_reviews", Lead.google_review_count, int), ("min_score", Lead.lead_score, int)]:
        try:
            if request.args.get(arg): query = query.filter(field >= caster(request.args[arg]))
        except ValueError: pass
    sorting = {"score_desc": desc(Lead.lead_score), "score_asc": asc(Lead.lead_score), "reviews": desc(Lead.google_review_count), "rating": desc(Lead.google_rating), "newest": desc(Lead.created_at), "oldest": asc(Lead.created_at)}
    return query.order_by(sorting.get(request.args.get("sort", "score_desc"), desc(Lead.lead_score)))


def _context():
    return {"pipeline_statuses": PIPELINE_STATUSES, "website_statuses": WEBSITE_STATUSES, "cities": GELDERLAND_CITIES, "categories": [x[0] for x in db.session.query(Lead.category).distinct().order_by(Lead.category).all()]}


@bp.get("/")
def dashboard():
    leads = Lead.query.all(); total = len(leads)
    stats = {"total": total, "new": sum(x.pipeline_status == "Nieuw" for x in leads), "no_site": sum(x.website_status == "Geen website" for x in leads), "bad_site": sum(x.website_status == "Slechte website" for x in leads), "called": sum(x.pipeline_status == "Gebeld" for x in leads), "appointments": sum(x.pipeline_status == "Afspraak" for x in leads), "quotes": sum(x.pipeline_status == "Offerte" for x in leads), "clients": sum(x.pipeline_status == "Klant" for x in leads), "avg_score": round(sum(x.lead_score or 0 for x in leads)/total) if total else 0}
    def grouped(field): return [{"label": label or "Onbekend", "value": count} for label, count in db.session.query(field, func.count(Lead.id)).group_by(field).order_by(func.count(Lead.id).desc()).all()]
    chart_data = {"status": grouped(Lead.pipeline_status), "category": grouped(Lead.category), "city": grouped(Lead.city)}
    return render_template("dashboard.html", stats=stats, chart_data=chart_data, top_leads=Lead.query.order_by(Lead.lead_score.desc()).limit(5).all(), **_context())


@bp.get("/leads")
@bp.get("/favorites")
def leads():
    if request.path.endswith("favorites") and not request.args.get("favorite"):
        args = request.args.to_dict(); args["favorite"] = "1"; return redirect(url_for("main.leads", **args))
    result = _filters(Lead.query).all()
    return render_template("leads.html", leads=result, finder=False, **_context())


@bp.get("/finder")
def finder():
    return render_template("leads.html", leads=_filters(Lead.query).limit(20).all(), finder=True, **_context())


@bp.get("/pipeline")
def pipeline():
    columns = {status: Lead.query.filter_by(pipeline_status=status).order_by(Lead.lead_score.desc()).all() for status in PIPELINE_STATUSES}
    return render_template("pipeline.html", columns=columns, **_context())


@bp.route("/leads/<int:lead_id>", methods=["GET", "POST"])
def lead_detail(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    if request.method == "POST":
        for name in ("contact_person", "notes", "internal_comments", "pipeline_status"):
            if name in request.form: setattr(lead, name, request.form[name].strip())
        for name in ("last_contact_date", "next_contact_date"):
            value = request.form.get(name); setattr(lead, name, datetime.strptime(value, "%Y-%m-%d").date() if value else None)
        update_lead_score(lead); db.session.commit(); flash("Lead bijgewerkt.", "success")
        return redirect(url_for("main.lead_detail", lead_id=lead.id))
    from ..services.scoring import calculate_lead_score
    _, reasons = calculate_lead_score(lead)
    return render_template("lead_detail.html", lead=lead, reasons=reasons, **_context())


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        for key in ("default_province", "default_city", "default_branches", "results_limit"):
            db.session.merge(Setting(key=key, value=request.form.get(key, "").strip()))
        rules = {key: int(request.form.get(key, value)) for key, value in DEFAULT_SCORE_RULES.items()}
        db.session.merge(Setting(key="leadscore_rules", value=json.dumps(rules))); db.session.commit(); flash("Instellingen opgeslagen.", "success")
    values = {item.key: item.value for item in Setting.query.all()}
    try: rules = {**DEFAULT_SCORE_RULES, **json.loads(values.get("leadscore_rules", "{}"))}
    except ValueError: rules = DEFAULT_SCORE_RULES
    return render_template("settings.html", values=values, rules=rules, **_context())


@bp.get("/export.csv")
def export_csv():
    rows = _filters(Lead.query).all(); output = io.StringIO(); fields = [c.name for c in Lead.__table__.columns if c.name != "id"]
    writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
    for lead in rows: writer.writerow({key: getattr(lead, key) or "" for key in fields})
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=yn-leads.csv"})


@bp.post("/import")
def import_csv():
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"): flash("Kies een CSV-bestand.", "error"); return redirect(url_for("main.leads"))
    text = file.stream.read().decode("utf-8-sig"); reader = csv.DictReader(io.StringIO(text)); created = 0
    allowed = {c.name for c in Lead.__table__.columns} - {"id", "created_at", "updated_at"}
    for row in reader:
        name = (row.get("company_name") or "").strip()
        if not name: continue
        duplicate = Lead.query.filter(or_(func.lower(Lead.company_name)==name.lower(), Lead.phone==row.get("phone"), Lead.website==row.get("website"))).first()
        if duplicate: continue
        data = {key: value.strip() for key, value in row.items() if key in allowed and value and key not in {"favorite", "google_rating", "google_review_count", "website_score", "lead_score"}}
        for key, caster in [("google_rating", float), ("google_review_count", int), ("website_score", int)]:
            try:
                if row.get(key): data[key] = caster(row[key])
            except ValueError: pass
        lead = Lead(**data); update_lead_score(lead); db.session.add(lead); created += 1
    db.session.commit(); flash(f"{created} nieuwe leads geïmporteerd.", "success"); return redirect(url_for("main.leads"))
